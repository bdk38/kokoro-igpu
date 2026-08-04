#!/usr/bin/env python3
"""
Phase 4 spike: load kokoro-v0_19.onnx with ONNX Runtime OpenVINO EP.

Goals:
  1) Confirm OpenVINOExecutionProvider is available and selected
  2) Create an InferenceSession against the staged Kokoro ONNX
  3) Run a minimal dummy forward (or fail clearly on op/provider issues)
  4) Log timings so intel_gpu_top can be correlated manually

This does NOT yet do full text->phoneme->audio Kokoro pipeline quality.
It answers: can the graph load and execute via OpenVINO on this host?
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np


ROOT = Path(os.environ.get("INTEL_IGPU_TTS_ROOT", "/data/intel-igpu-tts"))
DEFAULT_MODEL = ROOT / "models" / "kokoro-v0_19.onnx"
DEFAULT_VOICES = ROOT / "models" / "voices-v1.0.bin"
DEFAULT_CACHE = ROOT / "cache" / "openvino"
DEFAULT_OUTDIR = ROOT / "artifacts"


def log(msg: str) -> None:
    print(msg, flush=True)


def build_providers(device: str, precision: str, cache_dir: Path) -> list:
    """Return ORT providers list. device: GPU|CPU|AUTO"""
    cache_dir.mkdir(parents=True, exist_ok=True)

    prec = precision.lower()
    if prec in {"fp16", "f16"}:
        hint = "f16"
    elif prec in {"fp32", "f32"}:
        hint = "f32"
    else:
        hint = "f16"

    cfg_device = device if device != "AUTO" else "GPU"
    load_config = {
        cfg_device: {
            "INFERENCE_PRECISION_HINT": hint,
            "PERFORMANCE_HINT": "LATENCY",
            "CACHE_DIR": str(cache_dir),
        }
    }

    ov_opts = {
        "device_type": device,
        "cache_dir": str(cache_dir),
        "load_config": json.dumps(load_config),
    }

    return [
        ("OpenVINOExecutionProvider", ov_opts),
        "CPUExecutionProvider",
    ]


def inspect_session(sess) -> None:
    log(f"session providers: {sess.get_providers()}")
    inputs = sess.get_inputs()
    outputs = sess.get_outputs()
    log(f"inputs ({len(inputs)}):")
    for i in inputs:
        log(f"  - {i.name}: shape={i.shape} type={i.type}")
    log(f"outputs ({len(outputs)}):")
    for o in outputs:
        log(f"  - {o.name}: shape={o.shape} type={o.type}")


def load_voice_style(
    voices_path: Path, voice_name: str = "af_bella", token_len: int = 32
) -> np.ndarray:
    """
    voices-v1.0.bin is an NPZ pack used by kokoro-onnx.
    Each voice is typically (510, 1, 256); kokoro selects style[min(len, 509)].
    Return shape (1, 256) float32 for the ONNX style input.
    """
    try:
        data = np.load(voices_path, allow_pickle=True)
        if hasattr(data, "files"):
            keys = list(data.files)
            log(
                f"voices archive keys ({len(keys)}): "
                f"{keys[:12]}{'...' if len(keys) > 12 else ''}"
            )
            key = voice_name if voice_name in keys else keys[0]
            raw = np.array(data[key], dtype=np.float32)
            log(f"using voice key={key} raw_shape={raw.shape} dtype={raw.dtype}")
            if raw.ndim == 3 and raw.shape[-1] == 256:
                idx = min(max(token_len, 0), raw.shape[0] - 1)
                style = raw[idx].reshape(1, 256)
            elif raw.ndim == 2 and raw.shape[-1] == 256:
                idx = min(max(token_len, 0), raw.shape[0] - 1)
                style = raw[idx].reshape(1, 256)
            elif raw.ndim == 1:
                style = raw.reshape(1, -1)
            else:
                style = raw.reshape(1, -1)[:, :256]
            log(f"style_shape={style.shape}")
            return style.astype(np.float32)
    except Exception as exc:  # noqa: BLE001
        log(f"voices np.load failed: {exc}")

    log("WARNING: falling back to zeros style vector (1, 256)")
    return np.zeros((1, 256), dtype=np.float32)


def make_dummy_input_ids(length: int = 32) -> np.ndarray:
    """Minimal token row. Real phoneme IDs not required for graph load smoke."""
    ids = np.zeros((1, length), dtype=np.int64)
    ids[0, 1 : length - 1] = np.arange(1, length - 1, dtype=np.int64) % 50 + 1
    return ids


def write_wav(path: Path, audio: np.ndarray, sample_rate: int = 24000) -> None:
    audio = np.asarray(audio).reshape(-1)
    if np.issubdtype(audio.dtype, np.floating):
        peak = float(np.max(np.abs(audio))) or 1.0
        audio = np.clip(audio / max(peak, 1.0), -1.0, 1.0)
        pcm = (audio * 32767.0).astype(np.int16)
    else:
        pcm = audio.astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    log(f"wrote wav: {path} samples={pcm.shape[0]} sr={sample_rate}")


def map_feeds(sess, style: np.ndarray, speed: float, token_len: int) -> dict:
    feeds = {}
    for inp in sess.get_inputs():
        name = inp.name
        shape = inp.shape
        typ = inp.type or ""
        lname = name.lower()
        if any(k in lname for k in ("input_ids", "tokens", "token", "text")):
            length = token_len
            if len(shape) >= 2 and isinstance(shape[1], int) and shape[1] > 0:
                length = shape[1]
            feeds[name] = make_dummy_input_ids(length)
        elif any(k in lname for k in ("style", "ref", "speaker", "voice")):
            arr = style
            if (
                len(shape) >= 2
                and isinstance(shape[-1], int)
                and shape[-1] > 0
                and arr.shape[-1] != shape[-1]
            ):
                log(
                    f"style dim mismatch for {name}: have {arr.shape}, "
                    f"want *x{shape[-1]}; padding/truncating"
                )
                target = shape[-1]
                flat = arr.reshape(-1)
                if flat.size < target:
                    flat = np.pad(flat, (0, target - flat.size))
                arr = flat[:target].reshape(1, target).astype(np.float32)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            feeds[name] = arr.astype(np.float32)
        elif "speed" in lname:
            feeds[name] = np.array([speed], dtype=np.float32)
        else:
            if "int64" in typ:
                feeds[name] = make_dummy_input_ids(token_len)
            elif "int32" in typ:
                feeds[name] = make_dummy_input_ids(token_len).astype(np.int32)
            else:
                dims = []
                for d in shape:
                    if isinstance(d, int) and d > 0:
                        dims.append(d)
                    else:
                        dims.append(1)
                if not dims:
                    dims = [1]
                feeds[name] = np.zeros(dims, dtype=np.float32)
                log(f"WARNING: generic zero feed for input {name} shape={shape}")
    return feeds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--voices", type=Path, default=DEFAULT_VOICES)
    ap.add_argument(
        "--device",
        default=os.environ.get("OV_DEVICE", "GPU"),
        choices=["GPU", "CPU", "AUTO"],
    )
    ap.add_argument("--precision", default=os.environ.get("OV_PRECISION", "FP16"))
    ap.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.environ.get("OV_CACHE_DIR", DEFAULT_CACHE)),
    )
    ap.add_argument("--voice", default="af_bella")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--token-len", type=int, default=32)
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument(
        "--cpu-only",
        action="store_true",
        help="Force CPUExecutionProvider only (baseline)",
    )
    args = ap.parse_args()

    log(f"model={args.model}")
    log(f"voices={args.voices}")
    log(
        f"device={args.device} precision={args.precision} cache={args.cache_dir}"
    )
    if not args.model.is_file():
        log(f"FAIL: model not found: {args.model}")
        return 2

    import onnxruntime as ort

    log(f"onnxruntime={ort.__version__}")
    log(f"available_providers={ort.get_available_providers()}")

    so = ort.SessionOptions()
    so.log_severity_level = 2  # warning+

    if args.cpu_only:
        providers = ["CPUExecutionProvider"]
    else:
        if "OpenVINOExecutionProvider" not in ort.get_available_providers():
            log("FAIL: OpenVINOExecutionProvider not in available_providers")
            return 3
        providers = build_providers(args.device, args.precision, args.cache_dir)

    if args.cpu_only:
        log("requested_providers=['CPUExecutionProvider']")
    else:
        log(f"requested_providers={[providers[0][0], providers[1]]}")
        log(f"provider_options={providers[0][1]}")

    t0 = time.perf_counter()
    try:
        sess = ort.InferenceSession(str(args.model), so, providers=providers)
    except Exception as exc:  # noqa: BLE001
        log(f"FAIL: InferenceSession create: {type(exc).__name__}: {exc}")
        return 4
    t1 = time.perf_counter()
    log(f"session_create_s={t1 - t0:.3f}")
    inspect_session(sess)

    active = sess.get_providers()
    if not args.cpu_only and active and active[0] != "OpenVINOExecutionProvider":
        log(
            f"WARN: primary provider is {active[0]}, "
            "not OpenVINOExecutionProvider (possible fallback)"
        )

    style = load_voice_style(args.voices, args.voice, args.token_len)
    feeds = map_feeds(sess, style, args.speed, args.token_len)
    log("feed summary:")
    for k, v in feeds.items():
        log(
            f"  {k}: shape={getattr(v, 'shape', None)} "
            f"dtype={getattr(v, 'dtype', None)}"
        )

    log("=== INFER WINDOW START (watch intel_gpu_top now) ===")
    try:
        for i in range(max(0, args.warmup)):
            tw0 = time.perf_counter()
            _ = sess.run(None, feeds)
            log(f"warmup[{i}]_s={time.perf_counter() - tw0:.3f}")

        outs = None
        times = []
        for i in range(max(1, args.runs)):
            tr0 = time.perf_counter()
            outs = sess.run(None, feeds)
            dt = time.perf_counter() - tr0
            times.append(dt)
            log(f"run[{i}]_s={dt:.3f}")
    except Exception as exc:  # noqa: BLE001
        log(f"FAIL: sess.run: {type(exc).__name__}: {exc}")
        log("=== INFER WINDOW END ===")
        return 5
    log("=== INFER WINDOW END ===")

    if outs:
        for idx, arr in enumerate(outs):
            a = np.asarray(arr)
            amin = a.min() if a.size else "n/a"
            amax = a.max() if a.size else "n/a"
            log(
                f"output[{idx}]: shape={a.shape} dtype={a.dtype} "
                f"min={amin} max={amax}"
            )
        audio = np.asarray(outs[0])
        if audio.ndim >= 1 and audio.size > 100:
            out_wav = args.outdir / f"kokoro_ov_{args.device.lower()}_dummy.wav"
            try:
                write_wav(out_wav, audio.reshape(-1), 24000)
            except Exception as exc:  # noqa: BLE001
                log(f"wav write skipped: {exc}")

    log(f"OK: mean_run_s={sum(times)/len(times):.3f} n={len(times)}")
    log(f"final_providers={sess.get_providers()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
