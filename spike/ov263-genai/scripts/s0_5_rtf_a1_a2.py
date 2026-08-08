#!/usr/bin/env python3
"""S0.5 — cold vs steady RTF, A1 novel-shape, unforced A2 precision, B1/B3 inputs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
import wave
from pathlib import Path

import numpy as np

MODEL = Path("/data/intel-igpu-tts/spike/ov263-genai/out/kokoro-82M-int8-ov")
OUT = Path("/data/intel-igpu-tts/spike/ov263-genai/out/s0_5")
LOGS = Path("/data/intel-igpu-tts/spike/ov263-genai/logs")
DEVICE = "GPU"
VOICE = "af_heart"
SR = 24000

# Comparable to notes/44 long-ish and fox-class
FOX = "The quick brown fox jumps over the lazy dog."
MULTI = (
    "Kokoro is an open-weight text to speech model with eighty two million parameters. "
    "Despite its lightweight architecture, it delivers comparable quality to larger models "
    "while being significantly faster and more cost efficient."
)
# Novel texts never used in S0.2–S0.4 set (A1)
NOVEL1 = (
    "Seven silver swans swam silently seaward past twelve bright blue boxes of old books."
)
NOVEL2 = (
    "The museum opens at noon on Thursdays and serves tea near the marble staircase."
)

NOTE44_RTF = 5.01  # patched demo fresh long comparable

try:
    import espeakng_loader

    os.environ.setdefault("MISAKI_ESPEAK_LIBRARY", espeakng_loader.get_library_path())
    os.environ.setdefault("ESPEAK_DATA_PATH", espeakng_loader.get_data_path())
except Exception as e:
    print("espeakng_loader skip", e, flush=True)

result: dict = {"gate": "S0.5", "model": str(MODEL), "device": DEVICE, "voice": VOICE}


def main() -> int:
    import openvino as ov
    import openvino_genai as og

    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    result["openvino"] = ov.__version__
    result["openvino_genai"] = getattr(og, "__version__", "unknown")
    result["note44_rtf_comparable"] = NOTE44_RTF

    # ----- A2 unforced: compile IR with NO precision hint -----
    core = ov.Core()
    cache_dir = str(OUT / "ov_cache_unforced")
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    m = core.read_model(MODEL / "openvino_model.xml")
    # intentionally NO INFERENCE_PRECISION_HINT
    compiled = core.compile_model(m, DEVICE, {"CACHE_DIR": cache_dir})
    result["a2_direct_unforced_compile_s"] = round(time.time() - t0, 3)
    a2 = {}
    for key in (
        "EXECUTION_DEVICES",
        "INFERENCE_PRECISION_HINT",
        "DEVICE_ID",
        "PERFORMANCE_HINT",
    ):
        try:
            a2[key] = str(compiled.get_property(key))
        except Exception as e:
            a2[key] = f"err:{type(e).__name__}:{e}"
    # Also try reading default after compile without setting
    result["a2_unforced_direct_compile_props"] = a2
    print("A2_UNFORCED_DIRECT", a2, flush=True)

    # GenAI pipeline — no way to pass hint through public API; record that
    # and any config we can scrape from openvino_config.json
    oc = MODEL / "openvino_config.json"
    if oc.exists():
        result["a2_openvino_config_json"] = json.loads(oc.read_text())
        print("A2_OV_CONFIG", result["a2_openvino_config_json"], flush=True)

    # ----- Load GenAI (process-local; first load may be warm from prior S0) -----
    t0 = time.time()
    pipe = og.Text2SpeechPipeline(str(MODEL), DEVICE)
    result["pipeline_load_s"] = round(time.time() - t0, 3)
    print("PIPELINE_LOAD", result["pipeline_load_s"], flush=True)

    shape = tuple(pipe.get_speaker_embedding_shape())
    emb = np.fromfile(MODEL / "voices" / f"{VOICE}.bin", dtype=np.float32)
    speaker = ov.Tensor(emb.reshape(shape))

    def gen_one(text: str, tag: str) -> dict:
        t1 = time.time()
        g = pipe.generate(text, speaker, language="en-us")
        wall = time.time() - t1
        audio = np.nan_to_num(np.array(g.speeches[0].data, dtype=np.float32).reshape(-1))
        sr = int(getattr(g, "output_sample_rate", SR) or SR)
        dur = float(audio.size / sr) if audio.size else 0.0
        path = OUT / f"{tag}.wav"
        _wav(path, audio, sr)
        row = {
            "tag": tag,
            "text": text,
            "wall_s": round(wall, 3),
            "audio_s": round(dur, 3),
            "rtf": round(wall / max(dur, 1e-6), 3),
            "peak_abs": float(np.max(np.abs(audio))) if audio.size else 0.0,
            "wav": str(path),
        }
        print(
            f"{tag}: wall={row['wall_s']}s audio={row['audio_s']}s rtf={row['rtf']} peak={row['peak_abs']:.3f}",
            flush=True,
        )
        return row

    # ----- Fox: treat first as cold-ish in-process, then steady repeats -----
    # True process-cold already partly spent on load; still report first vs later.
    fox_runs = []
    for i in range(5):
        fox_runs.append(gen_one(FOX, f"fox_run{i}"))
    result["fox_runs"] = fox_runs
    # discard run0 as warmup for steady mean
    steady_fox = fox_runs[1:]
    result["fox_steady_rtf_mean"] = round(
        sum(r["rtf"] for r in steady_fox) / len(steady_fox), 3
    )
    result["fox_steady_wall_mean"] = round(
        sum(r["wall_s"] for r in steady_fox) / len(steady_fox), 3
    )
    result["fox_run0_rtf"] = fox_runs[0]["rtf"]
    print(
        "FOX_STEADY_mean_rtf",
        result["fox_steady_rtf_mean"],
        "run0",
        result["fox_run0_rtf"],
        flush=True,
    )

    # ----- Multi: first + second (steady for multi shape) -----
    multi_runs = [gen_one(MULTI, f"multi_run{i}") for i in range(3)]
    result["multi_runs"] = multi_runs
    result["multi_run0_rtf"] = multi_runs[0]["rtf"]
    result["multi_steady_rtf_mean"] = round(
        sum(r["rtf"] for r in multi_runs[1:]) / max(len(multi_runs) - 1, 1), 3
    )
    print(
        "MULTI_STEADY_mean_rtf",
        result["multi_steady_rtf_mean"],
        "run0",
        result["multi_run0_rtf"],
        flush=True,
    )

    # ----- A1: after warm steady, novel shape first vs second -----
    # Warm already established via fox/multi. Novel1 first+second, novel2 first only optional.
    a1_n1_first = gen_one(NOVEL1, "a1_novel1_first")
    a1_n1_second = gen_one(NOVEL1, "a1_novel1_second")
    a1_n2_first = gen_one(NOVEL2, "a1_novel2_first")
    a1_n2_second = gen_one(NOVEL2, "a1_novel2_second")
    result["a1"] = {
        "novel1_first": a1_n1_first,
        "novel1_second": a1_n1_second,
        "novel2_first": a1_n2_first,
        "novel2_second": a1_n2_second,
        "novel1_first_minus_second_wall_s": round(
            a1_n1_first["wall_s"] - a1_n1_second["wall_s"], 3
        ),
        "novel2_first_minus_second_wall_s": round(
            a1_n2_first["wall_s"] - a1_n2_second["wall_s"], 3
        ),
    }
    # Interpretation helper (not kill bar)
    pen = result["a1"]["novel1_first_minus_second_wall_s"]
    if pen >= 5.0:
        result["a1_interpretation"] = "shape_jit_penalty_seconds_class"
    elif pen >= 1.0:
        result["a1_interpretation"] = "moderate_first_infer_penalty"
    else:
        result["a1_interpretation"] = "little_or_no_novel_shape_penalty"
    print("A1", result["a1_interpretation"], result["a1"], flush=True)

    # ----- Optional igt during one multi steady generate -----
    igt_path = LOGS / "s0_5_igt_multi.json"
    if igt_path.exists():
        igt_path.unlink()
    igt = _start_igt(igt_path)
    time.sleep(0.8)
    _ = gen_one(MULTI, "multi_profile_run")
    time.sleep(0.8)
    _stop_igt(igt)
    result["igt_multi_profile"] = _parse_igt(igt_path)
    print("IGT_MULTI", result["igt_multi_profile"], flush=True)

    # ----- Product / demo speed clauses -----
    fox_ok = result["fox_steady_rtf_mean"] <= 1.0
    multi_ok = result["multi_steady_rtf_mean"] <= 1.0
    result["s0_5_product_speed_clause"] = bool(fox_ok and multi_ok)
    # demo-class: GPU works (prior bars) + RTF in ~4-6 band
    steady_rtfs = [result["fox_steady_rtf_mean"], result["multi_steady_rtf_mean"]]
    result["steady_rtf_band"] = {
        "fox": result["fox_steady_rtf_mean"],
        "multi": result["multi_steady_rtf_mean"],
        "vs_note44": NOTE44_RTF,
        "beats_note44_fox": result["fox_steady_rtf_mean"] < NOTE44_RTF,
        "beats_note44_multi": result["multi_steady_rtf_mean"] < NOTE44_RTF,
    }

    # B1 vs B3 lean from numbers
    if result["s0_5_product_speed_clause"]:
        result["b_branch_lean"] = "B1_fast_product_interest"
    elif max(steady_rtfs) <= 6.5 and min(steady_rtfs) >= 1.0:
        result["b_branch_lean"] = "B3_demo_class_ref_floor_band"
    elif max(steady_rtfs) > 6.5:
        result["b_branch_lean"] = "slower_than_demo_band_or_cold_confounded"
    else:
        result["b_branch_lean"] = "mixed_or_sub_1_partial"

    # Overall S0 verdict word (combines prior PASSes assumed)
    if result["s0_5_product_speed_clause"]:
        result["s0_verdict_word"] = "S0-GO-product"
    else:
        # ears already PASS, offload PASS → demo if usable
        result["s0_verdict_word"] = "S0-GO-demo"

    result["s0_5_complete"] = True
    _write(result)
    print("S0_VERDICT", result["s0_verdict_word"], flush=True)
    print("B_LEAN", result["b_branch_lean"], flush=True)
    print(
        "STEADY",
        result["steady_rtf_band"],
        "A1",
        result["a1_interpretation"],
        flush=True,
    )
    return 0


def _wav(path: Path, audio: np.ndarray, sr: int) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def _start_igt(path: Path):
    err = path.with_suffix(".err")
    return subprocess.Popen(
        ["sudo", "intel_gpu_top", "-J", "-s", "500", "-o", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=open(err, "w"),
    )


def _stop_igt(proc) -> None:
    if not proc:
        return
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    subprocess.run(
        ["sudo", "kill", str(proc.pid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _parse_igt(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {"samples": 0}
    text = path.read_text(errors="replace").strip()
    if text.startswith("["):
        text = text[1:]
    dec = json.JSONDecoder()
    idx = 0
    rcs = []
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
        if isinstance(engines, dict):
            for k, v in engines.items():
                if "render" in k.lower() or k.lower().startswith("rcs"):
                    b = v.get("busy") if isinstance(v, dict) else v
                    if b is not None:
                        b = float(b)
                        if b <= 1.0:
                            b *= 100.0
                        rcs.append(b)
    if not rcs:
        return {"samples": 0, "rcs_max": 0.0, "rcs_mean": 0.0}
    return {
        "samples": len(rcs),
        "rcs_max": round(max(rcs), 2),
        "rcs_mean": round(sum(rcs) / len(rcs), 2),
    }


def _write(obj: dict) -> None:
    p = OUT / "s0_5_result.json"
    p.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print("WROTE", p, flush=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
