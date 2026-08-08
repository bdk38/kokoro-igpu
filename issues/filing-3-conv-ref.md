# FILING DRAFT #3 — for github.com/openvinotoolkit/openvino/issues

**Repo:** openvinotoolkit/openvino · **Component:** GPU plugin (performance)
**Prepared:** 2026-08-08 · Fable draft for Grok evidence-attach + Nexus submit
**[VERIFY] markers = Grok confirms/fills from repo evidence before submit.**

---

## Title

`[GPU] f32 TTS convolutions fall to convolution_gpu_ref on Xe-LP, dominating runtime (RTF ≈ 5 vs 0.7 achievable on same silicon); optimized kernel selection missing for 1D/temporal conv patterns`

## Body

### Summary

Running a **f32 Kokoro TTS graph** on Intel Xe-LP iGPU, profiling shows the decoder's convolution workload selecting the reference kernel **`convolution_gpu_ref__f32`** for the overwhelming majority of runtime `[VERIFY: exact % + profile excerpt from repro notes]`. Result: fresh long-text synthesis at **RTF ≈ 5** (215.1 s wall for 42.9 s audio, GPU Render/3D pegged 98–100% the whole window) — the GPU is fully busy doing reference-kernel work.

**Capability proof on the same silicon:** the official `OpenVINO/kokoro-82M-int8-ov` pack (int8 weights, f16 compute) achieves warm steady **RTF ≈ 0.70** on this exact host/driver. The hardware is realtime-capable for this model family; the f32 conv path's kernel selection is the gap. TTS-style temporal/1D convolution shapes appear to have no optimized f32 kernel on this architecture.

### Environment

| Item | Value |
|------|-------|
| OpenVINO (repro) | 2026.2.1 `[VERIFY: optional single re-profile on 2026.3.0 to update or scope]` |
| Model | Kokoro v0.19 f32 ONNX (community export, whole graph, `INFERENCE_PRECISION_HINT=f32` required per companion accuracy issue) |
| Device / driver / OS | Intel UHD Xe-LP 64 EU (i3-1215U, 15 W) · intel-opencl-icd 26.22.38646.7 · IGC 2.36.5 · kernel 7.0.0-28 · Ubuntu 24.04-class |

### Measured

| Path | Workload | Wall | Audio | RTF | GPU busy |
|------|----------|-----:|------:|----:|---------|
| f32 ONNX, GPU | fresh long text (631 tokens, 2 chunks) | 215.1 s | 42.9 s | **5.01** | RCS 98–100% sustained |
| official int8/f16 IR, GPU (same host) | multi-sentence, warm steady | ~9.8 s | 14.3 s | **0.69** | RCS mean ~69% |

`[VERIFY: attach profile JSON/opcounts showing convolution_gpu_ref domination + intel_gpu_top logs for both rows]`

### Steps to reproduce

1. Compile the f32 Kokoro ONNX on `GPU` with `INFERENCE_PRECISION_HINT=f32`.
2. Synthesize a long passage; collect per-kernel profiling (`PERF_COUNT` / opcounts).
3. Observe `convolution_gpu_ref__f32` dominating total device time.

### Expected

Optimized (blocked/winograd/imad-class as applicable) f32 kernels selected for these convolution configurations, or an upcast-free fallback materially better than the reference kernel — bringing f32 within a small factor of the f16/int8 path rather than ~7×.

### Additional context

- The f32 path is not academic on this hardware: per the companion accuracy issue, f16 execution corrupts this graph's output, so f32 is currently the *only* correct precision for the community ONNX — making the reference-kernel floor the effective performance of that ecosystem path on Xe-LP.
- Hardware available for kernel testing on request.

**Attachments:** `[VERIFY: profile dumps, opcount tables, igt logs, repro script]`
