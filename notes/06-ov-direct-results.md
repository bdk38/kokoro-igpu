# Phase 4e — Direct OpenVINO runtime (`test_kokoro_ov_direct.py`)

**Date:** 2026-08-03  
**Model:** `models/patched/kokoro-v0_19.gpu4d.stft.onnx`  
**Script:** `scripts/test_kokoro_ov_direct.py`  
**OpenVINO:** 2026.2.1  

Bypasses ORT OpenVINO EP entirely: whole-graph `ov.Core` compile on one device.

## GPU FP32 static + profile + ORT compare

```text
compile: OK in 12.01s
execution devices: ['GPU.0']
warmup: 17.2s
runs: 2.693 / 1.424 / 1.412  mean=1.843s
audio: shape=54000  nan=0  min=-0.42 max=0.49 std=0.052
ORT CPU same feeds: shape=61200  mean_run≈1.09s
cmp: LENGTH MISMATCH; first 54000 corr=0.0095  max_abs=0.67
```

### Profile (top ops) — all GPU kernels

```text
~189 ms  Convolution  convolution_gpu_ref__f32  noise_res.1/...
~186 ms  Convolution  convolution_gpu_ref__f32
... entire top-25 is convolution_gpu_ref__f32 or TensorIterator (LSTM)
```

No CPU fallback ops in the top list. This is whole-graph (or near-whole) GPU execution inside OV.

### intel_gpu_top during window

```text
RCS ~95–99%
GPU act freq ~1060–1100 MHz
GPU power ~6–8 W (peaks higher in parse)
```

**Offload: YES (proven).**

### Quality: FAIL

Wrong length (54k vs 61.2k samples) and essentially zero correlation vs ORT CPU.

## CPU FP32 static + profile + ORT compare

```text
compile: OK in 1.12s
execution devices: ['CPU']
runs mean=0.996s
audio: shape=61200  nan=0  min=-0.45 max=0.43 std=0.065
ORT CPU: shape=61200  ~1.01–1.09s
cmp: max_abs=0.165  corr=0.968
```

### Profile highlights

```text
29 ms  STFT         jit_avx2_f32   /decoder/.../STFT   ← top op
~24 ms Convolution  brgconv_avx2_f32  resblocks...
```

STFT runs natively on OV CPU (unlike ORT-EP path where STFT stayed on ORT CPU EP).

### Quality: partial

Length matches; corr ~0.97 is “same voice-ish” but not bit-exact / not product-threshold vs ORT. Still far better than GPU’s 0.01.

## Comparison table

| Path | Compile | Device proof | mean infer | length | corr vs ORT | Notes |
|------|---------|--------------|------------|--------|-------------|-------|
| ORT CPU | OK | CPU | ~1.08s | 61200 | 1.0 | reference |
| OV direct CPU f32 static | OK | CPU | **0.996s** | 61200 | **0.968** | slight drift; STFT in OV |
| OV direct GPU f32 static | OK | **GPU.0 + RCS~99% + gpu kernels** | 1.84s | **54000** | **0.010** | true iGPU, wrong audio, slower |
| ORT + OV EP GPU f32 (prior) | OK | hybrid 3 subgraphs + STFT/NonZero CPU; RCS busy | ~2.3s | 61200 | ~0.04 | also wrong |

## Interpretation

1. **Direct OV GPU path is real iGPU execution** — not a fake provider label. Profile `convolution_gpu_ref__f32` + `EXECUTION_DEVICES=['GPU.0']` + RCS pegged.
2. **Removing EP partitioning did not fix correctness.** Bad audio is not only an ORT-EP boundary artifact; OV GPU graph math/length still diverges (likely ISTFT/STFT/complex or length-related GPU kernels).
3. **OV direct CPU is the best non-ORT result so far** (corr 0.97, ~parity latency) but still not a drop-in ORT replacement without listening tests / tighter tolerance work.
4. **Speed:** on i3-1215U UHD, GPU path is slower than CPU for this model at token_len=32. iGPU offload ≠ win.
5. **v2 patch remains necessary** for compile (rank stamp + 4D resize).

## Artifacts

- `logs/test_ov_direct_gpu_f32.log`
- `logs/test_ov_direct_cpu_f32.log`
- `artifacts/ov_direct_gpu_f32.wav`
- `artifacts/ov_direct_cpu_f32.wav`

## Decision framing

| Goal | Status |
|------|--------|
| Whole-graph OV GPU compile | **Done** |
| Prove iGPU kernels + RCS busy | **Done** |
| Correct GPU audio vs ORT | **Failed** |
| Faster than ORT CPU | **Failed** (GPU slower; OV CPU ≈ ORT) |
| Product TTS path | Still **ORT CPU** (or listen-test OV CPU if 0.97 corr acceptable) |

Next research (if any): dump intermediate tensors around STFT/ISTFT on GPU vs CPU; try OV HETERO with STFT forced CPU inside OV; or stop and package ORT CPU.
