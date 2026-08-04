#!/usr/bin/env python3
import json, subprocess, time, wave
from pathlib import Path
import numpy as np

outdir = Path("/data/intel-igpu-tts/artifacts/v112")
outdir.mkdir(parents=True, exist_ok=True)

sentences = [
    ("s1_well", "Well, honestly, I think we should wait; however, the choice is yours."),
    ("s2_wallet", "Wait, did you remember the keys, the wallet, and the passport?"),
    ("s3_peter", "Peter packed a heavy box of bright blue berries."),
    ("s4_swans", "Seven silver swans swam smoothly south across the sea."),
    ("fox", "The quick brown fox jumps over the lazy dog."),
]

def analyze(path):
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    frame = int(0.02 * sr)
    n_fr = x.size // frame
    if n_fr < 3:
        return {"dur": x.size / sr, "groups": 0}
    rms = np.sqrt(np.mean(x[: n_fr * frame].reshape(n_fr, frame) ** 2, axis=1))
    ref = float(np.percentile(rms, 90))
    speech = rms >= 0.15 * ref
    need = 5
    groups = []
    idx = np.nonzero(speech)[0]
    if idx.size:
        gs = prev = int(idx[0])
        for j in idx[1:]:
            j = int(j)
            if j - prev - 1 >= need:
                groups.append((gs, prev + 1))
                gs = j
            prev = j
        groups.append((gs, prev + 1))
    ginfo = []
    for s, e in groups:
        peak = float(rms[s:e].max())
        ginfo.append(
            {
                "start": round(s * 0.02, 2),
                "end": round(e * 0.02, 2),
                "dur": round((e - s) * 0.02, 2),
                "peak_over_ref": round(peak / ref, 3) if ref > 0 else None,
            }
        )
    tail = x[-int(0.6 * sr) :] if x.size > int(0.6 * sr) else x
    return {
        "dur": round(x.size / sr, 3),
        "peak": round(float(np.max(np.abs(x))), 4),
        "ref90": round(ref, 4),
        "groups": len(groups),
        "ginfo": ginfo,
        "tail06_peak": round(float(np.max(np.abs(tail))), 4),
        "tail06_rms": round(float(np.sqrt(np.mean(tail**2))), 4),
    }

results = {}
for name, text in sentences:
    body = outdir / f"{name}.json"
    wav = outdir / f"{name}.wav"
    hdr = outdir / f"{name}.headers"
    body.write_text(
        json.dumps(
            {
                "model": "kokoro",
                "input": text,
                "voice": "af_bella",
                "response_format": "wav",
            }
        )
    )
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            "http://127.0.0.1:8880/v1/audio/speech",
            "-H",
            "Content-Type: application/json",
            "--data-binary",
            f"@{body}",
            "-D",
            str(hdr),
            "--output",
            str(wav),
            "-w",
            "%{http_code} %{time_total}",
        ],
        capture_output=True,
        text=True,
    )
    parts = r.stdout.strip().split()
    http = parts[0] if parts else "000"
    ttot = float(parts[1]) if len(parts) > 1 else -1
    headers = hdr.read_text(errors="replace") if hdr.exists() else ""
    rtf = None
    for line in headers.splitlines():
        if line.lower().startswith("x-kokoro-rtf:"):
            rtf = line.split(":", 1)[1].strip()
    if http == "200":
        info = analyze(wav)
    else:
        info = {"error": wav.read_text(errors="replace")[:300] if wav.exists() else "no file"}
    results[name] = {"http": http, "curl_s": ttot, "rtf": rtf, "text": text, **info}
    print(
        f"=== {name} http={http} curl={ttot:.2f}s rtf={rtf} "
        f"dur={info.get('dur')} groups={info.get('groups')} ==="
    )
    for i, g in enumerate(info.get("ginfo") or []):
        print(f"  g{i}: {g}")
    if "tail06_peak" in info:
        print(f"  tail0.6 peak={info['tail06_peak']} rms={info['tail06_rms']}")

(outdir / "sentence_matrix.json").write_text(json.dumps(results, indent=2))
print("wrote", outdir / "sentence_matrix.json")
