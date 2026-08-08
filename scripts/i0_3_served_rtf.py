#!/usr/bin/env python3
"""I0.3 — served RTF matrix for ovgenai-gpu through real HTTP API.

Methodology (named):
  - Backend: ovgenai-gpu, ship venv 2026.3+GenAI, pack models/kokoro-82M-int8-ov
  - Path: POST /v1/audio/speech (not direct GenAI)
  - TTS cache OFF (measure synth+server assembly, not C1 hit)
  - Warm: KOKORO_WARM_TEXT = chunk-shaped pins (Fable F4 notes/61), plus
    discard first timed run per shape before steady mean
  - Steady RTF = mean(wall/audio) after discard; bar ≤ 1.0 fox and multi
  - Novel tax: one new text after warm, first vs second wall
  - Report-only: 1-chunk vs N-chunk same total text (G3 notes/54)
  - Daily :8880 left alone; this probe uses :8893

Exit 0 if fox+multi steady RTF ≤ 1.0; else 1.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path("/data/intel-igpu-tts")
VENV_PY = ROOT / "venv/bin/python"
SERVER = ROOT / "scripts/kokoro_server.py"
OUT = ROOT / "artifacts/i0_3"
LOG = OUT / "server.log"
PORT = int(os.environ.get("I0_3_PORT", "8893"))
BASE = f"http://127.0.0.1:{PORT}"
VOICE = "af_bella"
SR = 24000

# Chunk-shaped warm pins (F4): fox-class + two multi pieces similar to chunker output
FOX = "The quick brown fox jumps over the lazy dog."
MULTI_A = (
    "Kokoro is an open-weight text to speech model with eighty two million parameters. "
    "Despite its lightweight architecture, it delivers comparable quality to larger models "
    "while being significantly faster and more cost efficient."
)
MULTI_B = (
    "This multi-sentence passage is for served RTF evaluation of the official OpenVINO path."
)
MULTI = MULTI_A + " " + MULTI_B

# Novel texts (not in warm set)
NOVEL = (
    "Seven silver swans swam silently past bright blue boxes near the old museum."
)

# Report-only overhead: same total text as one blob vs forced short sentences
OVERHEAD_ONE = (
    "Alpha one. Bravo two. Charlie three. Delta four. Echo five."
)
# Natural short sentences → multiple chunks under soft budget
OVERHEAD_MANY = OVERHEAD_ONE  # same string; chunker decides N from punctuation

WARM_TEXT = "|".join([FOX, MULTI_A, MULTI_B])


def http_json(method: str, url: str, body: dict | None = None, timeout: float = 600.0):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        return resp.status, raw, hdrs


def wav_duration(wav_bytes: bytes) -> float:
    import io

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def speech(text: str, tag: str, speed: float = 1.0) -> dict:
    t0 = time.time()
    status, raw, hdrs = http_json(
        "POST",
        f"{BASE}/v1/audio/speech",
        {
            "input": text,
            "voice": VOICE,
            "response_format": "wav",
            "speed": speed,
        },
        timeout=900.0,
    )
    wall = time.time() - t0
    if status != 200:
        raise RuntimeError(f"{tag} HTTP {status}")
    path = OUT / f"{tag}.wav"
    path.write_bytes(raw)
    audio_s = wav_duration(raw)
    rtf = wall / max(audio_s, 1e-6)
    row = {
        "tag": tag,
        "wall_s": round(wall, 3),
        "audio_s": round(audio_s, 3),
        "rtf": round(rtf, 4),
        "bytes": len(raw),
        "x_backend": hdrs.get("x-kokoro-backend"),
        "x_rtf": hdrs.get("x-kokoro-rtf"),
        "x_cache": hdrs.get("x-kokoro-cache"),
        "path": str(path),
    }
    print(
        f"[{tag}] wall={row['wall_s']:.2f}s audio={row['audio_s']:.2f}s "
        f"rtf={row['rtf']:.3f} cache={row['x_cache']}",
        flush=True,
    )
    return row


def wait_health(timeout: float = 180.0) -> dict:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        try:
            st, raw, _ = http_json("GET", f"{BASE}/health", timeout=5.0)
            if st == 200:
                return json.loads(raw.decode())
        except Exception as e:
            last = e
        time.sleep(1.0)
    raise RuntimeError(f"health timeout: {last}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    result: dict = {
        "gate": "I0.3",
        "port": PORT,
        "voice": VOICE,
        "methodology": {
            "path": "POST /v1/audio/speech",
            "backend": "ovgenai-gpu",
            "tts_cache": "0",
            "warm": "KOKORO_WARM_TEXT chunk-shaped + discard first timed run/shape",
            "steady": "mean of runs after discard",
            "bar": "steady RTF <= 1.0 fox and multi",
            "fable_pred_fox": "<= 0.85",
        },
        "runs": [],
    }

    env = os.environ.copy()
    env.update(
        {
            "KOKORO_BACKEND": "ovgenai-gpu",
            "KOKORO_GENAI_MODEL": str(ROOT / "models/kokoro-82M-int8-ov"),
            "KOKORO_TTS_CACHE": "0",
            "KOKORO_DEFAULT_VOICE": VOICE,
            "KOKORO_WARM_TEXT": WARM_TEXT,
        }
    )

    # Ensure port free
    try:
        http_json("GET", f"{BASE}/health", timeout=1.0)
        print("ERROR: port already in use", PORT, flush=True)
        return 2
    except Exception:
        pass

    logf = open(LOG, "w")
    proc = subprocess.Popen(
        [str(VENV_PY), str(SERVER), "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT),
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    result["server_pid"] = proc.pid
    print(f"started pid={proc.pid} port={PORT}", flush=True)

    try:
        health = wait_health(240.0)
        result["health"] = health
        print("health", health, flush=True)
        if health.get("backend") != "ovgenai-gpu":
            raise RuntimeError(f"wrong backend {health}")

        # Stack identity (A3-ish)
        import openvino as ov
        import openvino_genai as og

        result["stack"] = {
            "openvino": ov.__version__,
            "openvino_genai": getattr(og, "__version__", "unknown"),
            "devices": list(ov.Core().available_devices),
            "pack": str(ROOT / "models/kokoro-82M-int8-ov"),
            "pack_identity": (ROOT / "models/kokoro-82M-int8-ov/SHIP_PACK_IDENTITY.txt")
            .read_text()
            .strip()
            .splitlines(),
        }

        # --- Fox: first timed (may still be warm from WARM_TEXT) + steady ---
        fox_runs = []
        for i in range(5):
            row = speech(FOX, f"fox_{i}")
            fox_runs.append(row)
            result["runs"].append(row)
        # If WARM_TEXT already pinned fox, run0 may already be steady.
        # Still discard first timed run per methodology name.
        fox_steady = fox_runs[1:]
        fox_mean = sum(r["rtf"] for r in fox_steady) / len(fox_steady)
        fox_mean_wall = sum(r["wall_s"] for r in fox_steady) / len(fox_steady)
        result["fox"] = {
            "first": fox_runs[0],
            "steady_n": len(fox_steady),
            "steady_mean_rtf": round(fox_mean, 4),
            "steady_mean_wall_s": round(fox_mean_wall, 3),
            "steady_runs": fox_steady,
        }
        print(f"FOX steady mean RTF={fox_mean:.4f}", flush=True)

        # --- Multi: first + steady ---
        multi_runs = []
        for i in range(4):
            row = speech(MULTI, f"multi_{i}")
            multi_runs.append(row)
            result["runs"].append(row)
        multi_steady = multi_runs[1:]
        multi_mean = sum(r["rtf"] for r in multi_steady) / len(multi_steady)
        multi_mean_wall = sum(r["wall_s"] for r in multi_steady) / len(multi_steady)
        result["multi"] = {
            "first": multi_runs[0],
            "steady_n": len(multi_steady),
            "steady_mean_rtf": round(multi_mean, 4),
            "steady_mean_wall_s": round(multi_mean_wall, 3),
            "steady_runs": multi_steady,
        }
        print(f"MULTI steady mean RTF={multi_mean:.4f}", flush=True)

        # --- Novel tax (once) ---
        n1 = speech(NOVEL, "novel_first")
        n2 = speech(NOVEL, "novel_second")
        result["runs"].extend([n1, n2])
        result["novel_tax"] = {
            "text": NOVEL,
            "first": n1,
            "second": n2,
            "delta_wall_s": round(n1["wall_s"] - n2["wall_s"], 3),
        }
        print(
            f"NOVEL tax delta_wall={result['novel_tax']['delta_wall_s']:.2f}s",
            flush=True,
        )

        # --- Report-only chunk overhead (same text; observe c2 via log if any) ---
        # With cache off, compare wall for one request; multi-sentence short text.
        o1 = speech(OVERHEAD_ONE, "overhead_punctuated")
        # Single long sentence (likely 1 chunk) with similar words
        one_chunkish = (
            "Alpha one bravo two charlie three delta four echo five without periods"
        )
        o2 = speech(one_chunkish, "overhead_onechunkish")
        result["runs"].extend([o1, o2])
        result["chunk_overhead_report_only"] = {
            "punctuated": o1,
            "onechunkish": o2,
            "note": "report-only G3; not a kill bar",
        }

        # Bars
        fox_pass = fox_mean <= 1.0
        multi_pass = multi_mean <= 1.0
        fable_fox = fox_mean <= 0.85
        result["bars"] = {
            "fox_steady_le_1": fox_pass,
            "multi_steady_le_1": multi_pass,
            "fable_pred_fox_le_0_85": fable_fox,
            "fox_steady_mean_rtf": round(fox_mean, 4),
            "multi_steady_mean_rtf": round(multi_mean, 4),
        }
        result["i0_3_verdict"] = (
            "PASS" if (fox_pass and multi_pass) else "FAIL"
        )
        print("BARS", json.dumps(result["bars"]), flush=True)
        print("VERDICT", result["i0_3_verdict"], flush=True)

        out_json = OUT / "i0_3_result.json"
        out_json.write_text(json.dumps(result, indent=2) + "\n")
        print("WROTE", out_json, flush=True)
        return 0 if result["i0_3_verdict"] == "PASS" else 1

    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
        logf.close()
        print("server stopped", flush=True)


if __name__ == "__main__":
    sys.exit(main())
