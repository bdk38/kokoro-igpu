# notes/31 — O2 Conv-rank blame (minimal repro + escalation)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Design:** `Fable/note_23` §4 (~20-line minimal repro for upstream disposition)  
**OpenVINO:** 2026.2.1 · **GPU:** Intel Xe-LP (GPU.0) · **Export:** torch dynamo ONNX

---

## One-line answer for filings

**A one-op `nn.Conv1d` (plain or `weight_norm`) dynamo ONNX does *not* reproduce the Kokoro failure on OV-GPU.**  
**Blame cannot be pinned to “Conv1d alone” or “weight_norm alone.”**  
**Actionable upstream repro = full `kokoro_decoder_t96_edge_dynamo.onnx` against OpenVINO GPU**, with working minimal Conv1d ONNX attached as contrast.

---

## Matrix (all dynamo unless noted)

| Case | OV-CPU | OV-GPU |
|------|--------|--------|
| plain Conv1d (k=1, k=3) | ok | **ok** |
| legacy TorchScript Conv1d | ok | **ok** |
| dynamo Conv2d-as-1d (NC1L) | ok | **ok** |
| weight_norm Conv1d small | ok | **ok** |
| weight_norm Conv1d 128→64 k=1 | ok | **ok** |
| weight_norm Conv1d **1090→512 k=1** (failing shape class) | ok | **ok** |
| plain Conv1d 1090→512 k=1 | ok | **ok** |
| Unsqueeze→weight_norm Conv1d | ok | **ok** |
| Cat→weight_norm Conv1d (1090 ch) | ok | **ok** |
| **Full Kokoro decoder dynamo** | ok | **FAIL** — data rank 3 vs filters rank 4 |

Artifacts: `spike/out/g3/diagnosis/minimal_conv1d/`  
JSON: `minimal_conv1d_report.json` · write-up: `MINIMAL_CONV1D_REPRO.md`

---

## What the ONNX files look like (minimals)

Dynamo plain/weight_norm minimals emit **clean 1D Conv**:

- weight shape **3D** e.g. `[512, 1090, 1]`
- `pads` length 2, `strides` length 1  
- ORT vs PT maxdiff ~1e-7  

So the exporter is **not** obviously writing illegal 4D filters in the simple case.

---

## What OV does on the full decoder

On `kokoro_decoder_t96_edge_dynamo.onnx`:

1. **`read_model` succeeds**; ordered Convolution ops show **3D** data and **3D** filters in partial shapes (e.g. `[1,1090,96]` × `[1024,1090,3]`).  
2. **`compile_model(..., 'GPU')` fails** during GPU ProgramBuilder with:
   ```text
   Data batch and filters rank do not match
   (data batch shape: [1,1090,192], filters shape: [512,1090,1,1])
   ```
3. **CPU compile of the same ONNX succeeds.**

So the rank break is introduced in the **GPU plugin build path** (or a GPU-specific transformation), not as a trivial “ONNX file already has 4D weights” fact for the minimal pattern.

Yet **isolated** 1090→512 k=1 weight_norm graphs **do not** hit that GPU path failure. Therefore something in the **full decoder graph** (op mix, intermediate ranks, multi-use weights, STFT, dynamo decomps, etc.) triggers the bad GPU lowering.

---

## Blame disposition (O2)

| Claim | Verdict |
|-------|---------|
| “Dynamo always emits bad Conv1d” | **False** (minimal ok) |
| “weight_norm alone breaks OV-GPU” | **False** (minimal ok) |
| “OV-GPU never runs 1D Conv” | **False** (minimal ok) |
| “Full Kokoro dynamo decoder is rejected by OV-GPU with Conv rank error” | **True** (reproduced) |
| Single-component export-vs-plugin split | **Undetermined** at one-op level |
| **Filing package** | **OpenVINO GPU** primary, repro = **full decoder dynamo ONNX** + contrast minimals that work |

### Recommended filing narrative

> OpenVINO 2026.2.1 GPU fails to compile a dynamo-exported Kokoro decoder ONNX with  
> `Convolution` rank mismatch (3D activations vs 4D filters `[O,I,1,1]`) at ProgramBuilder.  
> The same model compiles on CPU.  
> Minimal dynamo `Conv1d` / `weight_norm(Conv1d)` graphs with the same channel shapes **succeed** on GPU.  
> Please diagnose GPU-specific transformation on the attached full model; working minimals attached as contrast.

Secondary (optional) note to PyTorch: full-graph dynamo export may still be implicated if OV points at a specific emitted pattern; we do **not** yet have a one-op exporter smoking gun.

---

## Tie-back to spike park (notes/29–30)

- Does **not** reopen the spike.  
- **Does** sharpen upstream issue packs:  
  - **New/extended OV-GPU issue:** full dynamo decoder Conv-rank compile fail + minimal contrast.  
  - **f32 ref-conv issue:** still supported by NCHW profile (`convolution_gpu_ref__f32` 98%) on the rewrite graph — separate from O2.  
- Ship path / response cache queue unchanged.

---

## Artifact paths

```text
spike/out/g3/diagnosis/minimal_conv1d/
  tiny_conv1d_dynamo.onnx                 # works GPU
  tiny_conv1d_legacy.onnx                 # works GPU
  tiny_weight_norm_1090_512_k1_dynamo.onnx # works GPU
  tiny_plain_1090_512_k1_dynamo.onnx      # works GPU
  minimal_conv1d_report.json
  MINIMAL_CONV1D_REPRO.md

spike/out/g2/kokoro_decoder_t96_edge_dynamo.onnx  # FAIL GPU (primary repro)
```
