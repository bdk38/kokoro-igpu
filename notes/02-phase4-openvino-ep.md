# Phase 4 — Kokoro ONNX + onnxruntime-openvino

**Date:** 2026-08-03  
**Sandbox:** `/data/intel-igpu-tts`  
**Model:** `models/kokoro-v0_19.onnx` (311MB)  
**Voices:** `models/voices-v1.0.bin` (NPZ, 50 voices, each `(510,1,256)`)

## Stack under test

- Python 3.12 venv at `venv/`
- `openvino==2026.2.1` (GPU device visible: Intel UHD iGPU)
- `onnxruntime-openvino==1.24.1`
- Available ORT providers: `OpenVINOExecutionProvider`, `CPUExecutionProvider`
- Script: `scripts/test_kokoro_openvino_ep.py`

## Model I/O (confirmed via CPU session)

Inputs:

- `tokens` — `int64` `[1, sequence_length]`
- `style` — `float32` `[1, 256]`
- `speed` — `float32` `[1]`

Output:

- `audio` — `float32` `[audio_length]` (24 kHz)

Graph stats (`onnx` inspect): **2470 nodes**. Notable ops:

- `Resize` × 6 (includes **linear** mode on generator path)
- `STFT` × 1 (`/decoder/decoder/generator/STFT`)
- `ScatterND` × 1 (istft path)
- Heavy MatMul/Conv/LSTM/LayerNorm body

Linear Resizes of interest:

- `/decoder/decoder/generator/m_source/l_sin_gen/Resize` — mode=`linear`
- `/decoder/decoder/generator/m_source/l_sin_gen/Resize_1` — mode=`linear`

(Other Resizes are `nearest` and are less likely to be the GPU blocker.)

## Results matrix

### A) ORT CPUExecutionProvider only — PASS

```text
session_create_s ≈ 0.77
warmup ≈ 1.18s
run ≈ 1.22–1.24s  (token_len=32 dummy ids, af_bella style)
output shape (71400,) ≈ 2.97s of audio @ 24kHz
```

Log: `logs/test_kokoro_cpu_only.log`  
Artifact: `artifacts/kokoro_ov_gpu_dummy.wav` (name is from default device label; content is CPU run)

**Conclusion:** Graph is valid. Dummy tokens produce non-trivial audio. Good baseline for later RT-factor comparisons once real phonemes are wired.

### B) OpenVINO EP `device_type=GPU` FP16 — FAIL (session create)

Hard error during initialization:

```text
Check 'inputRank == 2 || inputRank == 4 || inputRank == 5' failed
at src/plugins/intel_gpu/src/plugin/ops/interpolate.cpp:37:
Mode 'linear_onnx' supports only 2D or 4D, 5D tensors
```

Log: `logs/test_kokoro_openvino_ep_gpu.log`

**Conclusion:** OpenVINO GPU plugin rejects Kokoro’s 3D linear Resize/Interpolate. Session never becomes runnable. No opportunity for silent CPU fallback in this configuration — fail is loud and early. This matches prior public reports (Crunchtools / research notes) and explains why Unicorn-style “provider name success” was never real offload proof.

### C) OpenVINO EP `device_type=CPU` FP32 — FAIL (session create)

```text
CPU plug-in doesn't support Parameter operation with dynamic rank.
Operation name: /decoder/decoder/generator/STFT_output_0
```

Log: `logs/test_kokoro_openvino_ep_cpu.log`

**Conclusion:** Even OpenVINO CPU path cannot take the full graph as partitioned by ORT EP because STFT introduces dynamic-rank boundaries the OV CPU plugin rejects.

### D) OpenVINO EP `HETERO:GPU,CPU` — FAIL

Got further into compile, then failed on infer-request / tensor shape compatibility around a dynamic subgraph boundary (`shape=[1,9,600..]` vs empty dim). Not a usable path as-is.

### E) OpenVINO EP `AUTO:GPU,CPU` — FAIL

Both GPU and CPU compile legs failed (GPU dynamic rank + CPU dynamic-rank STFT parameter).

## What this means

| Layer | Status |
|-------|--------|
| Host iGPU drivers (OpenCL/L0) | OK |
| OpenVINO sees GPU | OK |
| Tiny OV GPU model | OK |
| Kokoro ONNX on ORT CPU | OK |
| Kokoro ONNX on ORT OpenVINO GPU | **Blocked** (3D linear interpolate) |
| Kokoro ONNX on ORT OpenVINO CPU | **Blocked** (dynamic-rank STFT) |
| HETERO/AUTO easy win | **No** |

Phase 4 gate **“Kokoro ONNX via ORT OpenVINO EP + busy iGPU” is FAIL for stock v0.19 ONNX** on this stack.

This is a **model/op support** problem, not a missing driver problem. Packaging alone will not fix it.

## intel_gpu_top note

Because GPU session create failed immediately, there was no sustained infer window for OpenVINO GPU. CPU-only runs should show iGPU idle (expected). If you still had `intel_gpu_top` open during the GPU attempt, you should have seen no meaningful RCS/CCS busy period tied to Kokoro.

## Remaining technical options (ordered)

1. **Model surgery / export changes**  
   Re-export or graph-rewrite Kokoro so linear Resize is 4D (NCHW) or replaced with supported ops; stabilize STFT ranks. High effort, uncertain quality.

2. **Direct OpenVINO IR conversion + partial GPU**  
   `ov.convert_model` / offline conversion, then manual device affinity. Likely hits same ops; Echo9Zulu notes also cite ScatterND INT64 pain on GPU IR.

3. **Try alternate ONNX builds**  
   onnx-community v1.0 FP16/quantized exports might differ in opset/shapes. Worth a short A/B, but linear upsample + STFT are architectural, so odds are modest.

4. **Accept ORT CPU** for local OpenAI wrapper  
   Works today; pegs CPU. Useful stopgap / packaging path while iGPU remains blocked.

5. **Hardware path change**  
   NVIDIA Kokoro-FastAPI, or Meteor Lake+ for PyTorch XPU (not this Alder Lake iGPU).

6. **Stop iGPU pursuit** if options 1–3 exceed “too cumbersome” threshold.

## Commands to reproduce

```bash
source /data/intel-igpu-tts/scripts/env.sh

# GPU OpenVINO EP (expected FAIL)
python scripts/test_kokoro_openvino_ep.py --device GPU --precision FP16 \
  --warmup 1 --runs 2 | tee logs/test_kokoro_openvino_ep_gpu.log

# CPU ORT baseline (expected PASS)
python scripts/test_kokoro_openvino_ep.py --cpu-only \
  --warmup 1 --runs 2 | tee logs/test_kokoro_cpu_only.log
```

## Packages frozen after this phase

See `requirements.txt` / `pip freeze` in venv. Key pins:

- openvino 2026.2.1
- onnxruntime-openvino 1.24.1
- numpy 2.4.6
- onnx (added for graph inspect)
