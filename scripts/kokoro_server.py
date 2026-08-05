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
  KOKORO_WARM_BUCKETS   comma list of token buckets to pre-warm at startup
                    on OV backends, e.g. "96,192". First infer per
                    compiled bucket costs multi-second lazy GPU setup
                    (measured cold ~4-5x realtime vs warm steady ~0.9 at
                    bucket 96; notes/18); pre-warming moves that cost to
                    startup so the first user request per bucket is fast.
                    Uses real-text synthesize (not all-zero pads — zeros
                    do not warm the production path). Cache dir shortens
                    compile, NOT first-infer setup.
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
  Response Splitting: depends on backend (see notes/15):
    ort-cpu (RTF ~0.4)  -> Punctuation is fine and gives fast first-audio
    ov-gpu  (RTF 4-6)   -> use None or Paragraphs. Punctuation fires one
      slow request per sentence; the client can drop late segments and
      Read Aloud skips mid-passage. Confirmed by A/B with identical
      server build (notes/15-webui-response-splitting.md).

Notes:
  - Long input is chunked at sentence boundaries to stay under the model's
    510-token limit; chunks are stitched with a short gap.
  - OV backends compile per token-length; the server pads chunk tokens to
    bucket sizes (96/192/288/384/512) and caches compiled models per
    bucket, so steady-state requests reuse compiles. ORT is fully dynamic.
  - The NSF vocoder renders trailing pad tokens as a short breath-like
    burst after a quiet gap at chunk ends. OV-path chunks are therefore
    trimmed after inference: audio is segmented into gap-separated speech
    groups, and trailing groups are stripped only if they look like pad
    energy (gap-separated AND weak AND short). Natural mid-sentence
    pauses never trigger a cut because the speech that follows them fails
    the weak/short tests. Always on; fails safe (keeps audio when in
    doubt). ORT path never pads, so it is never trimmed.
    Set KOKORO_TRIM_DEBUG=1 to log per-chunk trim decisions.
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
import threading
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

# pad-tail trim (OV bucket-padded chunks only)
TRIM_FRAME_S = 0.02        # RMS analysis frame (20 ms)
TRIM_MARGIN_S = 0.03       # keep this much after the last speech frame
TRIM_FADE_S = 0.01         # fade length at the cut
TRIM_SEARCH_FACTOR = 1.5   # search window = pad fraction x this
TRIM_RMS_RATIO = 0.15      # frame counts as speech at >= 15% of ref RMS
TRIM_QUIET_S = 0.10        # gap length separating speech groups
TRIM_MOAN_MAX_S = 0.6      # pad burst must be shorter than this
                           # (measured ov-gpu bursts: 0.22-0.40 s)
TRIM_MOAN_RMS_RATIO = 0.9  # pad burst peak must stay below this x ref RMS
                           # (measured ov-gpu bursts: 0.64-0.83x ref;
                           # measured real continuation speech: ~1.39x)
TRIM_PAD_GAP_S = 0.15      # burst must be detached: gap before it >= this
                           # (measured: intra-word stop closure ~0.10 s,
                           # pre-moan pad gaps 0.46-0.48 s)
TRIM_REF_FLOOR = 1e-3      # refuse to trim when speech reference RMS is
                           # this low (silence-referenced clip)
TRIM_DEBUG = os.environ.get("KOKORO_TRIM_DEBUG", "0") == "1"


MODEL_PATH = os.environ.get(
    "KOKORO_MODEL", "/data/intel-igpu-tts/models/kokoro-v0_19.onnx")
VOICES_PATH = os.environ.get(
    "KOKORO_VOICES", "/data/intel-igpu-tts/models/voices-v1.0.bin")
BACKEND = os.environ.get("KOKORO_BACKEND", "ort-cpu")
GPU_PRECISION = os.environ.get("KOKORO_GPU_PRECISION", "f32")
CACHE_DIR = os.environ.get(
    "KOKORO_CACHE", "/data/intel-igpu-tts/cache/openvino")
DEFAULT_VOICE = os.environ.get("KOKORO_DEFAULT_VOICE", "af_bella")
WARM_BUCKETS = [int(x) for x in
                os.environ.get("KOKORO_WARM_BUCKETS", "").split(",")
                if x.strip().isdigit()]

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
# pad-tail trim
# ----------------------------------------------------------------------

