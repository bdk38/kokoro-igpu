#!/usr/bin/env python3
"""S0.2 — load official Kokoro OV IR via GenAI Text2SpeechPipeline on GPU; one generate."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import wave
from pathlib import Path

import numpy as np

MODEL = Path(
    os.environ.get(
        "S0_KOKORO_MODEL",
        "/data/intel-igpu-tts/spike/ov263-genai/out/kokoro-82M-int8-ov",
    )
)
OUT = Path(os.environ.get("S0_OUT", "/data/intel-igpu-tts/spike/ov263-genai/out"))
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
    print("espeakng_loader setup skip:", e, flush=True)

result: dict = {
    "gate": "S0.2",
    "model_path": str(MODEL),
    "model_repo": "OpenVINO/kokoro-82M-int8-ov",
    "device": DEVICE,
    "text": TEXT,
    "voice": VOICE,
    "load_ok": False,
    "generate_ok": False,
    "error": None,
    "error_type": None,
}


def main() -> int:
    import openvino as ov
    import openvino_genai as og

    result["openvino"] = ov.__version__
    result["openvino_genai"] = getattr(og, "__version__", "unknown")
    result["devices"] = list(ov.Core().available_devices)
    print("openvino", result["openvino"], flush=True)
    print("genai", result["openvino_genai"], flush=True)
    print("devices", result["devices"], flush=True)
    print("model", MODEL, "xml", (MODEL / "openvino_model.xml").exists(), flush=True)

    t0 = time.time()
    try:
        pipe = og.Text2SpeechPipeline(str(MODEL), DEVICE)
        result["load_s"] = round(time.time() - t0, 3)
        result["load_ok"] = True
        print(f"LOAD_OK in {result['load_s']}s", flush=True)
    except Exception as e:
        result["load_s"] = round(time.time() - t0, 3)
        result["error"] = f"{type(e).__name__}: {e}"
        result["error_type"] = type(e).__name__
        result["error_tb"] = traceback.format_exc()
        msg = str(e).lower()
        if any(
            x in msg
            for x in ("conv", "rank", "interpolate", "linear_onnx", "programbuilder")
        ):
            result["branch_hint"] = "B2_plugin_wall"
        else:
            result["branch_hint"] = "load_fail_other"
        print("LOAD_FAIL", result["error"], flush=True)
        print(result["error_tb"], flush=True)
        try:
            t1 = time.time()
            _ = og.Text2SpeechPipeline(str(MODEL), "CPU")
            result["cpu_load_ok"] = True
            result["cpu_load_s"] = round(time.time() - t1, 3)
            print("CPU_LOAD_OK", result["cpu_load_s"], flush=True)
        except Exception as e2:
            result["cpu_load_ok"] = False
            result["cpu_load_error"] = f"{type(e2).__name__}: {e2}"
            print("CPU_LOAD_FAIL", result["cpu_load_error"], flush=True)
        _write(result)
        return 2

    t1 = time.time()
    try:
        import openvino as ov

        # Official sample API: generate(text, speaker_embedding_tensor, language=...)
        shape = tuple(pipe.get_speaker_embedding_shape())
        result["speaker_embedding_shape"] = list(shape)
        voice_bin = MODEL / "voices" / f"{VOICE}.bin"
        if not voice_bin.exists():
            # fallback common voice
            alt = MODEL / "voices" / "af_bella.bin"
            print(f"voice {voice_bin} missing; try {alt}", flush=True)
            voice_bin = alt
            result["voice"] = voice_bin.stem
        emb = np.fromfile(voice_bin, dtype=np.float32)
        expected = int(np.prod(shape))
        if emb.size != expected:
            raise ValueError(
                f"voice pack size {emb.size} != expected {expected} for shape {shape}"
            )
        speaker_embedding = ov.Tensor(emb.reshape(shape))
        print(
            f"speaker_embedding from {voice_bin.name} shape={shape}",
            flush=True,
        )
        gen = pipe.generate(TEXT, speaker_embedding, language="en-us")
        result["generate_kwargs"] = {"language": "en-us", "speaker_from": str(voice_bin)}

        result["generate_s"] = round(time.time() - t1, 3)
        audio = _extract_audio(gen)
        audio = np.nan_to_num(audio.astype(np.float32))
        result["audio_samples"] = int(audio.size)
        result["audio_s"] = float(audio.size / SR) if audio.size else 0.0
        result["peak_abs"] = float(np.max(np.abs(audio))) if audio.size else 0.0
        result["sample_rate"] = getattr(gen, "output_sample_rate", SR)
        result["generate_ok"] = audio.size > 0 and result["peak_abs"] >= 1e-4
        wav_path = OUT / "s0_2_gpu_fox.wav"
        _write_wav(wav_path, audio, int(result["sample_rate"] or SR))
        result["wav_path"] = str(wav_path)
        result["branch_hint"] = (
            "B1_or_B3_load_generate_ok"
            if result["generate_ok"]
            else "generate_silent_or_empty"
        )
        print(
            f"GENERATE wall={result['generate_s']}s audio={result['audio_s']:.2f}s "
            f"peak={result['peak_abs']:.4f} -> {wav_path}",
            flush=True,
        )
    except Exception as e:
        result["generate_s"] = round(time.time() - t1, 3)
        result["error"] = f"{type(e).__name__}: {e}"
        result["error_type"] = type(e).__name__
        result["error_tb"] = traceback.format_exc()
        msg = str(e).lower()
        if any(x in msg for x in ("conv", "rank", "interpolate", "linear_onnx")):
            result["branch_hint"] = "B2_plugin_wall_at_generate"
        else:
            result["branch_hint"] = "generate_fail_other"
        print("GENERATE_FAIL", result["error"], flush=True)
        print(result["error_tb"], flush=True)
        _write(result)
        return 3

    result["s0_2_verdict"] = (
        "PASS" if result["load_ok"] and result["generate_ok"] else "FAIL"
    )
    _write(result)
    print("VERDICT", result["s0_2_verdict"], flush=True)
    return 0 if result["s0_2_verdict"] == "PASS" else 1


def _extract_audio(gen) -> np.ndarray:
    if hasattr(gen, "speeches") and gen.speeches:
        speech = gen.speeches[0]
        if hasattr(speech, "data"):
            return np.array(speech.data, dtype=np.float32).reshape(-1)
        return np.asarray(speech, dtype=np.float32).reshape(-1)
    if hasattr(gen, "audio"):
        return np.asarray(gen.audio, dtype=np.float32).reshape(-1)
    if isinstance(gen, (list, tuple)) and gen:
        return np.asarray(gen[0], dtype=np.float32).reshape(-1)
    return np.asarray(gen, dtype=np.float32).reshape(-1)


def _write_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio, -1, 1) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def _write(obj: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "s0_2_result.json"
    p.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print("WROTE", p, flush=True)


if __name__ == "__main__":
    sys.exit(main())
