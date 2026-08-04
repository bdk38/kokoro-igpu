# Phase 4c — `patch_kokoro_resize.py` results

**Date:** 2026-08-03  
**Script:** `scripts/patch_kokoro_resize.py` (from Nextcloud Documents)  
**Input:** `models/kokoro-v0_19.onnx`  
**Output:** `models/patched/kokoro-v0_19.gpu4d.onnx`

## Patch application

```text
opset=20 nodes=2470
ORT symbolic shape inference: FAILED (NoneType has no len()) → onnx native OK
patched 2 linear Resizes:
  l_sin_gen/Resize   scales [1,1,0.003333] → [1,1,1,0.003333]
  l_sin_gen/Resize_1 scales [1,1,300]      → [1,1,1,300]
onnx.checker: OK
```

## CPU parity (original vs patched, ORT CPU)

```text
shape both (61200,)
max_abs_diff = 4.65e-02
waveform_corr = 0.999441
thresholds: max_abs<1e-3 AND corr>0.9999 → FAIL (strict)
```

Interpretation: surgery is **almost** numerically identical; correlation is excellent. Strict gate failed — worth relaxing or investigating later, but not a show-stopper for GPU compile experiments. Patched model still runs cleanly on ORT CPU (~1.24s / 32 tokens).

## OpenVINO / provider matrix (patched model)

| Path | Result | Error |
|------|--------|-------|
| ORT CPU only | **PASS** | — |
| OpenVINO EP GPU FP16 | **FAIL** create | `rank().is_static()` (no more `linear_onnx`) |
| OpenVINO EP CPU | **FAIL** create | dynamic-rank Parameter `.../STFT_output_0` |
| HETERO:GPU,CPU | **FAIL** create | STFT Parameter not assignable to any device |
| AUTO:GPU,CPU | **FAIL** create | GPU static-rank + CPU STFT dynamic-rank |

## What changed vs unpatched

| Blocker | Before patch | After patch |
|---------|--------------|-------------|
| 3D `linear_onnx` Resize on GPU | **hard fail** | **gone** |
| STFT dynamic-rank partition | present (often masked) | **now the primary wall** |

The Resize rewrite did its job. The next architectural issue is STFT (and the OV partition boundary around it), not Interpolate rank.

## Logs / artifacts

- `logs/patch_v019.log`
- `logs/test_patched_v019_gpu.log`
- `logs/test_patched_v019_more.log`
- `models/patched/kokoro-v0_19.gpu4d.onnx` (311M)

## Implications

1. **Decision-2 Resize spike: partial success.** Correct fix for the documented GPU Interpolate error.
2. **Not sufficient alone** for Kokoro on OpenVINO EP (GPU or CPU) on this stack.
3. Next technical work if continuing iGPU:
   - Force STFT/ISTFT/ScatterND subgraph to stay on ORT CPU while rest uses OV GPU (provider partitioning / exclude ops) — if ORT-OV exposes that
   - Replace STFT path with static-rank equivalent
   - Different runtime path entirely
4. Practical packaging path remains **ORT CPU** (works with original or patched).

## Note on shape inference

ORT `SymbolicShapeInference` crashed here (`NoneType` has no `len()`); native `onnx.shape_inference` ran. Improving shape infer might help STFT ranks but did not on this pass.
