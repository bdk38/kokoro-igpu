#!/usr/bin/env python3
"""I0.2 smoke: start ovgenai-gpu server briefly, exercise health + speech + C2.

Starts kokoro_server on port 8891 with:
  KOKORO_BACKEND=ovgenai-gpu
  KOKORO_TTS_CACHE=1

Hits:
  GET  /health
  POST /v1/audio/speech  fox (x2 — print cache headers on second)
  POST /v1/audio/speech  multi-sentence (c2txt multi-chunk)
  POST /v1/audio/speech  speed=1.2 (native GenAI speed, one file)

Writes WAVs under artifacts/i0_2/. Exits non-zero on failure.
Uses absolute ship-venv python paths under /data/intel-igpu-tts.
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
from pathlib import Path

ROOT = Path("/data/intel-igpu-tts")
VENV_PY = ROOT / "venv" / "bin" / "python"
SERVER_PY = ROOT / "scripts" / "kokoro_server.py"
OUT_DIR = ROOT / "artifacts" / "i0_2"
PORT = 8891
BASE = f"http://127.0.0.1:{PORT}"
VOICE = "af_bella"

FOX = "The quick brown fox jumps over the lazy dog."
# Enough sentences that chunk_text_strings emits 2+ chunks (c2txt multi path).
MULTI = (
    "The quick brown fox jumps over the lazy dog. "
    "Pack my box with five dozen liquor jugs. "
    "How vexingly quick daft zebras jump! "
    "Sphinx of black quartz, judge my vow carefully today. "
    "Amazingly few discotheques provide jukeboxes for quiet evenings. "
    "The five boxing wizards jump quickly across the frozen riverbank. "
    "We promptly judged antique ivory buckles for the next prize. "
    "Crazy Fredrick bought many very exquisite opal jewels yesterday."
)
SPEED_TEXT = "Native GenAI speed check at one point two."


def _http_json(method: str, url: str, body: dict | None = None, timeout: float = 300.0):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        # HTTPMessage is case-insensitive; normalize for plain-dict lookup.
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        return resp.status, raw, hdrs


def _wait_health(proc: subprocess.Popen, deadline_s: float = 180.0) -> dict:
    t0 = time.time()
    last_err = None
    while time.time() - t0 < deadline_s:
        if proc.poll() is not None:
            raise RuntimeError(
                f"server exited early code={proc.returncode}; "
                f"see stderr above")
        try:
            st, raw, _ = _http_json("GET", f"{BASE}/health", timeout=5.0)
            if st == 200:
                return json.loads(raw.decode("utf-8"))
        except Exception as e:
            last_err = e
        time.sleep(1.0)
    raise TimeoutError(f"health not ready in {deadline_s}s; last={last_err}")


def _speech(text: str, voice: str, speed: float, out_path: Path) -> dict:
    body = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "speed": speed,
        "response_format": "wav",
    }
    st, raw, hdrs = _http_json("POST", f"{BASE}/v1/audio/speech", body=body)
    if st != 200:
        raise RuntimeError(f"speech status {st} for {out_path.name}")
    if len(raw) < 44:
        raise RuntimeError(f"speech body too small ({len(raw)}) for {out_path.name}")
    out_path.write_bytes(raw)
    return {
        "bytes": len(raw),
        "X-Kokoro-Backend": hdrs.get("x-kokoro-backend"),
        "X-Kokoro-Cache": hdrs.get("x-kokoro-cache"),
        "X-Kokoro-RTF": hdrs.get("x-kokoro-rtf"),
        "X-Kokoro-Format": hdrs.get("x-kokoro-format"),
    }


def main() -> int:
    if not VENV_PY.is_file():
        print(f"FAIL: missing venv python {VENV_PY}", flush=True)
        return 2
    if not SERVER_PY.is_file():
        print(f"FAIL: missing server {SERVER_PY}", flush=True)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["KOKORO_BACKEND"] = "ovgenai-gpu"
    env["KOKORO_TTS_CACHE"] = "1"
    env["KOKORO_TTS_CACHE_TIER"] = "both"
    # Isolate smoke cache from product tree if desired; still under project.
    env.setdefault(
        "KOKORO_TTS_CACHE_DIR",
        str(ROOT / "cache" / "tts-i0_2-smoke"),
    )
    env.setdefault(
        "KOKORO_GENAI_MODEL",
        str(ROOT / "models" / "kokoro-82M-int8-ov"),
    )

    print(f"[i0_2] starting server port={PORT} backend=ovgenai-gpu", flush=True)
    proc = subprocess.Popen(
        [str(VENV_PY), str(SERVER_PY), "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    log_path = OUT_DIR / "server.log"
    log_f = open(log_path, "w", encoding="utf-8")

    def _drain_log():
        if proc.stdout is None:
            return
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            log_f.write(line)
            log_f.flush()
            print(line, end="", flush=True)

    # Background drain so pipe does not fill; simple thread.
    import threading
    drain = threading.Thread(target=_drain_log, daemon=True)
    drain.start()

    try:
        health = _wait_health(proc)
        print(f"[i0_2] health={json.dumps(health)}", flush=True)
        if health.get("backend") != "ovgenai-gpu":
            print("FAIL: backend not ovgenai-gpu", flush=True)
            return 1
        if not health.get("genai"):
            print("FAIL: health missing genai=true", flush=True)
            return 1

        fox1 = _speech(FOX, VOICE, 1.0, OUT_DIR / "fox1.wav")
        print(f"[i0_2] fox1={fox1}", flush=True)

        fox2 = _speech(FOX, VOICE, 1.0, OUT_DIR / "fox2.wav")
        print(f"[i0_2] fox2 cache headers: "
              f"X-Kokoro-Cache={fox2.get('X-Kokoro-Cache')!r} "
              f"X-Kokoro-Backend={fox2.get('X-Kokoro-Backend')!r} "
              f"X-Kokoro-RTF={fox2.get('X-Kokoro-RTF')!r}",
              flush=True)
        if fox2.get("X-Kokoro-Cache") not in ("hit", "partial"):
            # Warmup may have populated C2; second request should hit C1 or C2.
            print(f"WARN: expected cache hit/partial on fox2, got "
                  f"{fox2.get('X-Kokoro-Cache')!r}", flush=True)

        multi = _speech(MULTI, VOICE, 1.0, OUT_DIR / "multi.wav")
        print(f"[i0_2] multi={multi}", flush=True)

        speed = _speech(SPEED_TEXT, VOICE, 1.2, OUT_DIR / "speed_1_2.wav")
        print(f"[i0_2] speed_1.2={speed}", flush=True)

        # Basic size sanity: multi should be longer than fox.
        if (OUT_DIR / "multi.wav").stat().st_size <= (OUT_DIR / "fox1.wav").stat().st_size:
            print("FAIL: multi wav not larger than fox", flush=True)
            return 1

        print("[i0_2] PASS", flush=True)
        return 0
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}", flush=True)
        return 1
    finally:
        if proc.poll() is None:
            print(f"[i0_2] terminating server pid={proc.pid}", flush=True)
            try:
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=30)
            except Exception:
                proc.kill()
                proc.wait(timeout=10)
        log_f.close()


if __name__ == "__main__":
    sys.exit(main())
