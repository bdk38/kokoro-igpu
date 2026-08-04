# Phase 4d — `patch_kokoro_v2.py` results

**Date:** 2026-08-03  
**Script:** `scripts/patch_kokoro_v2.py`  
**Output model:** `models/patched/kokoro-v0_19.gpu4d.stft.onnx`

## 0) Determinism probe (original v0.19)

```text
no Random* ops in graph
same model, two runs, same feeds:
  max_abs_diff = 0
  corr = 1.0
=> model is DETERMINISTIC
```

**Implication:** The v1 resize parity miss (`max_abs≈4.65e-2`, `corr≈0.99944`) is a **real** numerical delta from the Unsqueeze/Resize/Squeeze rewrite, not stochastic noise. Still small in correlation terms; treat as soft regression, not random.

## 1) Patch application

```text
resize: 2 nodes patched (l_sin_gen Resize + Resize_1)
STFT: stamped /decoder/decoder/generator/STFT_output_0 rank-4 OK
re-stamp after shape-infer: rank=4 OK
onnx.checker: OK
```

ORT symbolic shape infer still crashes (`NoneType` has no `len()`); native onnx infer used.

## 2) Provider matrix (patched gpu4d.stft)

| Path | Session create | Infer | Notes |
|------|----------------|-------|-------|
| ORT CPU | PASS | PASS ~1.08–1.25s | Reference quality |
| OpenVINO EP CPU FP32 | PASS | PASS ~1.05–1.20s | corr vs ORT ≈ 0.9993 |
| OpenVINO EP GPU FP16 | PASS | “PASS” but **bad audio** | NaNs / wrong stats; **no faster** |
| HETERO:GPU,CPU | PASS | PASS (slow first) | Creates; not quality-validated as GPU win |
| AUTO:GPU,CPU | PASS | PASS | Creates |

### Compile breakthrough

v1 (resize only) could not create OV sessions (dynamic-rank STFT Parameter).  
v2 (resize + STFT rank stamp) **clears session creation** on GPU, CPU, HETERO, AUTO.

That is a real step change.

## 3) Quality and offload proof (fixed feeds, seed 1234, 32 tokens)

| Backend | shape | min / max | std | mean_run |
|---------|-------|-----------|-----|----------|
| ORT CPU | 61200 | -0.464 / 0.514 | 0.070 | **1.082s** |
| OV CPU | 61200 | -0.466 / 0.516 | 0.070 | **1.053s** |
| OV GPU | 60600 | **nan / nan** | nan | **1.320s** (slower) |

Correlations:
- ORT CPU vs OV CPU: `max_abs≈3.7e-2`, `corr≈0.9993` (usable)
- ORT CPU vs OV GPU: **corr 0** (NaNs)
- Earlier non-fixed OV GPU run produced finite but pathological audio (`min≈-4.0`, `max≈0.03`) and wrong length

WAVs: `artifacts/v2_ort_cpu.wav`, `v2_ov_cpu.wav`, `v2_ov_gpu.wav`

## 4) `intel_gpu_top` during OV GPU infer

```text
RCS / BCS / VCS / VECS all ~0.00% for entire window
GPU freq req/act = 0
gpu power ~0.00 W
pkg power rose (~5–21 W) — consistent with CPU work
```

**No evidence of iGPU engine activity.** Provider name is `OpenVINOExecutionProvider` with `device_type=GPU`, but engines never left idle. Do **not** treat session success as offload proof (same lesson as Unicorn Orator).

## 5) Interpretation

1. **STFT rank stamp unblocked OV graph compile.** Correct next lever after Resize.
2. **OV CPU path is viable** on the patched model (quality ≈ ORT, speed ≈ ORT). Not an iGPU win; may still help packaging if OV CPU EP is desired.
3. **OV GPU path is not production-ready:**
   - numerical failure (NaN / garbage)
   - no `intel_gpu_top` busy
   - slower than CPU on this i3-1215U UHD
4. Likely remaining issues: FP16 instability, partial subgraph fallback, STFT/complex path on intel_gpu plugin, or partition still wrong despite rank stamp.
5. Resize rewrite still introduces a small deterministic CPU delta (v1 parity); acceptable only if listening tests OK on ORT/OV-CPU.

## 6) Logs

- `logs/probe_determinism_v019.log`
- `logs/patch_v2_v019.log`
- `logs/test_v2_stft_matrix.log`
- `logs/test_v2_stft_detail.log`
- `logs/test_v2_bench.log`
- `logs/test_v2_gpu_proof.log`

## 7) Decision framing

| Goal | Status after v2 |
|------|-----------------|
| Clear Resize GPU blocker | Done (v1) |
| Clear STFT dynamic-rank compile blocker | **Done (v2)** |
| OV session + audio on CPU EP | **Done** |
| Correct GPU audio | **Failed** |
| Measurable iGPU offload | **Failed** (engines idle) |
| Faster than ORT CPU | **Failed** on GPU; ~parity on OV CPU |

**Practical path still:** ORT CPU (original or patched) for product.  
**Research path if continuing:** FP32 GPU, disable FP16; inspect OV partition/exec devices; replace STFT with GPU-safe ops; or accept hybrid with proven engine counters — not provider name alone.