def trim_pad_tail(audio, n_real, n_bucket, sr=SR):
    """Remove the voiced tail the vocoder synthesizes from bucket pad tokens.

    Measured failure shape (see 10-status-trim-and-skips.md):

        real speech -> short quiet gap -> weak voiced burst (moan) -> silence

    v1.1.1 cut at the *first* sustained quiet and fired on comma pauses.
    v1.1.2/3 segmented into speech groups but a soft word-final syllable
    after a stop-closure gap ("pass^port") matched the weak+short profile
    of a moan, and a leading-silence head broke the reference RMS.

    A trailing group is stripped only when it passes ALL of:

      1. weak:     peak RMS < TRIM_MOAN_RMS_RATIO x speech reference
                   (measured moans 0.23-0.77x; real speech >= 1.05x)
      2. short:    duration < TRIM_MOAN_MAX_S (moans 0.12-0.40 s)
      3. detached: gap before it >= TRIM_PAD_GAP_S (a stop-closure gap
                   ~0.10 s keeps word-final syllables attached; pad gaps
                   measure 0.40-0.78 s)
      4. in the pad search window (head is sacred)

    A terminal-silence gate existed in v1.1.4 and was removed: across the
    full probe set every group it kept was an ear-confirmed pad moan and
    it never protected real speech (Kokoro renders final words attached
    to preceding speech, not detached). Tail length is still logged as
    data in case a weak+short+detached real word ever appears.

    The speech reference is the p90 of frames at >= 10% of the clip's max
    frame RMS (not a positional head, which can be leading silence), with
    a hard floor below which trimming is refused. If no group qualifies,
    only trailing silence after the last group is trimmed. No confident
    structure -> audio returned unchanged.
    """
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if n_bucket <= n_real or audio.size == 0:
        return audio
    pad_frac = (n_bucket - n_real) / float(n_bucket)
    search = int(audio.size * min(1.0, pad_frac * TRIM_SEARCH_FACTOR))
    frame = max(1, int(sr * TRIM_FRAME_S))
    # always keep a head region as the speech-RMS reference, even when the
    # pad fraction is large (short sentence in a big bucket)
    ref_min = min(audio.size // 2, max(frame * 5, int(sr * 0.2)))
    keep_min = max(audio.size - search, ref_min)  # never cut before this
    if audio.size - keep_min < frame or keep_min < frame:
        return audio

    n_fr = audio.size // frame
    if n_fr < 3:
        return audio
    rms = np.sqrt(np.mean(
        audio[:n_fr * frame].reshape(-1, frame).astype(np.float64) ** 2,
        axis=1))

    # speech reference from the loudest material anywhere in the clip;
    # a positional head window can be leading silence (whisper probe:
    # ref collapsed to 2e-4 and every ratio went nonsensical)
    loud = rms[rms >= 0.1 * float(rms.max())]
    ref = float(np.percentile(loud, 90)) if loud.size else 0.0
    if ref < TRIM_REF_FLOOR:
        return audio
    thresh = ref * TRIM_RMS_RATIO

    speech_idx = np.nonzero(rms >= thresh)[0]
    if speech_idx.size == 0:
        return audio

    # merge speech frames into groups; gaps shorter than TRIM_QUIET_S do
    # not separate groups (they are intra-speech texture, not structure)
    need = max(2, int(round(TRIM_QUIET_S / TRIM_FRAME_S)))
    groups = []                     # (start_frame, end_frame_exclusive)
    g_start = prev = int(speech_idx[0])
    for j in speech_idx[1:]:
        j = int(j)
        if j - prev - 1 >= need:
            groups.append((g_start, prev + 1))
            g_start = j
        prev = j
    groups.append((g_start, prev + 1))

    moan_max = max(1, int(round(TRIM_MOAN_MAX_S / TRIM_FRAME_S)))
    burst_lvl = ref * TRIM_MOAN_RMS_RATIO

    pad_gap = max(1, int(round(TRIM_PAD_GAP_S / TRIM_FRAME_S)))

    end_f = groups[-1][1]
    gi = len(groups) - 1
    stripped = 0
    while gi > 0:
        s, e = groups[gi]
        peak = float(rms[s:e].max())
        gap_before = s - groups[gi - 1][1]
        after = (groups[gi + 1][0] if gi + 1 < len(groups) else n_fr) - e
        if s * frame < keep_min:
            verdict = "kept:in-head"
        elif (e - s) > moan_max:
            verdict = "kept:too-long"
        elif peak >= burst_lvl:
            verdict = "kept:too-loud"
        elif gap_before < pad_gap:
            verdict = "kept:attached"
        else:
            verdict = "stripped"
        if TRIM_DEBUG:
            print(f"[trim]   g{gi}: {s * frame / sr:.2f}-{e * frame / sr:.2f}s "
                  f"dur={(e - s) * frame / sr:.2f}s peak/ref={peak / ref:.2f} "
                  f"gap={gap_before * frame / sr:.2f}s "
                  f"tail={after * frame / sr:.2f}s -> {verdict}", flush=True)
        if verdict != "stripped":
            break
        gi -= 1
        end_f = groups[gi][1]
        stripped += 1

    cut = min(audio.size, end_f * frame + int(sr * TRIM_MARGIN_S))
    if TRIM_DEBUG:
        print(f"[trim] n_real={n_real} n_bucket={n_bucket} "
              f"audio={audio.size / sr:.2f}s groups={len(groups)} "
              f"stripped={stripped} cut={cut / sr:.2f}s "
              f"ref={ref:.4f} thresh={thresh:.4f}", flush=True)
    if cut >= audio.size:
        return audio

    out = audio[:cut].copy()
    fade = min(int(sr * TRIM_FADE_S), out.size)
    if fade > 0:
        out[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return out


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
        print(f"[{{}}] openvino={{}}".format(
            f"ov-{device.lower()}", ov.get_version()), flush=True)
        self.model_path = model_path
        self.device = device
        self.precision = precision
        self.cache_dir = cache_dir
        self.name = f"ov-{device.lower()}"
        self._compiled = {}     # bucket -> (compiled, infer_request)
        # one infer request per bucket + FastAPI thread pool = "Infer
        # Request is busy" under concurrent posts; serialize infers (the
        # device serializes anyway) and protect compile-dict updates
        self._lock = threading.Lock()

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
        padded = n < bucket
        if padded:  # pad with pad-token 0; the vocoder voices these -> trim
            tokens = np.pad(tokens, ((0, 0), (0, bucket - n)))
        with self._lock:
            _, req = self._get(bucket)
            result = req.infer(
                {"tokens": tokens, "style": style, "speed": speed})
        audio = np.asarray(list(result.values())[0]).reshape(-1)
        if padded:
            audio = trim_pad_tail(audio, n, bucket)
        return audio


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

    app = FastAPI(title="Kokoro TTS (intel-igpu-tts)", version="1.1.6")
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
            # optional bucket pre-warm (OV only): eat the multi-second
            # first-infer lazy setup per bucket at startup, not on the
            # first user request of that length (notes/18)
            be = state["backend"]
            if WARM_BUCKETS and hasattr(be, "_bucket"):
                # IMPORTANT: all-zero (pad) tokens do NOT retire the same
                # lazy GPU setup as real phoneme content. Measured on
                # Alder Lake UHD: zeros pre-warm ~31s still left the first
                # fox request at ~18s RTF; real-text synthesize warm makes
                # first user request ~steady (~0.9 RTF at bucket 96).
                warm_text = {
                    96: "The quick brown fox jumps over the lazy dog.",
                    192: ("The quick brown fox jumps over the lazy dog. "
                          "Pack my box with five dozen liquor jugs. "),
                    288: ("The quick brown fox jumps over the lazy dog. "
                          "Pack my box with five dozen liquor jugs. "
                          "How vexingly quick daft zebras jump. "),
                    384: ("The quick brown fox jumps over the lazy dog. "
                          "Pack my box with five dozen liquor jugs. "
                          "How vexingly quick daft zebras jump. "
                          "Sphinx of black quartz, judge my vow. "),
                    512: ("The quick brown fox jumps over the lazy dog. "
                          "Pack my box with five dozen liquor jugs. "
                          "How vexingly quick daft zebras jump. "
                          "Sphinx of black quartz, judge my vow. "
                          "The five boxing wizards jump quickly. "),
                }
                for b in WARM_BUCKETS:
                    target = be._bucket(int(b))
                    text = warm_text.get(
                        target,
                        "The quick brown fox jumps over the lazy dog. " * max(
                            1, target // 40))
                    t0 = time.time()
                    synthesize(be, text, DEFAULT_VOICE, 1.0)
                    print(f"[server] pre-warmed bucket~{target} "
                          f"via synthesize in {time.time() - t0:.1f}s",
                          flush=True)
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