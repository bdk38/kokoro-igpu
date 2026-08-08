#!/usr/bin/env python3
"""S0.4 — generate official GenAI GPU WAVs for Nexus ears (int8 pack)."""
from __future__ import annotations

import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

MODEL = Path("/data/intel-igpu-tts/spike/ov263-genai/out/kokoro-82M-int8-ov")
OUT = Path("/data/intel-igpu-tts/spike/ov263-genai/out/s0_4")
DEVICE = "GPU"
VOICE = "af_heart"
SR = 24000

# Gate: ≥3 shorts + ≥1 multi-sentence
UTTERANCES = [
    ("s0_4_short1_fox.wav", "The quick brown fox jumps over the lazy dog."),
    ("s0_4_short2_hello.wav", "Hello, this is a short speech generation test."),
    ("s0_4_short3_keys.wav", "Please remember to bring your keys, wallet, and passport."),
    (
        "s0_4_multi_passage.wav",
        "Kokoro is an open-weight text to speech model with eighty two million parameters. "
        "Despite its lightweight architecture, it delivers comparable quality to larger models "
        "while being significantly faster and more cost efficient. "
        "This multi-sentence passage is for ear evaluation of the official OpenVINO path.",
    ),
]

try:
    import espeakng_loader

    os.environ.setdefault("MISAKI_ESPEAK_LIBRARY", espeakng_loader.get_library_path())
    os.environ.setdefault("ESPEAK_DATA_PATH", espeakng_loader.get_data_path())
except Exception as e:
    print("espeakng_loader skip", e, flush=True)


def write_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main() -> int:
    import openvino as ov
    import openvino_genai as og

    OUT.mkdir(parents=True, exist_ok=True)
    print("load", DEVICE, flush=True)
    t0 = time.time()
    pipe = og.Text2SpeechPipeline(str(MODEL), DEVICE)
    print("loaded", round(time.time() - t0, 2), "s", flush=True)

    shape = tuple(pipe.get_speaker_embedding_shape())
    emb = np.fromfile(MODEL / "voices" / f"{VOICE}.bin", dtype=np.float32)
    speaker = ov.Tensor(emb.reshape(shape))

    rows = []
    for fname, text in UTTERANCES:
        path = OUT / fname
        t1 = time.time()
        gen = pipe.generate(text, speaker, language="en-us")
        wall = time.time() - t1
        audio = np.array(gen.speeches[0].data, dtype=np.float32).reshape(-1)
        audio = np.nan_to_num(audio)
        sr = int(getattr(gen, "output_sample_rate", SR) or SR)
        write_wav(path, audio, sr)
        dur = audio.size / sr
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        row = {
            "filename": fname,
            "path": str(path),
            "text": text,
            "voice": VOICE,
            "wall_s": round(wall, 3),
            "audio_s": round(dur, 3),
            "rtf_wall": round(wall / max(dur, 1e-6), 3),
            "peak_abs": peak,
            "samples": int(audio.size),
            "sample_rate": sr,
            "bytes": path.stat().st_size,
        }
        rows.append(row)
        print(
            f"OK {fname} audio={dur:.2f}s wall={wall:.2f}s rtf={row['rtf_wall']} peak={peak:.3f}",
            flush=True,
        )

    meta = {
        "gate": "S0.4",
        "model": str(MODEL),
        "model_repo": "OpenVINO/kokoro-82M-int8-ov",
        "device": DEVICE,
        "voice": VOICE,
        "openvino": ov.__version__,
        "openvino_genai": getattr(og, "__version__", "unknown"),
        "note": "int8 official pack; cross-checkpoint vs ship v0.19; ears binding",
        "utterances": rows,
        "ear_instructions": (
            "Nexus: PASS/FAIL by filename. Want clear speech, no pad-moan, "
            "no missing words, no garbage. ≥3 shorts + multi must PASS for S0.4."
        ),
    }
    (OUT / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("WROTE", OUT / "manifest.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
