#!/usr/bin/env python3
"""
kokoro_server.py — OpenAI-compatible TTS server for Kokoro on bdk-server.

Phase 5 deliverable. Default backend is ORT-CPU (the proven product path);
the OpenVINO backends remain available as flags — including ov-gpu, the
real-iGPU path (correct speech, RTF > 1 on Alder Lake UHD; demo/offload
use, not latency).

Endpoints:
  POST /v1/audio/speech     OpenAI-compatible TTS (input, voice, speed,
                            response_format)
  GET  /v1/audio/voices     list available voices
  GET  /v1/models           minimal OpenAI-style model list
  GET  /health              backend + model status

Configuration (env vars):
  KOKORO_MODEL      path to ONNX model
                    default: /data/intel-igpu-tts/models/kokoro-v0_19.onnx
                    (use the patched gpu4d.stft model for OV backends)
  KOKORO_VOICES     path to voices NPZ
                    default: /data/intel-igpu-tts/models/voices-v1.0.bin
  KOKORO_BACKEND    ort-cpu | ov-cpu | ov-gpu     (default: ort-cpu)
  KOKORO_GPU_PRECISION  f32 | f16                 (default: f32; f16 is
                        broken upstream — MatMul compile bug)
  KOKORO_CACHE      OpenVINO cache dir (default: /data/intel-igpu-tts/cache/openvino)
  KOKORO_DEFAULT_VOICE  (default: af_bella)

Run:
  source /data/intel-igpu-tts/scripts/env.sh
  pip install fastapi uvicorn
  python scripts/kokoro_server.py --host 0.0.0.0 --port 8880

Open WebUI wiring (Admin -> Settings -> Audio):
  TTS Engine: OpenAI
  API Base URL: http://<bdk-server>:8880/v1
  API Key: anything (not checked)
  TTS Voice: af_bella (or any /v1/audio/voices entry, or OpenAI aliases)
  Response format: wav (mp3 works if ffmpeg is installed on the host)

Notes:
  - Long input is chunked at sentence boundaries to stay under the model's
    510-token limit; chunks are stitched with a short gap.
  - OV backends compile per token-length; the server pads chunk tokens to
    bucket sizes (96/192/288/384/512) and caches compiled models per
    bucket, so steady-state requests reuse compiles. ORT is fully dynamic.
  - mp3/opus/flac need ffmpeg on PATH; otherwise the server falls back to
    wav and says so in the X-Kokoro-Format header.
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import time
import wave

import numpy as np

# ----------------------------------------------------------------------
# config
# ----------------------------------------------------------------------

SR = 24000
MAX_TOKENS = 510
PAD_BUCKETS = [96, 192, 288, 384, 512]
CHUNK_GAP_S = 0.12

MODEL_PATH = os.environ.get(
    "KOKORO_MODEL", "/data/intel-igpu-tts/models/kokoro-v0_19.onnx")
VOICES_PATH = os.environ.get(
    "KOKORO_VOICES", "/data/intel-igpu-tts/models/voices-v1.0.bin")
BACKEND = os.environ.get("KOKORO_BACKEND", "ort-cpu")
GPU_PRECISION = os.environ.get("KOKORO_GPU_PRECISION", "f32")
CACHE_DIR = os.environ.get(
    "KOKORO_CACHE", "/data/intel-igpu-tts/cache/openvino")
DEFAULT_VOICE = os.environ.get("KOKORO_DEFAULT_VOICE", "af_bella")

# OpenAI voice aliases -> kokoro voices
OPENAI_VOICE_MAP = {
    "alloy": "af_alloy", "echo": "am_echo", "fable": "bf_emma",
    "onyx": "am_onyx", "nova": "af_nova", "shimmer": "af_shimmer",
}

# ----------------------------------------------------------------------
# tokenizer (kokoro v0.19) — same as tts_harness.py
# ----------------------------------------------------------------------

def _build_vocab():
    _pad = "$"
    _punctuation = ';:,.!?\u00a1\u00bf\u2014\u2026"\u00ab\u00bb\u201c\u201d '
    _letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    _letters_ipa = (
        "\u0251\u0250\u0252\u00e6\u0253\u0299\u03b2\u0254\u0255\u00e7\u0257"
        "\u0256\u00f0\u02a4\u0259\u0258\u025a\u025b\u025c\u025d\u025e\u025f"
        "\u0284\u0261\u0260\u0262\u029b\u0266\u0267\u0127\u0265\u029c\u0268"
        "\u026a\u029d\u026d\u026c\u026b\u026e\u029f\u0271\u026f\u0270\u014b"
        "\u0273\u0272\u0274\u00f8\u0275\u0278\u03b8\u0153\u0276\u0298\u0279"
        "\u027a\u027e\u027b\u0280\u0281\u027d\u0282\u0283\u0288\u02a7\u0289"
        "\u028a\u028b\u2c71\u028c\u0263\u0264\u028d\u03c7\u028e\u028f\u0291"
        "\u0290\u0292\u0294\u02a1\u0295\u02a2\u01c0\u01c1\u01c2\u01c3\u02c8"
        "\u02cc\u02d0\u02d1\u02bc\u02b4\u02b0\u02b1\u02b2\u02b7\u02e0\u02e4"
        "\u02de\u2193\u2191\u2192\u2197\u2198'\u0329'\u1d7b"
    )
    symbols = [_pad] + list(_punctuation) + list(_letters) + list(_letters_ipa)
    return {s: i for i, s in enumerate(symbols)}


VOCAB = _build_vocab()
_ESPEAK_BACKENDS = {}


def _espeak(lang):
    if lang not in _ESPEAK_BACKENDS:
        from phonemizer.backend import EspeakBackend
        _ESPEAK_BACKENDS[lang] = EspeakBackend(
            language=lang, preserve_punctuation=True, with_stress=True)
    return _ESPEAK_BACKENDS[lang]


def _cleanup_phonemes(ps, lang):
    ps = ps.replace("k\u0259k\u02c8o\u02d0\u0279o\u028a",
                    "k\u02c8o\u028ak\u0259\u0279o\u028a")
    ps = ps.replace("k\u0259k\u02c8\u0254\u02d0\u0279\u0259\u028a",
                    "k\u02c8\u0259\u028ak\u0259\u0279\u0259\u028a")
    ps = ps.replace("\u02b2", "j").replace("r", "\u0279")
    ps = ps.replace("x", "k").replace("\u026c", "l")
    ps = re.sub(r"(?<=[a-z\u0279\u02d0])(?=h\u02c8\u028cnd\u0279\u026ad)", " ", ps)
    ps = re.sub(r" z(?=[;:,.!?\u00a1\u00bf\u2014\u2026\"\u00ab\u00bb\u201c\u201d ]|$)",
                "z", ps)
    if lang == "en-us":
        ps = re.sub(r"(?<=n\u02c8a\u026an)ti(?!\u02d0)", "di", ps)
    return ps


def phonemes_to_ids(text, lang):
    ps = _espeak(lang).phonemize([text])
    ps = ps[0].strip() if ps else ""
    ps = _cleanup_phonemes(ps, lang)
    return [VOCAB[c] for c in ps if c in VOCAB]


_SENT_SPLIT = re.compile(r"(?<=[.!?\u2026])\s+")


def chunk_text(text, lang):
    """sentences -> token-id chunks, each under MAX_TOKENS."""
    sentences = [s for s in _SENT_SPLIT.split(text.strip()) if s]
    chunks, current = [], []
    for sent in sentences:
        ids = phonemes_to_ids(sent, lang)
        while len(ids) > MAX_TOKENS - 2:          # pathological run-on
            chunks.append(ids[:MAX_TOKENS - 2])
            ids = ids[MAX_TOKENS - 2:]
        if len(current) + len(ids) + 1 > MAX_TOKENS - 2:
            if current:
                chunks.append(current)
            current = list(ids)
        else:
            current = current + ([VOCAB[" "]] if current else []) + ids
    if current:
        chunks.append(current)
    return chunks


# ----------------------------------------------------------------------
# backends
# ----------------------------------------------------------------------

class OrtCpuBackend:
    name = "ort-cpu"

    def __init__(self, model_path):
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.log_severity_level = 3
        self.sess = ort.InferenceSession(
            model_path, sess_options=so, providers=["CPUExecutionProvider"])

    def infer(self, tokens, style, speed):
        return self.sess.run(None, {
            "tokens": tokens, "style": style, "speed": speed})[0]


class OvBackend:
    """OpenVINO direct runtime. Compiles per padded bucket length and
    caches compiled models in-process (plus OV CACHE_DIR on disk)."""

    def __init__(self, model_path, device, precision, cache_dir):
        import openvino as ov
        self.ov = ov
        self.core = ov.Core()
        self.model_path = model_path
        self.device = device
        self.precision = precision
        self.cache_dir = cache_dir
        self.name = f"ov-{device.lower()}"
        self._compiled = {}     # bucket -> (compiled, infer_request)

    def _bucket(self, n):
        for b in PAD_BUCKETS:
            if n <= b:
                return b
        return PAD_BUCKETS[-1]

    def _get(self, bucket):
        if bucket in self._compiled:
            return self._compiled[bucket]
        ov = self.ov
        model = self.core.read_model(self.model_path)
        want = {"tokens": ov.PartialShape([1, bucket]),
                "style": ov.PartialShape([1, 256]),
                "speed": ov.PartialShape([1])}
        reshape_map = {}
        for inp in model.inputs:
            for key, psh in want.items():
                if key in inp.get_names() or inp.any_name == key:
                    reshape_map[inp.any_name] = psh
        model.reshape(reshape_map)
        config = {"PERFORMANCE_HINT": "LATENCY",
                  "INFERENCE_PRECISION_HINT": self.precision}
        if self.cache_dir:
            config["CACHE_DIR"] = self.cache_dir
        t0 = time.time()
        compiled = self.core.compile_model(model, self.device, config)
        print(f"[{self.name}] compiled bucket={bucket} "
              f"in {time.time()-t0:.1f}s", flush=True)
        pair = (compiled, compiled.create_infer_request())
        self._compiled[bucket] = pair
        return pair

    def infer(self, tokens, style, speed):
        n = tokens.shape[1]
        bucket = self._bucket(n)
        if n < bucket:  # pad with pad-token 0; trailing pads add near-silence
            tokens = np.pad(tokens, ((0, 0), (0, bucket - n)))
        _, req = self._get(bucket)
        result = req.infer({"tokens": tokens, "style": style, "speed": speed})
        return list(result.values())[0]


def make_backend(name):
    if name == "ort-cpu":
        return OrtCpuBackend(MODEL_PATH)
    if name == "ov-cpu":
        return OvBackend(MODEL_PATH, "CPU", "f32", CACHE_DIR)
    if name == "ov-gpu":
        return OvBackend(MODEL_PATH, "GPU", GPU_PRECISION, CACHE_DIR)
    raise ValueError(f"unknown backend {name!r}")


# ----------------------------------------------------------------------
# synthesis
# ----------------------------------------------------------------------

_VOICES = None


def voices():
    global _VOICES
    if _VOICES is None:
        _VOICES = np.load(VOICES_PATH)
    return _VOICES


# Common leftover / alternate names from older Kokoro-FastAPI installs.
VOICE_ALIASES = {
    "bf_v0isabella": "bf_isabella",
    "bf_v0emma": "bf_emma",
    "bf_v0alice": "bf_alice",
    "bf_v0lily": "bf_lily",
    "af_v0bella": "af_bella",
    "af_v0sarah": "af_sarah",
    "af_v0nicole": "af_nicole",
    "af_v0sky": "af_sky",
    "am_v0adam": "am_adam",
    "am_v0michael": "am_michael",
    "bm_v0george": "bm_george",
    "bm_v0lewis": "bm_lewis",
}


def _canon_voice_token(token):
    token = (token or "").strip()
    if not token:
        return None
    token = OPENAI_VOICE_MAP.get(token, token)
    token = VOICE_ALIASES.get(token, token)
    if token not in voices() and "_v0" in token:
        alt = token.replace("_v0", "_", 1)
        if alt in voices():
            token = alt
    return token if token in voices() else None


_BLEND_PART = re.compile(
    r"^\s*([A-Za-z0-9_]+)(?:\s*\(\s*([0-9]*\.?[0-9]+)\s*\))?\s*$")


def parse_voice_spec(spec):
    """Parse plain voice or Kokoro-FastAPI blend: a(1)+b(2)+c."""
    spec = (spec or DEFAULT_VOICE).strip()
    if not spec:
        spec = DEFAULT_VOICE
    single = _canon_voice_token(spec)
    if single is not None and "+" not in spec:
        return [(single, 1.0)], single
    parts = []
    for raw in spec.split("+"):
        m = _BLEND_PART.match(raw)
        if not m:
            return None
        name = _canon_voice_token(m.group(1))
        if name is None:
            return None
        w = float(m.group(2)) if m.group(2) is not None else 1.0
        if w < 0:
            return None
        parts.append((name, w))
    if not parts:
        return None
    total = sum(w for _, w in parts)
    if total <= 0:
        return None
    parts = [(n, w / total) for n, w in parts]
    label = "+".join(f"{n}({w:g})" for n, w in parts)
    return parts, label


def resolve_voice(name):
    parsed = parse_voice_spec(name)
    if not parsed:
        return None
    parts, _ = parsed
    if len(parts) == 1:
        return parts[0][0]
    return parts


def style_for_parts(parts, n_tokens):
    acc = None
    for vname, w in parts:
        ref = voices()[vname]
        row = ref[min(n_tokens, ref.shape[0] - 1)].astype(np.float32)
        acc = row * w if acc is None else acc + row * w
    return acc.reshape(1, 256)


def synthesize(backend, text, voice_spec, speed):
    parsed = parse_voice_spec(voice_spec)
    if not parsed:
        return None, 0, None
    parts, label = parsed
    primary = parts[0][0]
    lang = "en-gb" if primary.startswith(("bf_", "bm_")) else "en-us"
    chunks = chunk_text(text, lang)
    if not chunks:
        return np.zeros(0, dtype=np.float32), 0, label
    gap = np.zeros(int(SR * CHUNK_GAP_S), dtype=np.float32)
    pieces = []
    total_tokens = 0
    for ids in chunks:
        total_tokens += len(ids)
        style = style_for_parts(parts, len(ids))
        tokens = np.array([[0, *ids, 0]], dtype=np.int64)
        audio = np.asarray(backend.infer(
            tokens, style, np.array([speed], dtype=np.float32))).reshape(-1)
        pieces.append(np.nan_to_num(audio.astype(np.float32)))
        pieces.append(gap)
    if pieces:
        pieces = pieces[:-1]
    audio = np.concatenate(pieces) if pieces else np.zeros(0, np.float32)
    return audio, total_tokens, label


def to_wav_bytes(audio):
    a = np.clip(audio, -1.0, 1.0)
    pcm = (a * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def transcode(wav_bytes, fmt):
    """wav -> mp3/opus/flac via ffmpeg if available; else None."""
    if shutil.which("ffmpeg") is None:
        return None
    codec = {"mp3": ["-f", "mp3"], "opus": ["-f", "opus"],
             "flac": ["-f", "flac"], "aac": ["-f", "adts"]}.get(fmt)
    if codec is None:
        return None
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", "pipe:0", *codec, "pipe:1"],
        input=wav_bytes, capture_output=True)
    return p.stdout if p.returncode == 0 and p.stdout else None


# ----------------------------------------------------------------------
# app
# ----------------------------------------------------------------------

def build_app():
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import Response
    from pydantic import BaseModel

    app = FastAPI(title="Kokoro TTS (intel-igpu-tts)", version="1.0")
    state = {"backend": None}

    class SpeechRequest(BaseModel):
        # Open WebUI / Kokoro-FastAPI may send extra keys; ignore unknowns.
        model_config = {"extra": "ignore"}

        input: str
        model: str = "kokoro"
        voice: str = DEFAULT_VOICE
        response_format: str = "wav"
        speed: float = 1.0

    @app.on_event("startup")
    def _startup():
        print(f"[server] model={MODEL_PATH}")
        print(f"[server] voices={VOICES_PATH}")
        print(f"[server] backend={BACKEND}"
              + (f" precision={GPU_PRECISION}" if BACKEND == "ov-gpu" else ""))
        state["backend"] = make_backend(BACKEND)
        # warm the default path so first request isn't cold
        try:
            synthesize(state["backend"], "Warm up.", DEFAULT_VOICE, 1.0)
            print("[server] warmup OK")
        except Exception as e:
            print(f"[server] warmup failed: {e}")

    @app.get("/health")
    def health():
        return {"status": "ok", "backend": BACKEND, "model": MODEL_PATH,
                "gpu_precision": GPU_PRECISION if BACKEND == "ov-gpu" else None}

    @app.get("/v1/models")
    def models():
        return {"object": "list", "data": [
            {"id": "kokoro", "object": "model", "owned_by": "local"},
            {"id": "tts-1", "object": "model", "owned_by": "local"},
        ]}

    @app.get("/v1/audio/voices")
    def list_voices():
        return {"voices": sorted(list(voices().keys())),
                "openai_aliases": OPENAI_VOICE_MAP,
                "default": DEFAULT_VOICE}

    @app.post("/v1/audio/speech")
    def speech(req: SpeechRequest):
        if not req.input or not req.input.strip():
            raise HTTPException(400, "empty input")
        if parse_voice_spec(req.voice) is None:
            raise HTTPException(400, f"unknown voice {req.voice!r}; "
                                     f"see /v1/audio/voices "
                                     f"(blends like a(1)+b(2) supported)")
        speed = float(np.clip(req.speed, 0.5, 2.0))
        t0 = time.time()
        audio, n_tokens, voice_label = synthesize(
            state["backend"], req.input, req.voice, speed)
        infer_s = time.time() - t0
        if audio is None:
            raise HTTPException(400, f"unknown voice {req.voice!r}")
        if audio.size == 0:
            raise HTTPException(400, "no synthesizable content")
        dur = audio.size / SR
        print(f"[speech] voice={voice_label} tokens={n_tokens} "
              f"audio={dur:.2f}s infer={infer_s:.2f}s "
              f"rtf={infer_s/max(dur,1e-6):.2f}", flush=True)

        wav_bytes = to_wav_bytes(audio)
        fmt = req.response_format.lower()
        headers = {"X-Kokoro-Backend": BACKEND,
                   "X-Kokoro-RTF": f"{infer_s/max(dur,1e-6):.2f}",
                   "X-Kokoro-Format": "wav"}
        if fmt in ("wav", "pcm", ""):
            return Response(wav_bytes, media_type="audio/wav", headers=headers)
        enc = transcode(wav_bytes, fmt)
        if enc is None:
            # graceful fallback: wav with header note
            return Response(wav_bytes, media_type="audio/wav", headers=headers)
        headers["X-Kokoro-Format"] = fmt
        media = {"mp3": "audio/mpeg", "opus": "audio/ogg",
                 "flac": "audio/flac", "aac": "audio/aac"}[fmt]
        return Response(enc, media_type=media, headers=headers)

    return app


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8880)
    args = ap.parse_args()
    import uvicorn
    uvicorn.run(build_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
