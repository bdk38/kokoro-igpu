#!/usr/bin/env python3
"""
patch_kokoro_v2.py — Kokoro ONNX surgery for OpenVINO EP, round 2.

Adds to the v1 resize rewrite:

  --stamp-stft          Stamp static rank-4 value_info on every STFT output
                        ([batch, frames, dft_bins, 2], dims symbolic), then
                        re-run native shape inference to propagate ranks
                        downstream. Targets the dynamic-rank Parameter
                        failure at the ORT->OpenVINO partition boundary.

  --probe-determinism   Run the ORIGINAL model twice with identical feeds
                        and report the diff. If the model contains
                        RandomNormal/RandomUniform (noise source in
                        m_source), two runs of the SAME model won't match —
                        which would explain the 4.65e-2 parity delta.

Typical round-2 sequence:

  # 0. settle the parity question (no output model written):
  python patch_kokoro_v2.py --model models/kokoro-v0_19.onnx \
      --probe-determinism --voices models/voices-v1.0.bin

  # 1. resize rewrite + STFT rank stamp in one pass:
  python patch_kokoro_v2.py \
      --model  models/kokoro-v0_19.onnx \
      --output models/patched/kokoro-v0_19.gpu4d.stft.onnx \
      --stamp-stft

  # 2. retry GPU / CPU / HETERO on the new file, read the next error.
"""

import argparse
import sys

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


# ----------------------------------------------------------------------
# shared helpers (unchanged from v1)
# ----------------------------------------------------------------------

def get_onnx_opset(model):
    for imp in model.opset_import:
        if imp.domain in ("", "ai.onnx"):
            return imp.version
    return 13


def get_attr(node, name, default=None):
    for a in node.attribute:
        if a.name == name:
            if a.type == onnx.AttributeProto.STRING:
                return a.s.decode()
            return helper.get_attribute_value(a)
    return default


def find_initializer(graph, name):
    for init in graph.initializer:
        if init.name == name:
            return init
    return None


def build_rank_map(model):
    ranks = {}
    g = model.graph
    for vi in list(g.value_info) + list(g.input) + list(g.output):
        tt = vi.type.tensor_type
        if tt.HasField("shape"):
            ranks[vi.name] = len(tt.shape.dim)
    for init in g.initializer:
        ranks[init.name] = len(init.dims)
    return ranks


def make_axes_input(graph, base_name, axes, opset):
    if opset >= 13:
        axes_name = f"{base_name}_axes"
        graph.initializer.append(
            numpy_helper.from_array(np.array(axes, dtype=np.int64), name=axes_name))
        return [axes_name], {}
    return [], {"axes": axes}


def run_shape_inference(model):
    try:
        from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference
        m = SymbolicShapeInference.infer_shapes(
            model, auto_merge=True, guess_output_rank=True)
        print("[shape-infer] ORT symbolic: OK")
        return m
    except Exception as e:
        print(f"[shape-infer] ORT symbolic failed ({type(e).__name__}: {e})")
    try:
        m = onnx.shape_inference.infer_shapes(model, strict_mode=False)
        print("[shape-infer] onnx native: OK")
        return m
    except Exception as e:
        print(f"[shape-infer] onnx native failed ({e}); using graph as-is")
        return model


# ----------------------------------------------------------------------
# fix 1: 3D->4D linear Resize (identical logic to v1)
# ----------------------------------------------------------------------

