<!--
SUBMIT READY — github.com/openvinotoolkit/openvino/issues
Labels (suggested): bug, category: GPU
VERIFY: 2026-08-08 Grok — all numbers from s0_5_result.json + i0_3_result.json on bdk-server
Attachments folder: issues/submit/attachments/
-->

# Title

```
[GPU] Shape-keyed kernel JIT causes ~17–30 s first-inference stall per novel tensor shape on Xe-LP iGPU; not covered by CACHE_DIR; reproduces on official Kokoro-82M GenAI pack (2026.3.0)
```

# Body (paste below)

### Summary

On Intel Xe-LP integrated graphics (Alder Lake-U UHD, 64 EU), the GPU plugin appears to JIT-compile kernels keyed on **exact internal tensor shapes**. For variable-output-length workloads (TTS), every novel output length triggers a host-side stall of **~17–30 s** on first inference of that shape, while **repeat shapes** run at realtime RTF. `CACHE_DIR` shortens model-level compile but does **not** eliminate the per-novel-shape first-infer tax.

This reproduces on the **official** Hugging Face pack `OpenVINO/kokoro-82M-int8-ov` via `openvino_genai.Text2SpeechPipeline` on OpenVINO **2026.3.0** / GenAI **2026.3.0.0** — i.e. the advertised Kokoro GPU path — not only third-party ONNX exports.

### Environment

| Item | Value |
|------|-------|
| OpenVINO | `2026.3.0-22451-8a17657b995-releases/2026/3` |
| openvino-genai | `2026.3.0.0-3277-bd8d6542e3c` |
| Model | `OpenVINO/kokoro-82M-int8-ov` (HF), voice `af_heart` / `af_bella` |
| Device | GPU — Intel UHD Graphics Xe-LP 64 EU, i3-1215U, PCI **8086:46b3** |
| Driver | intel-opencl-icd **26.22.38646.7** · IGC **2.36.5** · kernel **7.0.0-28-generic** |
| OS / Python | Ubuntu 24.04.4 LTS · Python 3.12.3 |

Same shape-keyed behavior was also seen on OpenVINO **2026.2.1** with a community f32 Kokoro ONNX (17–25 s class per novel shape) across a driver upgrade — stable across 2026.2.1→2026.3.0.

### Steps to reproduce

```bash
# 1. Download official pack OpenVINO/kokoro-82M-int8-ov
# 2. pip install openvino==2026.3.0 openvino-genai==2026.3.0.0
python - <<'PY'
import time, numpy as np, openvino as ov, openvino_genai as og
from pathlib import Path
MODEL = Path("kokoro-82M-int8-ov")  # local path
pipe = og.Text2SpeechPipeline(str(MODEL), "GPU")
shape = tuple(pipe.get_speaker_embedding_shape())
emb = np.fromfile(MODEL/"voices/af_heart.bin", dtype=np.float32).reshape(shape)
speaker = ov.Tensor(emb)

def gen(text):
    t0 = time.time()
    r = pipe.generate(text, speaker, language="en-us")
    audio = np.array(r.speeches[0].data, dtype=np.float32).reshape(-1)
    return time.time()-t0, audio.size/24000

# warm fixed short text
for _ in range(4):
    print("warm", gen("The quick brown fox jumps over the lazy dog."))
# novel
t1,a1 = gen("Seven silver swans swam silently seaward past twelve bright blue boxes of old books.")
t2,a2 = gen("Seven silver swans swam silently seaward past twelve bright blue boxes of old books.")
print("novel first", t1, "second", t2, "delta", t1-t2)
PY
```

### Measured (this host)

**Direct GenAI GPU** (`s0_5_result.json`, voice af_heart, warmup discarded for steady means):

| Case | Wall | Audio | RTF / note |
|------|-----:|------:|------------|
| Steady short (fox, mean runs 1–4) | ~2.27 s | 3.25 s | **RTF 0.70** |
| Steady multi-sentence (mean runs 1–2) | ~9.79 s | 14.30 s | **RTF 0.69** |
| Novel #1 first → second | **30.43 s** → 4.21 s | 6.08 s | **Δ +26.2 s** |
| Novel #2 first → second | **27.26 s** → 3.70 s | 5.38 s | **Δ +23.6 s** |

**Served product path** (HTTP `Text2SpeechPipeline` behind our server, I0.3, cache off):

| Case | Wall | Δ |
|------|-----:|--:|
| Novel first → second | 33.34 s → 4.57 s | **+28.8 s** |

Steady-state is realtime-class; the penalty is **per novel shape**, not baseline GPU slowness.

### Expected

Either:
1. shape-specialized kernels persisted (e.g. via `CACHE_DIR` or a dedicated kernel cache) so a given shape compiles once per install, or  
2. a documented API to pre-compile / bucket shapes, or  
3. first-infer compile cost on this class of iGPU in the low seconds, not tens of seconds.

### Additional context

- Field report of a similar persistent kernel-cache fix on another stack: Kokoro-FastAPI discussion of AMD MIOpen disk kernel cache (community issue trackers; happy to cross-link).
- App mitigations (shape warm pins, response/chunk cache) help UX but should not be required for the officially supported Kokoro GPU path’s first novel utterance.
- Hardware available for diagnostics/builds on request.
- Full timing JSON: attach `s0_5_result.json`, `i0_3_result.json`, `stack_versions.json`.

### Related local project

Repro harness and notes: https://github.com/bdk38/kokoro-igpu (Intel iGPU Kokoro measurements).
