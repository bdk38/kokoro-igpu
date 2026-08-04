#!/usr/bin/env python3
"""
tts_harness.py — real-text A/B harness for patched Kokoro across backends.

Pipeline: text -> espeak-ng phonemes -> Kokoro v0.19 token ids -> identical
feeds through each requested backend -> side-by-side WAVs + timings + RTF +
rough mel-spectrogram distance vs the reference backend.

Backends:
  ort-cpu   onnxruntime CPUExecutionProvider (reference)
  ov-cpu    OpenVINO runtime, whole-graph, CPU
  ov-gpu    OpenVINO runtime, whole-graph, GPU (real iGPU offload)

Prereqs (in the venv):
  sudo apt install espeak-ng
  pip install phonemizer
  # optional gold path: pip install kokoro-onnx (harness auto-uses its
  # tokenizer if importable; otherwise falls back to the vendored one)

Usage:
  python scripts/tts_harness.py \
      --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
      --voices models/voices-v1.0.bin \
      --voice af_bella \
      --text "The quick brown fox jumps over the lazy dog." \
      --backends ort-cpu,ov-cpu,ov-gpu \
      --gpu-precision f32 \
      --cache cache/openvino \
      --outdir artifacts/harness

Notes:
  - mel distance is a ROUGH indicator: backends may emit different frame
    counts (duration rounding), so frames are truncated to the shorter run.
    Ears remain the final gate; this number just tracks relative drift.
  - OV GPU compiles per token-length shape; first run for a new length is
    slow, cache makes repeats fast.
"""

import argparse
import os
import re
import sys
import time
import wave

import numpy as np

SR = 24000
MAX_TOKENS = 510


# ----------------------------------------------------------------------
# tokenizer (kokoro v0.19)
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


def _cleanup_phonemes(ps, lang):
    # kokoro v0.19 post-espeak normalization
    ps = ps.replace("k\u0259k\u02c8o\u02d0\u0279o\u028a", "k\u02c8o\u028ak\u0259\u0279o\u028a")
    ps = ps.replace("k\u0259k\u02c8\u0254\u02d0\u0279\u0259\u028a", "k\u02c8\u0259\u028ak\u0259\u0279\u0259\u028a")
    ps = ps.replace("\u02b2", "j").replace("r", "\u0279")
    ps = ps.replace("x", "k").replace("\u026c", "l")
    ps = re.sub(r"(?<=[a-z\u0279\u02d0])(?=h\u02c8\u028cnd\u0279\u026ad)", " ", ps)
    ps = re.sub(r" z(?=[;:,.!?\u00a1\u00bf\u2014\u2026\"\u00ab\u00bb\u201c\u201d ]|$)", "z", ps)
    if lang == "en-us":
        ps = re.sub(r"(?<=n\u02c8a\u026an)ti(?!\u02d0)", "di", ps)
    return ps


def phonemize_text(text, lang):
    """text -> filtered phoneme string. Tries kokoro-onnx first, then
    phonemizer/espeak with the vendored cleanup."""
    try:
        from kokoro_onnx.tokenizer import Tokenizer  # gold path if present
        tk = Tokenizer()
        ps = tk.phonemize(text, lang="en-us" if lang == "en-us" else "en-gb")
        print("[tokenizer] using kokoro-onnx Tokenizer")
        return ps
    except Exception:
        pass

    from phonemizer.backend import EspeakBackend
    backend = EspeakBackend(
        language=lang, preserve_punctuation=True, with_stress=True)
    ps = backend.phonemize([text])
    ps = ps[0].strip() if ps else ""
    ps = _cleanup_phonemes(ps, lang)
    print("[tokenizer] using phonemizer/espeak-ng (vendored cleanup)")
    return ps


