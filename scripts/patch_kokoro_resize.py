#!/usr/bin/env python3
"""
patch_kokoro_resize.py — Kokoro ONNX graph surgery for OpenVINO GPU EP.

Two fixes, in order:
  1. Symbolic shape inference — stamps static ranks onto value_info so the
     ORT->OpenVINO partitioner stops producing dynamic-rank Parameters
     (the STFT boundary failure on the OV CPU plugin).
  2. 3D->4D linear Resize rewrite — wraps each 3D `linear` Resize in
     Unsqueeze(axes=[2]) / Squeeze(axes=[2]) so it becomes a 4D resize with
     H=1, which the intel_gpu plugin accepts. Mathematically identical to
     1D linear interpolation along the last axis. Also patches the
     scales/sizes input from rank-3 to rank-4 (constant or dynamic).

Usage:
  # Patch (shape-infer + resize rewrite), write new model:
  python patch_kokoro_resize.py \
      --model  /data/intel-igpu-tts/models/kokoro-v0_19.onnx \
      --output /data/intel-igpu-tts/models/kokoro-v0_19.gpu4d.onnx

  # Shape inference ONLY (test whether annotation alone fixes OV-CPU EP):
  python patch_kokoro_resize.py --model ... --output ... --shape-infer-only

  # Patch + waveform parity check vs. original on ORT CPU:
  python patch_kokoro_resize.py --model ... --output ... \
      --check --voices /data/intel-igpu-tts/models/voices-v1.0.bin

Requires: onnx, numpy, onnxruntime (any flavor; parity uses CPU EP).
"""

import argparse
import sys

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def get_onnx_opset(model: onnx.ModelProto) -> int:
    for imp in model.opset_import:
        if imp.domain in ("", "ai.onnx"):
            return imp.version
    return 13


def run_symbolic_shape_inference(model: onnx.ModelProto) -> onnx.ModelProto:
    """Best effort: ORT symbolic shape inference, fallback to onnx native."""
    try:
        from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference
        inferred = SymbolicShapeInference.infer_shapes(
            model, auto_merge=True, guess_output_rank=True
        )
        print("[shape-infer] ORT symbolic shape inference: OK")
        return inferred
    except Exception as e:
        print(f"[shape-infer] ORT symbolic inference failed ({e}); "
              f"falling back to onnx.shape_inference")
        try:
            inferred = onnx.shape_inference.infer_shapes(model, strict_mode=False)
            print("[shape-infer] onnx native shape inference: OK")
            return inferred
        except Exception as e2:
            print(f"[shape-infer] native inference also failed ({e2}); "
                  f"continuing with original graph")
            return model


def build_rank_map(model: onnx.ModelProto) -> dict:
    """tensor name -> rank (len of shape) where known."""
    ranks = {}
    graph = model.graph
    for vi in list(graph.value_info) + list(graph.input) + list(graph.output):
        tt = vi.type.tensor_type
        if tt.HasField("shape"):
            ranks[vi.name] = len(tt.shape.dim)
    for init in graph.initializer:
        ranks[init.name] = len(init.dims)
    return ranks


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


def make_axes_input(graph, node_list, base_name, axes, opset):
    """
    Returns (inputs_extra, attrs) for Unsqueeze/Squeeze depending on opset:
    opset >= 13 -> axes is a tensor input; else an attribute.
    """
    if opset >= 13:
        axes_name = f"{base_name}_axes"
        graph.initializer.append(
            numpy_helper.from_array(np.array(axes, dtype=np.int64), name=axes_name)
        )
        return [axes_name], {}
    return [], {"axes": axes}


# ----------------------------------------------------------------------
# the resize rewrite
# ----------------------------------------------------------------------

