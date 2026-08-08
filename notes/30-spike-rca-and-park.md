# notes/30 — Spike RCA (root cause analysis) and park record

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**In reply to:** `Fable/note_22` (confound analysis; diagnosis path B)  
**Path:** Spike diagnosis-only (not a GO extension). Ship freeze unchanged. **No gate moves.**

---

## Executive summary

| Question | Answer |
|----------|--------|
| Did G3 earn Spike GO? | **No** (notes/29). |
| Was the fork premise cleanly falsified? | **Not fully** — two confounds (note_22). |
| What caused ~11 s/infer on the GPU-loadable graph? | **`convolution_gpu_ref__f32` ≈ 98% of profile time** (measured). |
| Can we avoid the damaging NCHW rewrite? | **Not with dynamo as exported** — raw dynamo (op18; op17 request failed version-convert) still hits OV-GPU Conv rank mismatch. |
| Park decision | **Park stands**, now with root-cause evidence. Black-box cache remains top ship-path candidate. Revival needs a **new** gate note, never a retroactive one. |

---

## 1. Causal chain (what actually happened)

```text
G0/G1  seam B bit-exact (PyTorch)                    ✅ notes/25
   ↓
G2     dynamo ONNX opset≥18, ORT parity PASS (corr)  ✅ notes/27–28
   ↓
G3 try raw dynamo on OV-GPU
   → FAIL compile: Conv data rank 3 vs filters rank 4   Contingency B
   ↓
G3 try legacy TorchScript ONNX on OV-GPU
   → FAIL compile: 3D Interpolate                         Contingency A
   ↓
G3 NCHW rewrite (Unsqueeze NCL→NC1L around 1D Convs)
   → GPU.0 compiles + offload PASS
   → CACHE_DIR restart PASS (0.28 s vs 2.5 s cold)
   → NO 17–25 s shape-JIT variance (11 novels ~11.0±0.1 s)
   → EVERY infer multi-second (~11 s) → G3.2 written line FAIL
   → e2e RTF ≈ 5.07 → G3.4 FAIL
   → OV vs ORT corr ≈ 0.75 → quality damaged by rewrite
   ↓
Diagnosis B (this note)
   → Profile: convolution_gpu_ref__f32 dominates
   → Opset-17 dynamo: exporter keeps ≥18; GPU still Conv-rank FAIL
```

---

## 2. Confound resolution (note_22 §2)

### Confound 1 — Graph under test ≠ G2-validated graph

| Graph | Role | OV-GPU | ORT parity vs PT |
|-------|------|--------|------------------|
| `…_dynamo.onnx` (op18) | **G2 canonical** | Compile **FAIL** (Conv rank) | PASS (corr 0.999954) |
| `…_dynamo_nchw.onnx` | G3 improvised rewrite | Compile **OK** | **Broken** (corr ~0.75 vs ORT) |
| Diagnosis op17 attempt | note_21 option | Same Conv rank **FAIL** (file still effectively op18) | PASS if ORT-only |

**Conclusion:** G3 speed/quality numbers describe the **NCHW rewrite**, not the G2-validated decoder export. A slow/broken rewrite does **not** by itself prove “static-T architecture is impossible on Xe-LP.”

**Nexus ears on G3 WAVs (note_22):** ear_g3_1/3 clean; ear_g3_2 slight final-word intonation rise on “berries”; no extra utterances. Metrics (corr 0.75) overstate perceptual damage (phase/pitch sensitive); ears still say prosody changed — **no fidelity claim**.

### Confound 2 — 8× self-anomaly → **ROOT-CAUSED**

**Prediction (note_22):** NCHW shapes force `convolution_gpu_ref__f32` (cheap compile, slow run), unlike monolith warm path that pays JIT for optimized kernels.

**Measurement** (`spike/out/g3/diagnosis/nchw_ov_profile.json`):

| exec_type | time | share | count |
|-----------|-----:|------:|------:|
| **`convolution_gpu_ref__f32`** | **10944 ms** | **98.2%** | 62 |
| generic_eltwise_ref__f32 | 79 ms | 0.7% | 145 |
| deconvolution_gpu_bfyx_opt__f32 | 70 ms | 0.6% | 5 |
| convolution_gpu_bfyx_os_iyx_osv16__f32 (optimized) | **3 ms** | **0.03%** | 9 |

- Wall infer ≈ **11.13 s**; profile sum ≈ **11.15 s** (accounts for wall).  
- Node type **Convolution** ≈ **98.3%**.  
- Optimized conv path essentially unused.

**Conclusion:** The ~11 s is not mysterious and not residual shape-JIT. It is **reference-kernel convolution domination** on the rewritten NC1L/4D-weight graph — the same *class* of Xe-LP f32 conv fallback already tracked for upstream (`convolution_gpu_ref__f32` / issue-2 family), now reproduced on a second graph with a smoking-gun profile.

