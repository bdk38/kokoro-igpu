# FILING DRAFT #1 — for github.com/openvinotoolkit/openvino/issues

**Repo:** openvinotoolkit/openvino · **Component:** GPU plugin
**Prepared:** 2026-08-08 · Fable draft for Grok evidence-attach + Nexus submit
**[VERIFY] markers = Grok confirms/fills from repo evidence before submit.**

---

## Title

`[GPU] Shape-keyed kernel JIT causes ~17–30 s first-inference stall per novel tensor shape on Xe-LP iGPU; not persisted by CACHE_DIR; reproduces on official Kokoro-82M pack (2026.3.0)`

## Body

### Summary

On Intel Xe-LP integrated graphics (Alder Lake-U, i3-1215U UHD, 64 EU), the GPU plugin JIT-compiles kernels keyed on **exact internal tensor shapes**. For variable-output-length workloads (TTS), every novel output sample count triggers a host-side compile of **~17–30 s** before first inference, while repeat shapes run fast. `CACHE_DIR` does not persist these shape-specialized kernels across novel shapes (partial blob-cache coverage of model-level compile only).

This reproduces on the **official `OpenVINO/kokoro-82M-int8-ov` pack via `openvino_genai.Text2SpeechPipeline`** on OpenVINO **2026.3.0** — the release whose notes list Kokoro-82M as an early release on CPU and GPU — so it directly affects the advertised Kokoro GPU path's cold/novel-text UX, not only third-party exports.

### Environment

| Item | Value |
|------|-------|
| OpenVINO | 2026.3.0-22451-8a17657b995-releases/2026/3 |
| openvino-genai | 2026.3.0.0-3277-bd8d6542e3c |
| Model | `OpenVINO/kokoro-82M-int8-ov` (HF), voice af_heart |
| Device | GPU (Intel UHD Graphics, Xe-LP 64 EU, i3-1215U, PCI 8086:46b3) |
| Driver | intel-opencl-icd 26.22.38646.7 · IGC 2.36.5 · kernel 7.0.0-28-generic |
| OS / Python | Ubuntu 24.04-class · Python 3.12.3 |

Also reproduced on OpenVINO **2026.2.1** with a community f32 Kokoro ONNX (same shape-keyed behavior, 17–25 s per novel shape), across an intermediate driver upgrade — behavior is stable across wheel 2026.2.1→2026.3.0 and two driver stacks.

### Steps to reproduce

1. Download `OpenVINO/kokoro-82M-int8-ov`; load `Text2SpeechPipeline(model_dir, "GPU")`.
2. Warm: generate one fixed short text 3–5× until wall time is steady.
3. Generate a **novel** text of a different length. Measure wall.
4. Repeat the same novel text. Measure wall.

### Measured (this host)

| Case | Wall | Audio | RTF |
|------|-----:|------:|----:|
| Warm steady, short (repeat shape) | ~2.27 s | 3.25 s | **0.70** |
| Warm steady, multi-sentence (repeat) | ~9.79 s | 14.30 s | **0.69** |
| **Novel text #1, first infer** | **30.43 s** | — | — (Δ +26.2 s vs its own second run of 4.21 s) |
| **Novel text #2, first infer** | **27.26 s** | — | — (Δ +23.6 s vs second run 3.70 s) |

Steady-state is realtime-class; the penalty is purely per-novel-shape. `[VERIFY: attach s0_5_result.json + s0_5 log]`

### Expected

Either (a) shape-specialized kernels are persisted via `CACHE_DIR` so a given shape compiles once per install, or (b) a documented mechanism to pre-compile/bucket shapes, or (c) first-infer compile cost on this class of hardware in the low seconds.

### Additional context

- The identical failure mode existed in AMD MIOpen and was resolved with a **persistent disk kernel cache** (see Kokoro-FastAPI issue #454 for the field report `[VERIFY: link]`). OpenVINO's GPU plugin appears to lack an equivalent persistent shape-kernel cache.
- Application-level mitigations we use (token-side shape bucketing + pinned warm utterances at startup + response caching) work but shouldn't be necessary for the officially supported model path.
- Happy to run diagnostics/builds on this hardware on request.

**Attachments:** `[VERIFY: versions json, timing table, GenAI script, logs]`