def patch_3d_linear_resizes(model):
    graph = model.graph
    opset = get_onnx_opset(model)
    ranks = build_rank_map(model)
    patched = 0

    for node in list(graph.node):
        if node.op_type != "Resize" or get_attr(node, "mode", "nearest") != "linear":
            continue
        x_name = node.input[0]
        rank = ranks.get(x_name)
        if rank is None:
            if "l_sin_gen" in node.name or "m_source" in node.name:
                rank = 3
            else:
                print(f"[resize] {node.name}: rank unknown, name no match — skip")
                continue
        if rank != 3:
            continue

        print(f"[resize] patching {node.name} (3D linear -> 4D)")
        tag = f"r3to4_{patched}"

        unsq_out = f"{x_name}_{tag}_4d"
        extra, attrs = make_axes_input(graph, f"{tag}_unsq", [2], opset)
        unsq = helper.make_node("Unsqueeze", [x_name] + extra, [unsq_out],
                                name=f"{tag}_Unsqueeze", **attrs)
        node.input[0] = unsq_out

        new_nodes = []

        def lift(idx, dtype, one_value):
            if len(node.input) <= idx or node.input[idx] == "":
                return
            pname = node.input[idx]
            init = find_initializer(graph, pname)
            if init is not None:
                arr = numpy_helper.to_array(init)
                if arr.size == 3:
                    new_arr = np.insert(arr, 2, one_value).astype(dtype)
                    nn = f"{pname}_{tag}_4d"
                    graph.initializer.append(numpy_helper.from_array(new_arr, name=nn))
                    node.input[idx] = nn
                    print(f"         constant param: {arr.tolist()} -> {new_arr.tolist()}")
                return
            np_dtype = np.float32 if dtype == np.float32 else np.int64
            one = f"{tag}_one_{idx}"
            graph.initializer.append(
                numpy_helper.from_array(np.array([one_value], dtype=np_dtype), name=one))
            names = {}
            for suffix, val in (("st0", [0]), ("en0", [2]), ("st1", [2]), ("en1", [3])):
                nm = f"{tag}_{suffix}_{idx}"
                graph.initializer.append(
                    numpy_helper.from_array(np.array(val, dtype=np.int64), name=nm))
                names[suffix] = nm
            head, tail, out4 = (f"{pname}_{tag}_head", f"{pname}_{tag}_tail",
                                f"{pname}_{tag}_4d")
            new_nodes.append(helper.make_node(
                "Slice", [pname, names["st0"], names["en0"]], [head],
                name=f"{tag}_slh_{idx}"))
            new_nodes.append(helper.make_node(
                "Slice", [pname, names["st1"], names["en1"]], [tail],
                name=f"{tag}_slt_{idx}"))
            new_nodes.append(helper.make_node(
                "Concat", [head, one, tail], [out4], name=f"{tag}_cc_{idx}", axis=0))
            node.input[idx] = out4
            print("         dynamic param: spliced 1 at axis 2")

        lift(2, np.float32, 1.0)
        lift(3, np.int64, 1)

        orig_out = node.output[0]
        mid = f"{orig_out}_{tag}_4d"
        node.output[0] = mid
        extra, attrs = make_axes_input(graph, f"{tag}_sq", [2], opset)
        sq = helper.make_node("Squeeze", [mid] + extra, [orig_out],
                              name=f"{tag}_Squeeze", **attrs)

        pos = list(graph.node).index(node)
        for i, n in enumerate([unsq] + new_nodes):
            graph.node.insert(pos + i, n)
        graph.node.insert(list(graph.node).index(node) + 1, sq)
        patched += 1

    return patched


# ----------------------------------------------------------------------
# fix 2: stamp static rank on STFT outputs
# ----------------------------------------------------------------------

def stamp_stft_rank(model):
    """
    ONNX STFT output is always rank 4: [batch, frames, dft_unique_bins, 2].
    Frames/bins are data-dependent (dynamic dims are fine for OV); it's the
    missing RANK that turns the partition Parameter dynamic-rank. Stamp it,
    then re-run native shape inference so downstream ranks resolve too.
    """
    graph = model.graph
    existing = {vi.name for vi in graph.value_info}
    stamped = 0

    for node in graph.node:
        if node.op_type != "STFT":
            continue
        out = node.output[0]
        print(f"[stft] found STFT node: {node.name} -> {out}")
        if out in existing:
            # replace whatever partial info exists with an explicit rank-4
            for vi in graph.value_info:
                if vi.name == out:
                    graph.value_info.remove(vi)
                    break
        vi = helper.make_tensor_value_info(
            out, TensorProto.FLOAT,
            [f"stft_batch_{stamped}", f"stft_frames_{stamped}",
             f"stft_bins_{stamped}", 2])
        graph.value_info.append(vi)
        print(f"[stft] stamped {out} as rank-4 "
              f"[batch, frames, bins, 2] (dims symbolic)")
        stamped += 1

    if stamped == 0:
        print("[stft] WARNING: no STFT nodes found in graph")
        return 0

    # propagate downstream — native inference now has an anchor to work from
    return stamped


# ----------------------------------------------------------------------
# determinism probe
# ----------------------------------------------------------------------

