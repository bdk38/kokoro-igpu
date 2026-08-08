<!--
SUBMIT READY — github.com/openvinotoolkit/openvino/issues
Labels (suggested): performance, category: GPU
VERIFY: 2026-08-08 Grok
  - Profile top ops: convolution_gpu_ref__f32 ≈ 96.2% of summed PERF_COUNT ms (iss2_profile.log)
  - notes/44 WebUI soak: 215 s wall / 42.9 s audio / RTF 5.01 / RCS ~100%
  - Contrast: official int8 GenAI steady RTF ~0.69–0.73 on SAME host (s0_5 / i0_3)
File AFTER #2 and paste #2 URL in "Related".
-->

# Title

```
[GPU] f32 Kokoro TTS path dominated by convolution_gpu_ref__f32 on Xe-LP (RTF ~5); optimized kernels missing while official int8/f16 pack reaches RTF ~0.7 on same silicon
```

# Body (paste below)

### Summary

On Intel Xe-LP iGPU, a **working f32** Kokoro TTS ONNX graph (community v0.19 + GPU enablement patches; must run f32 because **f16 hard-fails** — see companion MatMul issue) spends essentially all profiled device time in the reference kernel **`convolution_gpu_ref__f32`**.

Result on a real long utterance: **RTF ≈ 5** with Render/3D engine pegged ~100% — the GPU is busy, but on the reference path.

**Capability proof on the same silicon / drivers:** official `OpenVINO/kokoro-82M-int8-ov` (int8 weights, default f16 compute) via GenAI reaches warm steady **RTF ≈ 0.69–0.73**. The hardware is realtime-capable for this model family; the f32 convolution kernel selection is the gap.

### Environment

| Item | Value |
|------|-------|
| OpenVINO (profile / soak) | **2026.2.1** (primary captures); host now also runs **2026.3.0** for GenAI contrast |
| Model | Kokoro v0.19 f32 ONNX, patched (`gpu4d.stft`), `INFERENCE_PRECISION_HINT=f32` |
| Device | Intel UHD Xe-LP 64 EU (i3-1215U, 8086:46b3) |
| Driver | intel-opencl-icd **26.22.38646.7** · IGC **2.36.5** |
| OS | Ubuntu 24.04.4 LTS |

### Measured

| Path | Workload | Wall | Audio | RTF | GPU |
|------|----------|-----:|------:|----:|-----|
| f32 patched ONNX, GPU | fresh long text (631 tokens, 2 chunks), WebUI soak | **215.1 s** | 42.9 s | **5.01** | RCS ~98–100% sustained |
| official int8 IR GenAI, GPU | multi-sentence **warm steady** | ~9.8 s | 14.3 s | **0.69** | RCS mean ~69% |
| official int8 IR GenAI, GPU | fox **warm steady** | ~2.3 s | 3.25 s | **0.70** | — |

### Profiling (PERF_COUNT excerpt)

From a profiled f32 GPU infer on this host (`iss2_profile.log`):

- Summed op times in capture: **2793.8 ms**  
- Of which `convolution_gpu_ref__f32`: **2688.4 ms (~96.2%)**  
- Top kernels are all `convolution_gpu_ref__f32` under `/decoder/.../generator/` noise_res and resblocks (200 ms+ each for several layers).

### Steps to reproduce

1. Build/compile patched Kokoro f32 ONNX on `GPU` with `INFERENCE_PRECISION_HINT=f32` (f16 will not run — companion bug).  
2. Enable `PERF_COUNT` / per-op profiling; run one medium/long synthesis.  
3. Observe `convolution_gpu_ref__f32` dominating device time.  
4. Optional contrast: run official `OpenVINO/kokoro-82M-int8-ov` GenAI on same GPU; warm steady RTF ~0.7.

Patch + server project: https://github.com/bdk38/kokoro-igpu  

### Expected

Optimized f32 kernels (or a materially faster non-ref fallback) for these temporal/1D-style convolution configurations on Xe-LP, bringing correct f32 execution within a small factor of the int8/f16 official path rather than ~7× slower.

### Why f32 matters here

Per companion accuracy/runtime bug, **f16 inference hard-fails** on this graph (MatMul dimension validation). f32 is currently the **only correct** precision for the community ONNX path on this GPU — so the reference-kernel floor is the effective performance of that ecosystem path on Xe-LP.

### Attachments

- `iss2_profile.log` (PERF_COUNT, ref domination)  
- `iss2_gputop.log` / notes/44 soak (RTF 5.01, RCS pegged)  
- Contrast: `s0_5_result.json` (official pack steady RTF ~0.70)  
- Companion: *(paste f16 MatMul issue URL after filing #2)*

### Related local project

https://github.com/bdk38/kokoro-igpu