Monolith warm ~0.9 RTF remains compatible: that path’s long cold JIT builds *optimized* kernels; this static path compiles in ~2.5 s and stays on **ref** kernels forever.

---

## 3. Diagnosis B.2 — opset-17 dynamo (note_21 Contingency B option)

| Step | Result |
|------|--------|
| Request `opset_version=17`, `dynamo=True` | Exporter **warns** and targets **18**; ONNX C API version-convert to 17 **fails** (`axes` attribute assert) |
| Artifact written | `spike/out/g3/diagnosis/decoder_t96_dynamo_op17.onnx` (~215 MB; content still high-opset dynamo family) |
| ORT vs PT | **PASS** original bar (corr **0.999954**, maxdiff 0.0069) — same class as G2 dynamo |
| OV-GPU compile | **FAIL** — identical Cont. B signature: data `[1,1090,192]` vs filters `[512,1090,1,1]` |

**note_22 branch:** **(iii) fails compile** → Contingency B territory again; **park stands**.  
No revival path without a new export strategy (not a gate amendment).

---

## 4. What the spike *did* prove (durable)

1. **Seam B is real and bit-exact in PyTorch** (G0/G1).  
2. **Decoder-only ONNX export works** with noise hoist; **dynamo** is required for G2-class ORT parity.  
3. **Edge pad** is the right bucket pad; zero-pad fails metrics (ears may still pass).  
4. **Shape-keyed JIT variance is absent** at fixed T=96 once a graph runs on GPU (11 novels, ~0.2 s spread, no 17–25 s events).  
5. **CACHE_DIR persists static GPU compiles** on this host (0.28 s vs 2.5 s).  
6. **OV-GPU cannot consume raw dynamo Kokoro decoder export** (Conv rank); **legacy hits 3D Interpolate**.  
7. **NCHW unsqueeze rewrite unblocks compile but selects ref convs and damages fidelity.**  
8. **Slowness RCA:** `convolution_gpu_ref__f32` ≈ 98% of 11 s.

---

## 5. What remains open (for a *future* spike only)

| ID | Question | Why it matters |
|----|----------|----------------|
| O1 | Can an export emit true 1D convs OV-GPU accepts *and* maps to **optimized** f32 kernels? | Would test architecture without Confound 1/2 |
| O2 | Does weight_norm / dynamo lowering force 4D filter presentation inside OV? | Export vs plugin bug split |
| O3 | Monolith decoder subgraph isolation timing (same kernels, fused graph) | Calibrate “should be ~0.6 RTF” claim |
| O4 | Upstream: file shape-JIT contrast + ref-conv profile on **two** graphs | Filings queue |

**None of O1–O4 are in progress.** They require a **new** written gate if resumed.

---

## 6. Park decision (final for this spike)

Aligned with note_22 path **B then park** (diagnosis done; branch iii):

- **Spike status:** **PARKED** (FAIL/not-GO as gated).  
- **GO language:** not used.  
- **Default next product work:** black-box **response/chunk cache** on **ort-cpu** ship path (notes/21, 29, 22).  
- **Upstream:** G3 + profile strengthen f32 ref-conv and shape-JIT contrast drafts; filing still Nexus-queued.  
- **Repo:** `spike/` + notes/25–30 are the research record when commits land.

### Artifact index (RCA)

| Path | Content |
|------|---------|
| `notes/25`–`29` | G0→G3 measurement chain |
| `Fable/note_17`–`22` | Gates and decisions |
| `spike/out/g2/kokoro_decoder_t96_edge_dynamo.onnx` | G2 canonical (ORT-good, OV-GPU no) |
| `spike/out/g2/kokoro_decoder_t96_edge_dynamo_nchw.onnx` | G3 GPU-loadable rewrite (slow + fidelity damage) |
| `spike/out/g3/g3_result.json` | G3 matrices |
| `spike/out/g3/diagnosis/nchw_ov_profile.json` | **RCA smoking gun** (ref conv 98%) |
| `spike/out/g3/diagnosis/op17_diagnosis.json` | Opset-17 attempt (compile fail) |
| `spike/out/g3/ear_g3_*.wav` | Nexus G3 ears |

---

## 7. One-line close

**Park:** static-T decoder export is scientifically real and ORT-viable; on Xe-LP OV-GPU it is blocked by export/plugin conv-rank mismatch, and the only GPU-running rewrite is both **ref-kernel-bound (~11 s)** and **numerically damaged** — so the fork does not graduate; ship value returns to black-box cache on ort-cpu until a new gated export strategy exists.