def list_random_ops(model):
    hits = [n for n in model.graph.node
            if n.op_type in ("RandomNormal", "RandomNormalLike",
                             "RandomUniform", "RandomUniformLike",
                             "Multinomial", "Bernoulli")]
    return hits


def load_style(voices_path, voice, n_tokens):
    voices = np.load(voices_path)
    ref = voices[voice]
    style = ref[min(n_tokens, ref.shape[0] - 1)]
    return style.reshape(1, 256).astype(np.float32)


def probe_determinism(model_path, voices, voice):
    import onnxruntime as ort
    model = onnx.load(model_path)
    rnd = list_random_ops(model)
    if rnd:
        print(f"[probe] graph contains {len(rnd)} random op(s):")
        for n in rnd:
            print(f"        {n.op_type}  {n.name}")
    else:
        print("[probe] no Random* ops found in graph")

    rng = np.random.default_rng(1234)
    n_tok = 32
    feeds = {
        "tokens": rng.integers(1, 100, size=(1, n_tok), dtype=np.int64),
        "style": load_style(voices, voice, n_tok),
        "speed": np.array([1.0], dtype=np.float32),
    }
    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(model_path, sess_options=so,
                                providers=["CPUExecutionProvider"])
    a = sess.run(None, feeds)[0]
    b = sess.run(None, feeds)[0]
    max_abs = float(np.max(np.abs(a - b)))
    denom = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    corr = float(np.sum(a * b) / denom) if denom > 0 else 0.0
    print(f"[probe] SAME model, run twice, same feeds:")
    print(f"[probe] max_abs_diff={max_abs:.6e}  corr={corr:.6f}")
    if max_abs > 1e-4:
        print("[probe] => model is stochastic; parity gates must use "
              "correlation, not bit-exactness. Your 4.65e-2 delta is "
              "explained if this number is in the same ballpark.")
    else:
        print("[probe] => model is deterministic; a large patched-vs-original "
              "diff would be real and worth investigating.")


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--output", default=None,
                    help="output model (required unless --probe-determinism)")
    ap.add_argument("--stamp-stft", action="store_true",
                    help="stamp rank-4 value_info on STFT outputs")
    ap.add_argument("--no-resize-patch", action="store_true",
                    help="skip the 3D->4D resize rewrite")
    ap.add_argument("--no-shape-infer", action="store_true")
    ap.add_argument("--probe-determinism", action="store_true",
                    help="run original model twice, report diff, exit")
    ap.add_argument("--voices", default=None)
    ap.add_argument("--voice", default="af_bella")
    args = ap.parse_args()

    if args.probe_determinism:
        if not args.voices:
            print("--probe-determinism requires --voices", file=sys.stderr)
            sys.exit(2)
        probe_determinism(args.model, args.voices, args.voice)
        return

    if not args.output:
        print("--output is required", file=sys.stderr)
        sys.exit(2)

    print(f"[load] {args.model}")
    model = onnx.load(args.model)
    print(f"[load] opset={get_onnx_opset(model)} nodes={len(model.graph.node)}")

    if not args.no_shape_infer:
        model = run_shape_inference(model)

    if not args.no_resize_patch:
        n = patch_3d_linear_resizes(model)
        print(f"[resize] patched {n} node(s)")

    if args.stamp_stft:
        stamp_stft_rank(model)
        # propagation pass with the STFT anchor in place
        model = run_shape_inference(model)
        # inference engines don't understand STFT and may CLOBBER the stamp
        # with an empty/rank-0 entry — re-stamp so the partition-boundary
        # tensor is guaranteed to carry rank 4 in the saved model
        print("[stft] re-stamping after propagation (guard against clobber)")
        stamp_stft_rank(model)
        # verify the anchor survived
        for vi in model.graph.value_info:
            if any(vi.name == n.output[0] for n in model.graph.node
                   if n.op_type == "STFT"):
                r = len(vi.type.tensor_type.shape.dim)
                print(f"[stft] final check: {vi.name} rank={r} "
                      f"{'OK' if r == 4 else 'STILL BROKEN'}")

    try:
        onnx.checker.check_model(model, full_check=False)
        print("[check] onnx.checker: OK")
    except Exception as e:
        print(f"[check] onnx.checker warning: {e}")

    onnx.save(model, args.output)
    print(f"[save] {args.output}")


if __name__ == "__main__":
    main()