def tokenize(text, voice):
    lang = "en-gb" if voice.startswith(("bf_", "bm_")) else "en-us"
    ps = phonemize_text(text, lang)
    dropped = sorted({c for c in ps if c not in VOCAB})
    if dropped:
        print(f"[tokenizer] dropped {len(dropped)} symbol(s) not in vocab: "
              f"{dropped}")
    ids = [VOCAB[c] for c in ps if c in VOCAB]
    if len(ids) > MAX_TOKENS:
        print(f"[tokenizer] WARNING: {len(ids)} tokens > {MAX_TOKENS}, truncating")
        ids = ids[:MAX_TOKENS]
    print(f"[tokenizer] phonemes ({len(ids)} tokens): {ps[:120]}"
          f"{'...' if len(ps) > 120 else ''}")
    return ids


# ----------------------------------------------------------------------
# feeds
# ----------------------------------------------------------------------

def make_feeds(voices_path, voice, ids, speed):
    voices = np.load(voices_path)
    if voice not in voices:
        print(f"voice '{voice}' not found; available: "
              f"{list(voices.keys())[:10]}...", file=sys.stderr)
        sys.exit(2)
    ref = voices[voice]                               # (510, 1, 256)
    style = ref[min(len(ids), ref.shape[0] - 1)].reshape(1, 256).astype(np.float32)
    tokens = np.array([[0, *ids, 0]], dtype=np.int64)  # pad token 0 both ends
    return {
        "tokens": tokens,
        "style": style,
        "speed": np.array([speed], dtype=np.float32),
    }


# ----------------------------------------------------------------------
# backends
# ----------------------------------------------------------------------

def run_ort_cpu(model_path, feeds, runs):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.log_severity_level = 3
    t0 = time.time()
    sess = ort.InferenceSession(model_path, sess_options=so,
                                providers=["CPUExecutionProvider"])
    print(f"[ort-cpu] session in {time.time()-t0:.2f}s")
    out, times = None, []
    for _ in range(runs):
        t = time.time()
        out = sess.run(None, feeds)[0]
        times.append(time.time() - t)
    return np.asarray(out).reshape(-1), times


def run_ov(model_path, feeds, runs, device, precision, cache):
    import openvino as ov
    core = ov.Core()
    t0 = time.time()
    model = core.read_model(model_path)
    n = feeds["tokens"].shape[1]
    reshape_map = {}
    want = {"tokens": ov.PartialShape([1, n]),
            "style": ov.PartialShape([1, 256]),
            "speed": ov.PartialShape([1])}
    for inp in model.inputs:
        for key, psh in want.items():
            if key in inp.get_names() or inp.any_name == key:
                reshape_map[inp.any_name] = psh
    model.reshape(reshape_map)
    config = {"PERFORMANCE_HINT": "LATENCY",
              "INFERENCE_PRECISION_HINT": precision}
    if cache:
        config["CACHE_DIR"] = cache
    compiled = core.compile_model(model, device, config)
    print(f"[ov-{device.lower()}] compile in {time.time()-t0:.2f}s "
          f"(precision={precision}, static n={n})")
    try:
        print(f"[ov-{device.lower()}] execution devices: "
              f"{compiled.get_property('EXECUTION_DEVICES')}")
    except Exception:
        pass
    infer = compiled.create_infer_request()
    out, times = None, []
    for _ in range(runs):
        t = time.time()
        result = infer.infer(feeds)
        times.append(time.time() - t)
        out = list(result.values())[0]
    return np.asarray(out).reshape(-1), times


# ----------------------------------------------------------------------
# mel-spectrogram distance (numpy only, rough indicator)
# ----------------------------------------------------------------------

def _mel_filterbank(sr, n_fft, n_mels=80, fmin=0.0, fmax=12000.0):
    def hz_to_mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel_to_hz(m):
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    mels = np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2)
    hz = mel_to_hz(mels)
    bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for i in range(n_mels):
        l, c, r = bins[i], bins[i + 1], bins[i + 2]
        if c > l:
            fb[i, l:c] = (np.arange(l, c) - l) / (c - l)
        if r > c:
            fb[i, c:r] = (r - np.arange(c, r)) / (r - c)
    return fb


