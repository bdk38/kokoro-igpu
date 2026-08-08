#!/usr/bin/env python3
"""v1.1.7 warm-transfer experiment (Fable note_14).

After KOKORO_WARM_BUCKETS=96 pre-warm via near-capacity real synthesize,
send first-ever requests of s1..s4 (novel content, varied lengths, same
bucket 96). Record wall, RTF, tokens, audio dur.

PASS claim: all ~2.9s / RTF~0.9 -> warm transfers across content/length.
FAIL claim: any ~18s -> cold is per-content/per-length (explains v114).
"""
import json, subprocess, wave, time
from pathlib import Path

outdir = Path("/data/intel-igpu-tts/artifacts/v117")
outdir.mkdir(parents=True, exist_ok=True)

sentences = [
    ("s1_well", "Well, honestly, I think we should wait; however, the choice is yours."),
    ("s2_wallet", "Wait, did you remember the keys, the wallet, and the passport?"),
    ("s3_peter", "Peter packed a heavy box of bright blue berries."),
    ("s4_swans", "Seven silver swans swam smoothly south across the sea."),
    ("fox", "The quick brown fox jumps over the lazy dog."),
]

results = {}
for name, text in sentences:
    body = outdir / ("%s.json" % name)
    wav = outdir / ("%s.wav" % name)
    hdr = outdir / ("%s.headers" % name)
    body.write_text(json.dumps({
        "model": "kokoro",
        "input": text,
        "voice": "af_bella",
        "response_format": "wav",
    }))
    t0 = time.time()
    r = subprocess.run([
        "curl", "-s", "-X", "POST", "http://127.0.0.1:8880/v1/audio/speech",
        "-H", "Content-Type: application/json",
        "--data-binary", "@" + str(body),
        "-D", str(hdr),
        "--output", str(wav),
        "-w", "%{http_code} %{time_total}",
    ], capture_output=True, text=True)
    wall = time.time() - t0
    parts = r.stdout.strip().split()
    http = parts[0] if parts else "000"
    ttot = float(parts[1]) if len(parts) > 1 else -1
    headers = hdr.read_text(errors="replace") if hdr.exists() else ""
    meta = {}
    for line in headers.splitlines():
        if line.lower().startswith("x-kokoro-"):
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip()
    dur = None
    n_samples = None
    if http == "200" and wav.exists():
        with wave.open(str(wav), "rb") as w:
            n_samples = w.getnframes()
            sr = w.getframerate()
            dur = n_samples / float(sr)
    row = {
        "http": http,
        "curl_s": round(ttot, 3),
        "wall_s": round(wall, 3),
        "rtf": meta.get("x-kokoro-rtf"),
        "backend": meta.get("x-kokoro-backend"),
        "audio_s": round(dur, 3) if dur is not None else None,
        "n_samples": n_samples,
        "text": text,
        "headers": meta,
    }
    results[name] = row
    print("=== %s http=%s wall=%.2fs curl=%.2fs rtf=%s audio=%ss ===" % (
        name, http, wall, ttot, row["rtf"], row["audio_s"]), flush=True)

(outdir / "warm_transfer_matrix.json").write_text(json.dumps(results, indent=2))
print("wrote", outdir / "warm_transfer_matrix.json")
print("\n--- VERDICT HEURISTIC ---")
for name, row in results.items():
    rtf = row.get("rtf")
    try:
        rtf_f = float(rtf) if rtf is not None else None
    except Exception:
        rtf_f = None
    if rtf_f is not None:
        label = "WARM" if rtf_f <= 1.5 else ("COLD" if rtf_f >= 3.0 else "MID")
    else:
        label = "?"
    print("%s: curl=%s rtf=%s audio=%s -> %s" % (
        name, row.get("curl_s"), rtf, row.get("audio_s"), label))
