#!/usr/bin/env python3
"""S0.3 — offload proof for official GenAI Kokoro on GPU (not provider name alone)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np

MODEL = Path(
    os.environ.get(
        "S0_KOKORO_MODEL",
        "/data/intel-igpu-tts/spike/ov263-genai/out/kokoro-82M-int8-ov",
    )
)
OUT = Path(os.environ.get("S0_OUT", "/data/intel-igpu-tts/spike/ov263-genai/out"))
LOGS = Path(os.environ.get("S0_LOGS", "/data/intel-igpu-tts/spike/ov263-genai/logs"))
DEVICE = os.environ.get("S0_DEVICE", "GPU")
TEXT = os.environ.get(
    "S0_TEXT",
    "The quick brown fox jumps over the lazy dog.",
)
VOICE = os.environ.get("S0_VOICE", "af_heart")
SR = 24000

try:
    import espeakng_loader

    os.environ.setdefault("MISAKI_ESPEAK_LIBRARY", espeakng_loader.get_library_path())
    os.environ.setdefault("ESPEAK_DATA_PATH", espeakng_loader.get_data_path())
except Exception as e:
    print("espeakng_loader skip:", e, flush=True)

result: dict = {
    "gate": "S0.3",
    "model_path": str(MODEL),
    "device_request": DEVICE,
    "text": TEXT,
    "voice": VOICE,
}


def main() -> int:
    import openvino as ov
    import openvino_genai as og

    result["openvino"] = ov.__version__
    result["openvino_genai"] = getattr(og, "__version__", "unknown")
    core = ov.Core()
    result["available_devices"] = list(core.available_devices)
    print("devices", result["available_devices"], flush=True)

    # --- A: direct IR compile props (secondary, same weights) ---
    xml = MODEL / "openvino_model.xml"
    try:
        t0 = time.time()
        model = core.read_model(xml)
        # Prefer f32 compute hint like notebook GPU path (int8 weights still)
        cfg = {}
        try:
            cfg["INFERENCE_PRECISION_HINT"] = "f32"
        except Exception:
            pass
        # CACHE_DIR for faster repeat
        cache_dir = str(OUT / "ov_cache_s0")
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        cfg["CACHE_DIR"] = cache_dir
        compiled = core.compile_model(model, DEVICE, cfg)
        result["direct_compile_s"] = round(time.time() - t0, 3)
        props = {}
        for key in (
            "EXECUTION_DEVICES",
            "SUPPORTED_PROPERTIES",
            "INFERENCE_PRECISION_HINT",
            "OPTIMAL_NUMBER_OF_INFER_REQUESTS",
        ):
            try:
                props[key] = _jsonable(compiled.get_property(key))
            except Exception as e:
                props[key] = f"err:{type(e).__name__}"
        # try more property names if SUPPORTED lists them
        try:
            supported = compiled.get_property("SUPPORTED_PROPERTIES")
            for p in list(supported)[:40]:
                name = str(p)
                if name in props:
                    continue
                if any(
                    k in name.upper()
                    for k in ("EXEC", "DEVICE", "PRECISION", "PERF")
                ):
                    try:
                        props[name] = _jsonable(compiled.get_property(p))
                    except Exception:
                        pass
        except Exception:
            pass
        result["direct_compile_props"] = props
        print("DIRECT_COMPILE props", json.dumps(props, default=str)[:800], flush=True)
    except Exception as e:
        result["direct_compile_error"] = f"{type(e).__name__}: {e}"
        result["direct_compile_tb"] = traceback.format_exc()
        print("DIRECT_COMPILE_FAIL", result["direct_compile_error"], flush=True)

    # --- B: GenAI pipeline generate under intel_gpu_top ---
    gpu_json = LOGS / "s0_3_intel_gpu_top.json"
    gpu_err = LOGS / "s0_3_intel_gpu_top.err"
    LOGS.mkdir(parents=True, exist_ok=True)
    for p in (gpu_json, gpu_err):
        if p.exists():
            p.unlink()

    # idle sample ~3s
    idle_proc = _start_igt(gpu_json, gpu_err)
    time.sleep(3.5)
    idle_stats = _parse_igt_stats(gpu_json)
    result["gpu_idle"] = idle_stats
    print("GPU_IDLE", idle_stats, flush=True)
    _stop_igt(idle_proc)

    # fresh file for generate window
    if gpu_json.exists():
        gpu_json.unlink()
    gen_proc = _start_igt(gpu_json, gpu_err)
    time.sleep(1.0)  # let igt start

    t_load0 = time.time()
    pipe = og.Text2SpeechPipeline(str(MODEL), DEVICE)
    result["genai_load_s"] = round(time.time() - t_load0, 3)
    print("GENAI_LOAD", result["genai_load_s"], flush=True)

    shape = tuple(pipe.get_speaker_embedding_shape())
    voice_bin = MODEL / "voices" / f"{VOICE}.bin"
    emb = np.fromfile(voice_bin, dtype=np.float32)
    speaker = ov.Tensor(emb.reshape(shape))
    result["speaker_embedding_shape"] = list(shape)

    t_gen0 = time.time()
    gen = pipe.generate(TEXT, speaker, language="en-us")
    result["generate_s"] = round(time.time() - t_gen0, 3)
    speech = gen.speeches[0]
    audio = np.array(speech.data, dtype=np.float32).reshape(-1)
    result["audio_s"] = float(audio.size / getattr(gen, "output_sample_rate", SR))
    result["peak_abs"] = float(np.max(np.abs(audio))) if audio.size else 0.0
    result["generate_ok"] = audio.size > 0 and result["peak_abs"] >= 1e-4
    print(
        f"GENERATE wall={result['generate_s']}s audio={result['audio_s']:.2f}s "
        f"peak={result['peak_abs']:.4f}",
        flush=True,
    )

    time.sleep(1.2)  # catch trailing samples
    _stop_igt(gen_proc)
    gen_stats = _parse_igt_stats(gpu_json)
    result["gpu_during_generate"] = gen_stats
    print("GPU_DURING_GENERATE", gen_stats, flush=True)

    # --- verdict ---
    exec_devs = str(result.get("direct_compile_props", {}).get("EXECUTION_DEVICES", ""))
    gpu_in_exec = "GPU" in exec_devs.upper()
    rcs_max = float(gen_stats.get("rcs_max") or 0)
    rcs_mean = float(gen_stats.get("rcs_mean") or 0)
    idle_max = float(idle_stats.get("rcs_max") or 0)
    # PASS if EXECUTION_DEVICES shows GPU OR strong RCS activity during generate
    # notes/44 fingerprint: real offload pegged ~98-100% RCS under load
    strong_top = rcs_max >= 50.0 and rcs_max > idle_max + 10.0
    moderate_top = rcs_mean >= 15.0 and rcs_max >= 30.0
    offload_ok = bool(gpu_in_exec or strong_top or moderate_top)
    silent_cpu = (not gpu_in_exec) and rcs_max < 5.0 and result["generate_ok"]

    result["evidence"] = {
        "execution_devices_has_gpu": gpu_in_exec,
        "execution_devices": exec_devs,
        "igt_rcs_max_during_gen": rcs_max,
        "igt_rcs_mean_during_gen": rcs_mean,
        "igt_rcs_max_idle": idle_max,
        "strong_top_match_note44_class": strong_top,
        "moderate_top": moderate_top,
    }
    if silent_cpu:
        result["s0_3_verdict"] = "KILL"
        result["verdict_reason"] = "generate_ok_but_no_gpu_exec_evidence_silent_cpu_class"
    elif offload_ok:
        result["s0_3_verdict"] = "PASS"
        result["verdict_reason"] = (
            "execution_devices_gpu"
            if gpu_in_exec
            else "intel_gpu_top_rcs_activity"
        )
    else:
        result["s0_3_verdict"] = "INCONCLUSIVE"
        result["verdict_reason"] = "weak_or_missing_offload_evidence"

    _write(result)
    print("VERDICT", result["s0_3_verdict"], result["verdict_reason"], flush=True)
    return 0 if result["s0_3_verdict"] == "PASS" else 1


def _start_igt(out_path: Path, err_path: Path):
    # needs sudo on this host (assert without)
    cmd = [
        "sudo",
        "intel_gpu_top",
        "-J",
        "-s",
        "500",
        "-o",
        str(out_path),
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=open(err_path, "w"),
    )


def _stop_igt(proc) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass
    # ensure no stray
    subprocess.run(
        ["sudo", "kill", str(proc.pid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _parse_igt_stats(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {"samples": 0, "rcs_max": 0.0, "rcs_mean": 0.0, "gpu_max_max": 0.0}
    text = path.read_text(errors="replace").strip()
    if text.startswith("["):
        text = text[1:]
    dec = json.JSONDecoder()
    idx = 0
    rcs_vals = []
    gmax_vals = []
    while idx < len(text):
        while idx < len(text) and text[idx] in " \n\r\t,":
            idx += 1
        if idx >= len(text) or text[idx] == "]":
            break
        try:
            obj, off = dec.raw_decode(text, idx)
            idx = off
        except Exception:
            break
        engines = obj.get("engines") or {}
        vals = []
        rcs = None

        def add(name, busy):
            nonlocal rcs
            if busy is None:
                return
            try:
                b = float(busy)
            except Exception:
                return
            if b <= 1.0:
                b *= 100.0
            vals.append(b)
            n = str(name).lower()
            if "render" in n or n.startswith("rcs"):
                rcs = b

        if isinstance(engines, dict):
            for k, v in engines.items():
                if isinstance(v, dict):
                    add(k, v.get("busy", v.get("load")))
                else:
                    add(k, v)
        elif isinstance(engines, list):
            for e in engines:
                add(e.get("name") or e.get("class") or "", e.get("busy", e.get("load")))
        if rcs is not None:
            rcs_vals.append(rcs)
        if vals:
            gmax_vals.append(max(vals))
    def st(xs):
        if not xs:
            return 0.0, 0.0
        return max(xs), sum(xs) / len(xs)

    rmax, rmean = st(rcs_vals)
    gmax, gmean = st(gmax_vals)
    return {
        "samples": len(gmax_vals),
        "rcs_max": round(rmax, 2),
        "rcs_mean": round(rmean, 2),
        "gpu_max_max": round(gmax, 2),
        "gpu_max_mean": round(gmean, 2),
    }


def _jsonable(x):
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, (list, tuple)):
        return [_jsonable(i) for i in x]
    try:
        return str(x)
    except Exception:
        return repr(x)


def _write(obj: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "s0_3_result.json"
    p.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print("WROTE", p, flush=True)


if __name__ == "__main__":
    sys.exit(main())
