# Phase 4b — Decision 1: Kokoro v1.0 ONNX variant A/B on OpenVINO GPU EP

**Date:** 2026-08-03  
**Source:** `onnx-community/Kokoro-82M-v1.0-ONNX`  
**Local path:** `/data/intel-igpu-tts/models/v1/`  
**Log:** `logs/test_kokoro_v1_variants_gpu.log`

## Why this test

v0.19 failed GPU session create on 3D `linear_onnx` Interpolate. Hypothesis: a different export (FP16 / quantized / v1.0 graph) might reshape or eliminate that op.

## Downloaded artifacts

Under `models/v1/onnx/`:

- `model.onnx` (~326MB FP32)
- `model_fp16.onnx` (~163MB)
- `model_q4.onnx`, `model_q4f16.onnx`
- `model_q8f16.onnx`
- `model_quantized.onnx`
- `model_uint8.onnx`, `model_uint8f16.onnx`

Voices: per-voice raw bins in `models/v1/voices/` (e.g. `af_bella.bin` = 510×256 float32).  
Tests reused existing NPZ `models/voices-v1.0.bin` for style vectors (compatible 256-d).

## Graph inspect (representative)

All inspected variants keep the same architectural blockers:

| Item | Present |
|------|---------|
| I/O | `input_ids`, `style[1,256]`, `speed` → `waveform` |
| `Resize` | 6 |
| linear `Resize` | **yes** — `/decoder/.../l_sin_gen/Resize` and `Resize_1` |
| `STFT` | 1 |
| `ScatterND` | 1 |

Quantized graphs have more nodes (Q/DQ) but **do not remove** linear Resize / STFT / ScatterND.

## GPU OpenVINO EP results

Script: `scripts/test_kokoro_openvino_ep.py --device GPU --precision FP16`

| Model | Session create | Error |
|-------|----------------|-------|
| model.onnx | FAIL | `linear_onnx` only 2D/4D/5D |
| model_fp16.onnx | FAIL | same |
| model_q8f16.onnx | FAIL | same (deeper subgraph id) |
| model_quantized.onnx | FAIL | same |
| model_q4f16.onnx | FAIL | same |
| model_uint8f16.onnx | FAIL | same |

No variant reached `sess.run()`. No sustained Kokoro infer window on iGPU.

### About intel_gpu_top movement

Short GPU activity during these attempts is expected and **not** proof of successful Kokoro offload:

- OpenVINO still parses/partitions/compiles subgraphs before hitting the unsupported Interpolate
- Cache dir messages and rising subgraph indices (`...subgraph_67_66` etc.) show compile work
- Failure is still at **InferenceSession create**, before timed infer loops

That matches “PID + some movement” without a working GPU Kokoro path.

## Conclusion

**Decision 1 is exhausted: FAIL.**

Stock Kokoro ONNX exports (v0.19 and v1.0 FP32/FP16/quantized) share the same GPU-illegal 3D linear Resize. Changing precision/quantization does not fix iGPU OpenVINO EP support on this stack (OpenVINO 2026.2.1 + ORT-OV 1.24.1 + UHD 46b3).

## Implications

Remaining iGPU options are no longer “try another file”:

1. **Graph surgery** — rewrite linear 3D Resize to 4D-supported form (or nearest/other supported path), possibly fix STFT rank for OV partitions  
2. **Custom export** from PyTorch with OV-friendly ops  
3. **Abandon iGPU for Kokoro on this host** — use ORT CPU wrapper, or other hardware  
4. **Wait for upstream** OpenVINO GPU interpolate rank support (uncertain timeline)

Packaging an OpenAI API on ORT CPU remains viable anytime; it just will not unload the CPU onto this iGPU with current Kokoro ONNX graphs.