def patch_3d_linear_resizes(model: onnx.ModelProto) -> int:
    """
    Wrap every 3D linear Resize in Unsqueeze/Squeeze and lift its
    scales/sizes to rank 4. Returns number of nodes patched.
    """
    graph = model.graph
    opset = get_onnx_opset(model)
    ranks = build_rank_map(model)
    patched = 0

    # iterate over a snapshot; we mutate graph.node in place
    for node in list(graph.node):
        if node.op_type != "Resize":
            continue
        mode = get_attr(node, "mode", "nearest")
        if mode != "linear":
            continue

        x_name = node.input[0]
        rank = ranks.get(x_name)

        # If rank unknown, fall back to targeting the known offenders
        # (the l_sin_gen sine-generator path) by name.
        if rank is None:
            if "l_sin_gen" in node.name or "m_source" in node.name:
                print(f"[resize] {node.name}: rank unknown, matched by name; "
                      f"assuming 3D")
                rank = 3
            else:
                print(f"[resize] {node.name}: linear mode but rank unknown "
                      f"and name doesn't match l_sin_gen — SKIPPING "
                      f"(rerun after shape inference or add --force)")
                continue

        if rank != 3:
            print(f"[resize] {node.name}: linear, rank {rank} — no patch needed")
            continue

        print(f"[resize] patching {node.name} (3D linear -> 4D)")
        tag = f"r3to4_{patched}"

        # ---- Unsqueeze input:  [N,C,L] -> [N,C,1,L] ----
        unsq_out = f"{x_name}_{tag}_4d"
        extra_in, attrs = make_axes_input(graph, graph.node, f"{tag}_unsq", [2], opset)
        unsq_node = helper.make_node(
            "Unsqueeze", [x_name] + extra_in, [unsq_out],
            name=f"{tag}_Unsqueeze", **attrs
        )
        node.input[0] = unsq_out

        # ---- Patch scales (input 2) or sizes (input 3): rank 3 -> 4 ----
        # Inserted spatial axis is axis 2; its scale is 1.0 / its size is 1.
        def lift_param(idx, dtype, one_value):
            nonlocal_new_nodes = []
            if len(node.input) <= idx or node.input[idx] == "":
                return nonlocal_new_nodes
            pname = node.input[idx]
            init = find_initializer(graph, pname)
            if init is not None:
                arr = numpy_helper.to_array(init)
                if arr.size == 3:
                    new_arr = np.insert(arr, 2, one_value).astype(dtype)
                    new_name = f"{pname}_{tag}_4d"
                    graph.initializer.append(
                        numpy_helper.from_array(new_arr, name=new_name)
                    )
                    node.input[idx] = new_name
                    print(f"         constant {'scales' if idx == 2 else 'sizes'}: "
                          f"{arr.tolist()} -> {new_arr.tolist()}")
                elif arr.size in (0, 4):
                    pass  # empty roi-style or already 4 — leave alone
                else:
                    print(f"         WARNING: param {pname} has {arr.size} elems; "
                          f"left untouched")
                return nonlocal_new_nodes

            # dynamic scales/sizes: splice a 1 into position 2 via Slice+Concat
            np_dtype = np.float32 if dtype == np.float32 else np.int64
            one_name = f"{tag}_one_{idx}"
            graph.initializer.append(
                numpy_helper.from_array(np.array([one_value], dtype=np_dtype),
                                        name=one_name)
            )
            s0, s1 = f"{tag}_st0_{idx}", f"{tag}_en0_{idx}"
            s2, s3 = f"{tag}_st1_{idx}", f"{tag}_en1_{idx}"
            for nm, val in ((s0, [0]), (s1, [2]), (s2, [2]), (s3, [3])):
                graph.initializer.append(
                    numpy_helper.from_array(np.array(val, dtype=np.int64), name=nm)
                )
            head = f"{pname}_{tag}_head"
            tail = f"{pname}_{tag}_tail"
            out4 = f"{pname}_{tag}_4d"
            nonlocal_new_nodes.append(helper.make_node(
                "Slice", [pname, s0, s1], [head], name=f"{tag}_slice_head_{idx}"))
            nonlocal_new_nodes.append(helper.make_node(
                "Slice", [pname, s2, s3], [tail], name=f"{tag}_slice_tail_{idx}"))
            nonlocal_new_nodes.append(helper.make_node(
                "Concat", [head, one_name, tail], [out4],
                name=f"{tag}_concat_{idx}", axis=0))
            node.input[idx] = out4
            print(f"         dynamic {'scales' if idx == 2 else 'sizes'}: "
                  f"spliced 1 at axis 2 via Slice/Concat")
            return nonlocal_new_nodes

        new_nodes = []
        new_nodes += lift_param(2, np.float32, 1.0)   # scales
        new_nodes += lift_param(3, np.int64, 1)       # sizes

        # ---- Squeeze output back:  [N,C,1,L'] -> [N,C,L'] ----
        orig_out = node.output[0]
        resize_out_4d = f"{orig_out}_{tag}_4d"
        node.output[0] = resize_out_4d
        extra_in, attrs = make_axes_input(graph, graph.node, f"{tag}_sq", [2], opset)
        sq_node = helper.make_node(
            "Squeeze", [resize_out_4d] + extra_in, [orig_out],
            name=f"{tag}_Squeeze", **attrs
        )

        # insert nodes in topological position (just before the Resize)
        pos = list(graph.node).index(node)
        for i, n in enumerate([unsq_node] + new_nodes):
            graph.node.insert(pos + i, n)
        graph.node.insert(list(graph.node).index(node) + 1, sq_node)

        # stale rank info for the (renamed) resize output no longer applies;
        # remove any value_info entry for the intermediate name we created
        patched += 1

    return patched


