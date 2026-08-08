#!/usr/bin/env python3
"""I0.4 regression matrix (notes/54, notes/61 F1/F2, notes/63).

Pieces:
  A. ort-cpu pre/post fox vs artifacts/webui_soak/fox_miss.wav (F1)
  B. ort-cpu within-post multi-chunk determinism (cache off) + size check vs v121 p0
  C. ort-cpu cache P0 (off determinism) + P1 (miss→hit byte-eq) on ephemeral port
  D. ovgenai-gpu within-backend P0/P1 byte-eq (F2) on ephemeral port
  E. WebUI path smoke: container → host :8880 health + speech if docker net allows

Does not change product default. Leaves :8880 running if it was ort-cpu.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path("/data/intel-igpu-tts")
VENV = ROOT / "venv/bin/python"
SERVER = ROOT / "scripts/kokoro_server.py"
OUT = ROOT / "artifacts/i0_4"
OUT.mkdir(parents=True, exist_ok=True)

FOX = "The quick brown fox jumps over the lazy dog."
# Long multi-chunk text (ort path packs by token ids ~510)
MULTI = (
    "Kokoro is an open-weight text to speech model with eighty two million parameters. "
    "Despite its lightweight architecture, it delivers comparable quality to larger models "
    "while being significantly faster and more cost efficient. "
    "With one hour of training data from a few people, the model can learn to speak in their voices. "
    "This multi-sentence passage exercises several synthesis chunks for regression. "
    "The quick brown fox jumps over the lazy dog near the river bank at dawn. "
    "Please remember to bring your keys, wallet, and passport when you travel abroad tomorrow."
)
VOICE = "af_bella"
PRE_FOX = ROOT / "artifacts/webui_soak/fox_miss.wav"
V121_P0 = ROOT / "artifacts/v121_cache/p0_a.wav"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def http(method, url, body=None, timeout=600.0):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read(), {k.lower(): v for k, v in resp.headers.items()}


def speech(base, text, tag, speed=1.0, voice=VOICE):
    t0 = time.time()
    st, raw, hdrs = http(
        "POST",
        f"{base}/v1/audio/speech",
        {"input": text, "voice": voice, "response_format": "wav", "speed": speed},
    )
    wall = time.time() - t0
    assert st == 200, (tag, st)
    path = OUT / f"{tag}.wav"
    path.write_bytes(raw)
    with wave.open(io.BytesIO(raw), "rb") as w:
        audio_s = w.getnframes() / float(w.getframerate())
    row = {
        "tag": tag,
        "wall_s": round(wall, 3),
        "audio_s": round(audio_s, 3),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "cache": hdrs.get("x-kokoro-cache"),
        "backend": hdrs.get("x-kokoro-backend"),
        "path": str(path),
    }
    print(
        f"[{tag}] {row['bytes']}B wall={row['wall_s']}s "
        f"cache={row['cache']} sha={row['sha256'][:12]}…",
        flush=True,
    )
    return row


def start_server(port, env_extra, log_name):
    env = os.environ.copy()
    env.update(env_extra)
    log_path = OUT / log_name
    logf = open(log_path, "w")
    proc = subprocess.Popen(
        [str(VENV), str(SERVER), "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    base = f"http://127.0.0.1:{port}"
    t0 = time.time()
    last = None
    while time.time() - t0 < 240:
        try:
            st, raw, _ = http("GET", f"{base}/health", timeout=3)
            if st == 200:
                return proc, logf, base, json.loads(raw.decode())
        except Exception as e:
            last = e
            if proc.poll() is not None:
                logf.flush()
                raise RuntimeError(
                    f"server died early: {log_path.read_text()[-2000:]}"
                )
        time.sleep(0.5)
    raise RuntimeError(f"health timeout port={port}: {last}")


def stop_server(proc, logf):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        proc.terminate()
    try:
        proc.wait(timeout=20)
    except Exception:
        proc.kill()
    logf.close()


def main():
    result = {
        "gate": "I0.4",
        "pieces": {},
        "stack": {},
    }
    import openvino as ov

    result["stack"] = {
        "openvino": ov.__version__,
        "python": sys.version.split()[0],
    }
    try:
        import openvino_genai as og

        result["stack"]["openvino_genai"] = og.__version__
    except Exception as e:
        result["stack"]["openvino_genai"] = f"err:{e}"

    # ----- A: pre/post fox on live :8880 (ort-cpu) -----
    print("=== A pre/post fox ===", flush=True)
    live = "http://127.0.0.1:8880"
    hst, hraw, _ = http("GET", f"{live}/health")
    health = json.loads(hraw.decode())
    result["live_health"] = health
    assert health.get("backend") == "ort-cpu", health

    # cache may be on — use unique never-seen suffix? F1 wants same fox text as soak.
    # Soak fox was synth without requiring cache-off if deterministic.
    # For true synth path, hit ephemeral cache-off server for post fox too.
    # Compare BOTH live (may hit cache) and fresh cache-off synth to pre ref.
    pre_sha = sha256_file(PRE_FOX)
    pre_bytes = PRE_FOX.stat().st_size

    # Ephemeral ort cache-off for clean post synth
    proc, logf, base, h = start_server(
        8894,
        {
            "KOKORO_BACKEND": "ort-cpu",
            "KOKORO_TTS_CACHE": "0",
            "KOKORO_DEFAULT_VOICE": VOICE,
        },
        "ort_cacheoff.log",
    )
    try:
        post_fox = speech(base, FOX, "A_post_fox_cacheoff")
        post_fox2 = speech(base, FOX, "A_post_fox_cacheoff_b")
        multi_a = speech(base, MULTI, "B_multi_a")
        multi_b = speech(base, MULTI, "B_multi_b")
    finally:
        stop_server(proc, logf)

    fox_match = post_fox["sha256"] == pre_sha
    fox_det = post_fox["sha256"] == post_fox2["sha256"]
    multi_det = multi_a["sha256"] == multi_b["sha256"]
    v121_size = V121_P0.stat().st_size if V121_P0.is_file() else None

    result["pieces"]["A_pre_post_fox"] = {
        "pre_path": str(PRE_FOX),
        "pre_sha256": pre_sha,
        "pre_bytes": pre_bytes,
        "post": post_fox,
        "post_b": post_fox2,
        "byte_match_pre": fox_match,
        "within_post_determinism": fox_det,
        "pass": fox_match and fox_det,
    }
    result["pieces"]["B_multi_determinism"] = {
        "a": multi_a,
        "b": multi_b,
        "within_post_byte_equal": multi_det,
        "v121_p0_bytes": v121_size,
        "note": "exact v121 P0 text not recovered; within-post multi det is bar; size informative only",
        "pass": multi_det,
    }
    print(
        f"A fox pre/post match={fox_match} det={fox_det} "
        f"B multi det={multi_det}",
        flush=True,
    )

    # ----- C: cache P0/P1 ort -----
    print("=== C cache P0/P1 ort ===", flush=True)
    cache_dir = OUT / "tts_cache_ort"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir()

    # P0 cache off
    proc, logf, base, h = start_server(
        8895,
        {
            "KOKORO_BACKEND": "ort-cpu",
            "KOKORO_TTS_CACHE": "0",
            "KOKORO_DEFAULT_VOICE": VOICE,
        },
        "ort_p0.log",
    )
    try:
        p0a = speech(base, FOX, "C_p0_a")
        p0b = speech(base, FOX, "C_p0_b")
    finally:
        stop_server(proc, logf)

    # P1 cache on
    proc, logf, base, h = start_server(
        8895,
        {
            "KOKORO_BACKEND": "ort-cpu",
            "KOKORO_TTS_CACHE": "1",
            "KOKORO_TTS_CACHE_TIER": "both",
            "KOKORO_TTS_CACHE_DIR": str(cache_dir),
            "KOKORO_DEFAULT_VOICE": VOICE,
        },
        "ort_p1.log",
    )
    try:
        p1_miss = speech(base, FOX, "C_p1_miss")
        p1_hit = speech(base, FOX, "C_p1_hit")
    finally:
        stop_server(proc, logf)

    c_pass = (
        p0a["sha256"] == p0b["sha256"]
        and p0a.get("cache") in (None, "None")
        and p1_miss["sha256"] == p1_hit["sha256"]
        and (p1_hit.get("cache") == "hit" or p1_hit["wall_s"] < 0.2)
    )
    # header may be missing if middleware — also accept wall hit
    result["pieces"]["C_ort_cache_p0_p1"] = {
        "p0_equal": p0a["sha256"] == p0b["sha256"],
        "p0_a": p0a,
        "p0_b": p0b,
        "p1_bodies_equal": p1_miss["sha256"] == p1_hit["sha256"],
        "p1_miss": p1_miss,
        "p1_hit": p1_hit,
        "pass": bool(
            p0a["sha256"] == p0b["sha256"]
            and p1_miss["sha256"] == p1_hit["sha256"]
            and p1_hit["wall_s"] < max(0.25, p1_miss["wall_s"] * 0.25)
        ),
    }
    print("C pass", result["pieces"]["C_ort_cache_p0_p1"]["pass"], flush=True)

    # ----- D: ovgenai P0/P1 -----
    print("=== D ovgenai P0/P1 ===", flush=True)
    gcache = OUT / "tts_cache_genai"
    if gcache.exists():
        shutil.rmtree(gcache)
    gcache.mkdir()

    # Use short fox for speed; multi one pair for multi-chunk c2txt
    GENAI_MULTI = (
        "Kokoro is an open-weight text to speech model with eighty two million parameters. "
        "Despite its lightweight architecture, it delivers comparable quality to larger models "
        "while being significantly faster and more cost efficient."
    )

    proc, logf, base, h = start_server(
        8896,
        {
            "KOKORO_BACKEND": "ovgenai-gpu",
            "KOKORO_GENAI_MODEL": str(ROOT / "models/kokoro-82M-int8-ov"),
            "KOKORO_TTS_CACHE": "0",
            "KOKORO_DEFAULT_VOICE": VOICE,
            "KOKORO_WARM_TEXT": FOX,
        },
        "genai_p0.log",
    )
    try:
        assert h.get("backend") == "ovgenai-gpu", h
        g_p0a = speech(base, FOX, "D_p0_fox_a")
        g_p0b = speech(base, FOX, "D_p0_fox_b")
        g_m0a = speech(base, GENAI_MULTI, "D_p0_multi_a")
        g_m0b = speech(base, GENAI_MULTI, "D_p0_multi_b")
    finally:
        stop_server(proc, logf)

    proc, logf, base, h = start_server(
        8896,
        {
            "KOKORO_BACKEND": "ovgenai-gpu",
            "KOKORO_GENAI_MODEL": str(ROOT / "models/kokoro-82M-int8-ov"),
            "KOKORO_TTS_CACHE": "1",
            "KOKORO_TTS_CACHE_TIER": "both",
            "KOKORO_TTS_CACHE_DIR": str(gcache),
            "KOKORO_DEFAULT_VOICE": VOICE,
            "KOKORO_WARM_TEXT": FOX,
        },
        "genai_p1.log",
    )
    try:
        # unique text so miss then hit (not warm-text C1)
        uniq = "I0.4 genai cache byte equality probe sentence number seven."
        g_miss = speech(base, uniq, "D_p1_miss")
        g_hit = speech(base, uniq, "D_p1_hit")
    finally:
        stop_server(proc, logf)

    d_pass = (
        g_p0a["sha256"] == g_p0b["sha256"]
        and g_m0a["sha256"] == g_m0b["sha256"]
        and g_miss["sha256"] == g_hit["sha256"]
        and g_hit["wall_s"] < max(0.5, g_miss["wall_s"] * 0.25)
    )
    result["pieces"]["D_ovgenai_p0_p1"] = {
        "fox_p0_equal": g_p0a["sha256"] == g_p0b["sha256"],
        "multi_p0_equal": g_m0a["sha256"] == g_m0b["sha256"],
        "p1_bodies_equal": g_miss["sha256"] == g_hit["sha256"],
        "fox_a": g_p0a,
        "fox_b": g_p0b,
        "multi_a": g_m0a,
        "multi_b": g_m0b,
        "p1_miss": g_miss,
        "p1_hit": g_hit,
        "pass": d_pass,
    }
    print("D pass", d_pass, flush=True)

    # ----- E: WebUI path smoke -----
    print("=== E WebUI path ===", flush=True)
    e = {"live_health_ok": health.get("status") == "ok", "backend": health.get("backend")}
    # speech on live 8880 (cache may hit)
    try:
        live_fox = speech(live, FOX, "E_live_fox")
        e["live_speech_ok"] = True
        e["live_fox"] = live_fox
    except Exception as ex:
        e["live_speech_ok"] = False
        e["live_speech_err"] = str(ex)

    # docker container → host if present
    try:
        r = subprocess.run(
            [
                "docker",
                "ps",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        names = [n for n in r.stdout.splitlines() if n]
        e["docker_containers"] = names
        owui = next((n for n in names if "open-webui" in n.lower() or "webui" in n.lower()), None)
        if owui:
            # curl from container
            cr = subprocess.run(
                [
                    "docker",
                    "exec",
                    owui,
                    "curl",
                    "-sS",
                    "--max-time",
                    "15",
                    "http://host.docker.internal:8880/health",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            e["container_health_rc"] = cr.returncode
            e["container_health_body"] = (cr.stdout or cr.stderr)[:500]
            e["container_health_ok"] = cr.returncode == 0 and "ort-cpu" in (cr.stdout or "")
        else:
            e["container_health_ok"] = None
            e["container_note"] = "no open-webui container name matched"
    except Exception as ex:
        e["container_health_ok"] = None
        e["container_err"] = str(ex)

    e["pass"] = bool(e.get("live_speech_ok") and e.get("live_health_ok"))
    result["pieces"]["E_webui_path"] = e
    print("E pass", e["pass"], "container", e.get("container_health_ok"), flush=True)

    # ----- rollup -----
    pieces_pass = {
        k: bool(v.get("pass"))
        for k, v in result["pieces"].items()
    }
    result["piece_pass"] = pieces_pass
    result["i0_4_verdict"] = (
        "PASS" if all(pieces_pass.values()) else "FAIL"
    )
    outp = OUT / "i0_4_result.json"
    outp.write_text(json.dumps(result, indent=2) + "\n")
    print("PIECES", json.dumps(pieces_pass), flush=True)
    print("VERDICT", result["i0_4_verdict"], flush=True)
    print("WROTE", outp, flush=True)
    return 0 if result["i0_4_verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
