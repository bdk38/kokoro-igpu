#!/usr/bin/env python3
"""
test_kokoro_ov_direct.py — run patched Kokoro through the OpenVINO runtime
DIRECTLY (ov.Core), bypassing the ONNX Runtime OpenVINO EP and its
partitioning entirely. One whole-graph compile, one device, no
subgraph-boundary Parameters. (The OpenArc-style architecture.)

Only viable on models that compile under OpenVINO — i.e. the v2-patched
graph (4D resizes + STFT rank stamp).

Usage:
  source /data/intel-igpu-tts/scripts/env.sh

  # GPU FP32 first (settles the FP16-overflow question at the same time):
  python scripts/test_kokoro_ov_direct.py \
      --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
      --voices models/voices-v1.0.bin \
      --device GPU --precision f32 --static \
      --compare-ort --wav artifacts/ov_direct_gpu_f32.wav

  # then GPU FP16, then CPU for a control:
  ... --device GPU --precision f16 --static
  ... --device CPU --precision f32

Flags worth knowing:
  --static        reshape inputs to fixed shapes before compile
                  (tokens [1,N]). The intel_gpu plugin is much happier
                  with static shapes; strongly recommended for GPU.
  --profile       per-op performance counters from the compiled model —
                  proves where execution actually happened and where
                  time went.
  --compare-ort   also run ORT CPU on identical feeds and report
                  correlation (requires onnxruntime).
"""

import argparse
import struct
import sys
import time
import wave

import numpy as np


def load_style(voices_path, voice, n_tokens):
    voices = np.load(voices_path)
    if voice not in voices:
        print(f"voice '{voice}' not in archive; available: "
              f"{list(voices.keys())[:8]}...", file=sys.stderr)
        sys.exit(2)
    ref = voices[voice]                       # (510, 1, 256)
    style = ref[min(n_tokens, ref.shape[0] - 1)]
    return style.reshape(1, 256).astype(np.float32)


def make_feeds(args):
    rng = np.random.default_rng(args.seed)
    tokens = rng.integers(1, 100, size=(1, args.tokens), dtype=np.int64)
    return {
        "tokens": tokens,
        "style": load_style(args.voices, args.voice, args.tokens),
        "speed": np.array([args.speed], dtype=np.float32),
    }


def audio_stats(name, a):
    a = np.asarray(a).reshape(-1)
    n_nan = int(np.isnan(a).sum())
    n_inf = int(np.isinf(a).sum())
    finite = a[np.isfinite(a)]
    if finite.size:
        print(f"[{name}] shape={a.shape} nan={n_nan} inf={n_inf} "
              f"min={finite.min():.4f} max={finite.max():.4f} "
              f"std={finite.std():.4f}")
    else:
        print(f"[{name}] shape={a.shape} ALL NON-FINITE (nan={n_nan} inf={n_inf})")
    return a


def write_wav(path, audio, sr=24000):
    a = np.nan_to_num(np.asarray(audio).reshape(-1), nan=0.0)
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    print(f"[wav] wrote {path} ({len(pcm)} samples @ {sr} Hz)")