def log_mel(audio, n_fft=1024, hop=256):
    a = np.nan_to_num(np.asarray(audio, dtype=np.float64))
    if a.size < n_fft:
        a = np.pad(a, (0, n_fft - a.size))
    n_frames = 1 + (a.size - n_fft) // hop
    win = np.hanning(n_fft)
    frames = np.stack([a[i * hop:i * hop + n_fft] * win
                       for i in range(n_frames)])
    spec = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    mel = spec @ _mel_filterbank(SR, n_fft).T
    return np.log10(np.maximum(mel, 1e-10))


def mel_distance(a, b):
    ma, mb = log_mel(a), log_mel(b)
    n = min(ma.shape[0], mb.shape[0])
    d = float(np.mean(np.abs(ma[:n] - mb[:n])))
    return d, ma.shape[0], mb.shape[0]


# ----------------------------------------------------------------------
# output
# ----------------------------------------------------------------------

def write_wav(path, audio):
    a = np.nan_to_num(np.asarray(audio).reshape(-1), nan=0.0)
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--voice", default="af_bella")
    ap.add_argument("--text", required=True)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--backends", default="ort-cpu,ov-cpu,ov-gpu",
                    help="comma list of: ort-cpu, ov-cpu, ov-gpu")
    ap.add_argument("--gpu-precision", default="f32", choices=["f32", "f16"])
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--outdir", default="artifacts/harness")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    ids = tokenize(args.text, args.voice)
    if not ids:
        print("no tokens produced from text", file=sys.stderr)
        sys.exit(2)
    feeds = make_feeds(args.voices, args.voice, ids, args.speed)
    print(f"[feeds] tokens={feeds['tokens'].shape} voice={args.voice}")

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    results = {}
    for b in backends:
        print(f"\n----- backend: {b} -----")
        try:
            if b == "ort-cpu":
                audio, times = run_ort_cpu(args.model, feeds, args.runs)
            elif b == "ov-cpu":
                audio, times = run_ov(args.model, feeds, args.runs,
                                      "CPU", "f32", args.cache)
            elif b == "ov-gpu":
                audio, times = run_ov(args.model, feeds, args.runs,
                                      "GPU", args.gpu_precision, args.cache)
            else:
                print(f"unknown backend {b}, skipping")
                continue
        except Exception as e:
            print(f"[{b}] FAILED: {type(e).__name__}: {e}")
            continue
        dur = audio.size / SR
        mean_t = float(np.mean(times))
        results[b] = {"audio": audio, "mean_t": mean_t, "dur": dur}
        tag = b.replace("-", "_")
        path = os.path.join(args.outdir, f"{tag}.wav")
        write_wav(path, audio)
        print(f"[{b}] samples={audio.size} dur={dur:.2f}s "
              f"mean_infer={mean_t:.3f}s RTF={mean_t/dur:.3f} -> {path}")

    if not results:
        sys.exit(1)

    ref_name = "ort-cpu" if "ort-cpu" in results else list(results)[0]
    ref = results[ref_name]["audio"]
    print(f"\n===== SUMMARY (reference: {ref_name}) =====")
    print(f"text: {args.text!r}")
    print(f"{'backend':<10} {'infer_s':>8} {'audio_s':>8} {'RTF':>6} "
          f"{'mel_L1':>8} {'frames':>12}")
    for b, r in results.items():
        if b == ref_name:
            print(f"{b:<10} {r['mean_t']:>8.3f} {r['dur']:>8.2f} "
                  f"{r['mean_t']/r['dur']:>6.3f} {'ref':>8} {'-':>12}")
        else:
            d, fa, fb = mel_distance(ref, r["audio"])
            print(f"{b:<10} {r['mean_t']:>8.3f} {r['dur']:>8.2f} "
                  f"{r['mean_t']/r['dur']:>6.3f} {d:>8.4f} {f'{fb}vs{fa}':>12}")
    print("\nmel_L1 guide: <0.05 near-identical | 0.05-0.15 audible-but-same-"
          "speech | >0.3 investigate. Rough metric — ears are the gate.")


if __name__ == "__main__":
    main()
