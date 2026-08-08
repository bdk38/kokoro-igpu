# notes/27 — Spike G2: decoder-only ONNX @ T=96 (edge pad)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Design:** `Fable/note_17`–`19` (Nexus-acked gates + pad lock + G2 greenlight)  
**Path:** Spike only. Ship freeze held.

---

## One-line verdict

**ONNX export succeeded** (static shapes, `onnx.checker` PASS, ORT-CPU runs).  
**Export-parity bar: FAIL** — real-region maxdiff **0.0142**, corr **0.999878** (need ≤1e-3 **or** ≥0.9999).  
Very close on correlation; maxdiff is the clear miss. **Three ear WAVs ready for Nexus** (not a substitute for the parity bar).

---

## What shipped under `spike/`

| Path | Role |
|------|------|
| `spike/g2_export.py` | G0 allowlist + noise-hoist export module + ONNX + ORT parity + ears |
| `spike/out/g2/kokoro_decoder_t96_edge.onnx` | ~204 MB decoder graph |
| `spike/out/g2/g2_result.json` | Full machine-readable report |
| `spike/out/g2/parity_pt.wav` / `parity_ort.wav` | Same inputs, PT vs ORT real region |
| `spike/out/g2/ear_1.wav` … `ear_3.wav` | Nexus ear set |

Run:

```bash
/data/kokoro-openvino/venv-peek/bin/python spike/g2_export.py
```

---

## G0 allowlist

```text
missing outside allowlist = 0, unexpected = 0
g0_pass_amended = true
```

---

## Noise hoist (note_18 §3.1)

| Site | Source | Shape @ T=96 | In ONNX graph? |
|------|--------|--------------|----------------|
| `phase_rand` | `SineGen._f02sine` `torch.rand` | `[1, 9]` | **Yes** |
| `sine_noise` | `SineGen.forward` `randn_like(sine_waves)` | `[1, 57600, 9]` | **Yes** |
| `uv_noise` | `SourceModuleHnNSF` `randn_like(uv)` | `[1, 57600, 1]` | **No — dead** |

**Finding:** `Generator.forward` computes `noi_source` from `uv_noise` but **never uses it** — only `har_source` feeds the STFT path. Export graph therefore has **2 live noise inputs**. Count of stochastic *call sites* in source = 3 (≤ note_18 threshold); live graph inputs = 2. Documented, not a surprise blocker.

---

## ONNX I/O (static)

```text
opset = 17
pad_mode = edge
inputs:
  asr         [1, 512, 96]
  F0          [1, 192]
  N           [1, 192]
  style       [1, 128]
  sine_noise  [1, 57600, 9]
  phase_rand  [1, 9]
output:
  audio       [1, 1, 57600]
onnx.checker  PASS
```

---

## Two comparisons (note_19 §3 — do not conflate)

### A. Bucket fidelity (notes/26 — already decided)

| | |
|--|--|
| What | `decoder(edge→96)` vs native T, real region |
| Result | corr **0.997**, P1_weak, **ear-clean** (Nexus) |
| Role | Cost of static bucketing |

### B. Export parity (this note — G2 bar)

| | |
|--|--|
| What | PyTorch `DecoderExport` vs ORT-CPU, **identical** edge-padded inputs + **identical** `sine_noise`/`phase_rand` |
| Region | Real region after trim (T_native=90 → 54 000 samples); full buffer also reported |
| Bar | maxdiff ≤ **1e-3** **or** corr ≥ **0.9999** |

| region | maxdiff | mean\|diff\| | corr | bar |
|--------|--------:|-------------:|-----:|-----|
| full 57600 | 0.01415 | 3.41e-4 | 0.999878 | FAIL |
| **real 54000** | **0.01415** | 3.64e-4 | **0.999878** | **FAIL** |

**G2 export-parity: FAIL** (corr misses 0.9999 by ~2.2e-5; maxdiff is 14× the 1e-3 ceiling).

### Diagnostic (not a gate)

Original `decoder()` with torch RNG seed vs export module with hoisted noise (same seed, different draw order): maxdiff ~0.076, corr ~0.998 — matches the **weekend peek ~0.075** class when noise streams differ. Confirms noise hoist is load-bearing for fair ORT compares.

Export warning of note: TorchScript exporter logs `instance_norm` with `train=True` despite `eval()` — likely contributor to the 1e-2-class maxdiff. Worth a follow-up (force IN eval / opset / dynamo exporter) before declaring G2 dead.

---

## Ear set (for Nexus)

| file | text | T_native | samples |
|------|------|---------:|--------:|
| `spike/out/g2/ear_1.wav` | Hello from the spike ladder. | 90 | 54000 |
| `spike/out/g2/ear_2.wav` | Peter packed bright berries. | 91 | 54600 |
| `spike/out/g2/ear_3.wav` | Remember the keys and wallet. | 92 | 55200 |

All via: CPU frontend → **edge** pad to 96 → ONNX decoder (ORT-CPU) → real-region trim.  
Also listen: `parity_pt.wav` vs `parity_ort.wav` (export-parity pair).

Longer lines exceed T=96 (e.g. swans T=110) — expected; multi-bucket is G3 territory.

---

## Gate status vs note_17/19

| Item | Status |
|------|--------|
| G0 allowlist | **PASS** |
| G1 seam ladder | **PASS** (notes/25) |
| Pad decision edge | **LOCKED** (notes/26 + note_19) |
| G2 ONNX exists + checker | **PASS** |
| G2 export-parity bar | **FAIL** (numbers above) |
| G2 ears | **Awaiting Nexus** (3 files) |
| G3 | **Blocked** until G2 parity resolved or Nexus accepts a written bar amendment |

---

## Recommended next (do not silent-move the bar)

1. **Nexus ears** on `ear_1..3` + optional `parity_pt` vs `parity_ort`.
2. **Parity hardening pass** (spike-only): chase InstanceNorm export mode, try dynamo exporter / higher opset, confirm CustomSTFT numerics — target maxdiff ≤ 1e-3 or corr ≥ 0.9999 without relaxing the written gate.
3. Only after G2 parity PASS (or explicit Nexus gate amendment): G3 OV-GPU static matrix.

Ship path still frozen.

---

## Nexus ear record (long set) — 2026-08-07

**Files:** `spike/out/g2/ear_long_1.wav`, `ear_long_2.wav`, `ear_long_3.wav`  
**Verdict: PASS**

- All words present; no missing text.
- No additional utterances / no moan-class pad artifacts.
- Pauses at chunk boundaries — **expected** from T≤96 stitch (not a trim/decoder defect).
- Listened for intonation, lisps, clicks — no defects reported beyond those expected pauses.

Short set (`ear_1..3`) previously: audibly clean.

**Implication:** Product-path ears on the ONNX decoder stitch are good enough to keep using this export for listen tests. **Export-parity numeric bar remains FAIL** (maxdiff 0.014 / corr 0.999878) until a hardening pass or written bar amendment — ears do not silently rewrite that gate.

