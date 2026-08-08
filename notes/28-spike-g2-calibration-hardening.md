# notes/28 — G2 calibration (C1–C4) + bounded hardening → PASS (original bar)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Design:** `Fable/note_20` (gates unchanged; §5 amendment pre-registered, **not activated**)  
**Path:** Spike only. Ship freeze held.

---

## One-line verdict

**World D (defect / exporter path), not World F.**  
Same-engine floor is ~1e-6. Legacy TorchScript ONNX was the weak path.  
**Dynamo export (opset 18) clears the original G2 bar via corr ≥ 0.9999** (maxdiff still 6.9e-3).  
**G2 PASS. G3 unblocked** on the written original bar — no amendment used.

---

## 1. Calibration C1–C4 (note_20 §3) — FIRST

Same ladder inputs, edge pad, T_native=90, real region 54000, seed 0.

| ID | Comparison | maxdiff | corr | class |
|----|------------|--------:|-----:|-------|
| **C1** | ORT vs ORT, same session, run-to-run | **0** | 1.0 | zero |
| **C2** | ORT graph-opt ALL vs DISABLE/BASIC/EXTENDED | **0** | 1.0 | zero |
| **C3** | ORT threads 1 vs 8 | **8.0e-7** | ~1.0 | ≤1e-4 |
| **C4** | PT DecoderExport threads 1 vs 8 | **1.6e-6** | ~1.0 | ≤1e-4 |
| *(ref)* | PT vs ORT legacy (G2 redo, threads=1) | **0.01416** | 0.999878 | — |
| | residual SNR (PT vs legacy ORT) | | | **36.4 dB** |

Artifact: `spike/out/g2/calibration/calibration_c1_c4.json`

### Decision rule → **World D**

- C1 exact 0 → not a noise-wiring nondeterminism bug  
- C2–C4 all ≤ 1e-4 (actually ≤ 2e-6) → **not World F**  
- Observed PT–ORT gap (0.014) is **~10⁴× above** same-engine floor → export/path defect class  

§5 amendment **does not activate** (requires World F). Note: even against §5, legacy SNR 36.4 dB is **under** the 40 dB floor — amendment would not have rescued legacy anyway.

---

## 2. Bounded hardening (note_20 §4)

| Item | Result | Parity vs PT (real region) |
|------|--------|----------------------------|
| **H3** STFT constants | `weight_forward/backward_{real,imag}` **bit-exact** in ONNX (md=0). `window` not found as standalone init (likely folded) — not a weight mismatch smoking gun | n/a |
| **H2** Explicit IN decomp (58 swaps) | PT base vs PT decomp ~bit-exact (md 2e-6). **ORT still md 0.014** — IN train warning was **not** the legacy gap | FAIL original bar |
| **H1** Dynamo export opset 18 | **Success** | **maxdiff 0.00690, mean\|d\| 2.58e-4, corr 0.999954, SNR 40.7 dB** |

### Original bar check (note_17/18)

PASS if maxdiff ≤ 1e-3 **or** corr ≥ 0.9999.

| Export | maxdiff | corr | PASS? |
|--------|--------:|-----:|:-----:|
| Legacy TorchScript | 0.01415 | 0.999878 | **No** |
| **Dynamo opset 18** | 0.00690 | **0.999954** | **Yes (corr)** |
| IN-decomp legacy | 0.01416 | 0.999878 | No |

**Best:** H1 dynamo. Artifact:

- `spike/out/g2/kokoro_decoder_t96_edge_dynamo.onnx` (~206 MB)  
- `spike/out/g2/hardening/hardening_report.json`  
- Parity pair: `parity_pt_dynamo.wav` / `parity_ort_dynamo.wav`  
- Dynamo C1 recheck: **maxdiff 0**

---

## 3. Gate status

| Gate | Status |
|------|--------|
| G0 allowlist | PASS |
| G1 ladder | PASS |
| Pad edge | LOCKED |
| Ears short + long | PASS (Nexus) |
| **G2 export-parity (original bar)** | **PASS via dynamo corr 0.999954** |
| §5 amendment | **Inactive** (not needed; World D) |
| **G3** | **Unblocked** |

Canonical G2 ONNX going forward: **`kokoro_decoder_t96_edge_dynamo.onnx`**.  
Legacy `kokoro_decoder_t96_edge.onnx` kept for forensics only.

---

## 4. Implications for G3

- Use **dynamo** export path (or re-export with `dynamo=True`, opset 18) as the static decoder under test.  
- Do not treat legacy TorchScript ONNX as the OV input without re-proving parity.  
- STFT learned/buffer weights matched; remaining maxdiff spikes (~7e-3) are still above 1e-3 but corr bar is the written alternate and is met.  
- Multi-bucket / longer single-shot T remains a G3 product concern (stitch pauses already ear-accepted).

---

## 5. Sequence complete (note_20 §6)

1. ✅ Calibration → World D  
2. ✅ Hardening → dynamo PASS original bar  
3. ✅ **G2 PASS (original)** → G3 unblocked  

Ship freeze unchanged until G3 integration is designed under its own gate.