# ----------------------------------------------------------------------
# parity check
# ----------------------------------------------------------------------

def load_style(voices_path: str, voice: str, n_tokens: int) -> np.ndarray:
    voices = np.load(voices_path)
    ref = voices[voice]                      # (510, 1, 256)
    style = ref[min(n_tokens, ref.shape[0] - 1)]
    return style.reshape(1, 256).astype(np.float32)


def run_model(path: str, feeds: dict) -> np.ndarray:
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(path, sess_options=so,
                                providers=["CPUExecutionProvider"])
    return sess.run(None, feeds)[0]


def parity_check(orig: str, patched: str, voices: str, voice: str) -> bool:
    rng = np.random.default_rng(1234)
    n_tok = 32
    tokens = rng.integers(1, 100, size=(1, n_tok), dtype=np.int64)
    feeds = {
        "tokens": tokens,
        "style": load_style(voices, voice, n_tok),
        "speed": np.array([1.0], dtype=np.float32),
    }
    print("[parity] running original on ORT CPU...")
    a = run_model(orig, feeds)
    print(f"[parity] original: shape={a.shape} "
          f"min={a.min():.5f} max={a.max():.5f}")
    print("[parity] running patched on ORT CPU...")
    b = run_model(patched, feeds)
    print(f"[parity] patched:  shape={b.shape} "
          f"min={b.min():.5f} max={b.max():.5f}")

    if a.shape != b.shape:
        print(f"[parity] FAIL: shape mismatch {a.shape} vs {b.shape}")
        return False
    max_abs = float(np.max(np.abs(a - b)))
    denom = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    corr = float(np.sum(a * b) / denom) if denom > 0 else 0.0
    print(f"[parity] max_abs_diff={max_abs:.6e}  waveform_corr={corr:.6f}")
    ok = max_abs < 1e-3 and corr > 0.9999
    print(f"[parity] {'PASS' if ok else 'FAIL'} "
          f"(thresholds: max_abs<1e-3, corr>0.9999)")
    return ok


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="input ONNX model")
    ap.add_argument("--output", required=True, help="output (patched) ONNX model")
    ap.add_argument("--shape-infer-only", action="store_true",
                    help="only run symbolic shape inference, no resize rewrite")
    ap.add_argument("--no-shape-infer", action="store_true",
                    help="skip shape inference, only rewrite resizes")
    ap.add_argument("--check", action="store_true",
                    help="run waveform parity check original vs patched (ORT CPU)")
    ap.add_argument("--voices", default=None, help="voices NPZ (for --check)")
    ap.add_argument("--voice", default="af_bella", help="voice key (for --check)")
    args = ap.parse_args()

    print(f"[load] {args.model}")
    model = onnx.load(args.model)
    opset = get_onnx_opset(model)
    print(f"[load] opset={opset} nodes={len(model.graph.node)}")

    if not args.no_shape_infer:
        model = run_symbolic_shape_inference(model)

    if not args.shape_infer_only:
        n = patch_3d_linear_resizes(model)
        print(f"[resize] patched {n} node(s)")
        if n == 0:
            print("[resize] WARNING: nothing patched — check node names/ranks")

    try:
        onnx.checker.check_model(model, full_check=False)
        print("[check] onnx.checker: OK")
    except Exception as e:
        print(f"[check] onnx.checker warning: {e}")

    onnx.save(model, args.output,
              save_as_external_data=False)
    print(f"[save] {args.output}")

    if args.check:
        if not args.voices:
            print("--check requires --voices", file=sys.stderr)
            sys.exit(2)
        ok = parity_check(args.model, args.output, args.voices, args.voice)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