def correlate(name_a, a, name_b, b):
    a = np.asarray(a).reshape(-1)
    b = np.asarray(b).reshape(-1)
    n = min(a.size, b.size)
    if a.size != b.size:
        print(f"[cmp] LENGTH MISMATCH {name_a}={a.size} {name_b}={b.size} "
              f"(comparing first {n})")
    a, b = a[:n], b[:n]
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() == 0:
        print(f"[cmp] no finite overlap — corr undefined")
        return
    a, b = a[mask], b[mask]
    max_abs = float(np.max(np.abs(a - b)))
    denom = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    corr = float(np.sum(a * b) / denom) if denom > 0 else 0.0
    print(f"[cmp] {name_a} vs {name_b}: max_abs={max_abs:.4e} corr={corr:.6f}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="patched ONNX model")
    ap.add_argument("--voices", required=True, help="voices NPZ")
    ap.add_argument("--voice", default="af_bella")
    ap.add_argument("--device", default="GPU", help="GPU / CPU / HETERO:GPU,CPU")
    ap.add_argument("--precision", default="f32", choices=["f32", "f16"],
                    help="INFERENCE_PRECISION_HINT (start with f32 on GPU)")
    ap.add_argument("--static", action="store_true",
                    help="reshape model to static input shapes before compile")
    ap.add_argument("--tokens", type=int, default=32)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--cache", default=None, help="OV cache dir")
    ap.add_argument("--profile", action="store_true",
                    help="enable per-op perf counters, print top 25 ops")
    ap.add_argument("--compare-ort", action="store_true",
                    help="also run ORT CPU on same feeds and correlate")
    ap.add_argument("--wav", default=None, help="write output wav here")
    args = ap.parse_args()

    import openvino as ov
    print(f"[ov] version: {ov.get_version()}")
    core = ov.Core()
    print(f"[ov] devices: {core.available_devices}")

    feeds = make_feeds(args)
    print(f"[feeds] tokens={feeds['tokens'].shape} "
          f"style={feeds['style'].shape} speed={feeds['speed']}")

    # ---- read + (optionally) freeze shapes ----
    t0 = time.time()
    model = core.read_model(args.model)
    print(f"[model] read in {time.time()-t0:.2f}s; inputs:")
    for inp in model.inputs:
        print(f"        {inp.any_name}: {inp.partial_shape} {inp.element_type}")

    if args.static:
        shapes = {
            "tokens": ov.PartialShape([1, args.tokens]),
            "style": ov.PartialShape([1, 256]),
            "speed": ov.PartialShape([1]),
        }
        # map by any_name so tensor-name variations still resolve
        reshape_map = {}
        for inp in model.inputs:
            for key, ps in shapes.items():
                if key in inp.get_names() or inp.any_name == key:
                    reshape_map[inp.any_name] = ps
        print(f"[model] reshaping to static: "
              f"{ {k: str(v) for k, v in reshape_map.items()} }")
        model.reshape(reshape_map)

    # ---- compile ----
    config = {
        "PERFORMANCE_HINT": "LATENCY",
        "INFERENCE_PRECISION_HINT": args.precision,
    }
    if args.cache:
        config["CACHE_DIR"] = args.cache
    if args.profile:
        config["PERF_COUNT"] = "YES"

    print(f"[compile] device={args.device} config={config}")
    t0 = time.time()
    try:
        compiled = core.compile_model(model, args.device, config)
    except Exception as e:
        print(f"COMPILE FAIL on {args.device}:\n{e}")
        sys.exit(4)
    print(f"[compile] OK in {time.time()-t0:.2f}s")
    try:
        print(f"[compile] execution devices: "
              f"{compiled.get_property('EXECUTION_DEVICES')}")
    except Exception:
        pass

    infer = compiled.create_infer_request()

    def one_run():
        t = time.time()
        result = infer.infer(feeds)
        dt = time.time() - t
        out = list(result.values())[0]
        return out, dt

    # ---- warmup + timed window ----
    for i in range(args.warmup):
        _, dt = one_run()
        print(f"[warmup {i}] {dt:.3f}s")

    print("=== INFER WINDOW START (watch intel_gpu_top now) ===")
    times, out = [], None
    for i in range(args.runs):
        out, dt = one_run()
        times.append(dt)
        print(f"[run {i}] {dt:.3f}s")
    print("=== INFER WINDOW END ===")
    print(f"[timing] mean={np.mean(times):.3f}s over {len(times)} runs")

    audio = audio_stats(f"OV {args.device} {args.precision}", out)

    if args.profile:
        try:
            prof = infer.get_profiling_info()
            prof = sorted(prof, key=lambda p: p.real_time.total_seconds(),
                          reverse=True)[:25]
            print("[profile] top ops by real time:")
            for p in prof:
                ms = p.real_time.total_seconds() * 1e3
                print(f"    {ms:9.3f} ms  {p.node_type:<20} "
                      f"{p.exec_type:<24} {p.node_name[:60]}")
        except Exception as e:
            print(f"[profile] unavailable: {e}")

    if args.compare_ort:
        try:
            import onnxruntime as ort
            so = ort.SessionOptions()
            so.log_severity_level = 3
            sess = ort.InferenceSession(args.model, sess_options=so,
                                        providers=["CPUExecutionProvider"])
            t = time.time()
            ref = sess.run(None, feeds)[0]
            print(f"[ort-cpu] ran in {time.time()-t:.3f}s")
            audio_stats("ORT CPU", ref)
            correlate(f"OV-{args.device}", audio, "ORT-CPU", ref)
        except Exception as e:
            print(f"[compare-ort] failed: {e}")

    if args.wav:
        write_wav(args.wav, audio)


if __name__ == "__main__":
    main()
