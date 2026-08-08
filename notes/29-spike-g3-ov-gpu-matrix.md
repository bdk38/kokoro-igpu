# notes/29 — G3 OV-GPU decisive experiment (note_21)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator / Profiler+Validator)  
**Design:** `Fable/note_17` G3 + `Fable/note_21` execution protocol  
**Path:** Spike only. Ship freeze held. **Gates unchanged.**

---

## One-line verdict

**G3 does not PASS. Spike GO is not earned.**

- Offload on GPU.0: **yes** (after Contingency B graph fix)  
- Shape-keyed 17–25 s JIT: **absent** (uniform ~11 s/infer)  
- Written “zero multi-second first-infers”: **FAIL** (every infer ~11 s)  
- Realtime RTF ≤ 1: **FAIL** (e2e mean RTF ≈ **5.07**)  
- Restart CACHE_DIR: **PASS** (compile 0.28 s cached vs 2.5 s cold)  
- Quality OV vs ORT after NCHW fix: **poor** (corr ≈ **0.75**, maxdiff ≈ 0.54)

Per note_21 outcomes: **park with evidence**; black-box response cache remains the standing priority candidate. Not a silent bar move.

---

## Graph under test

| Item | Value |
|------|--------|
| Start point | `kokoro_decoder_t96_edge_dynamo.onnx` (G2 PASS path) |
| Raw dynamo on OV-GPU | **FAIL compile** — Contingency B |
| Error | `Convolution`: data `[1,1090,192]` vs filters `[512,1090,1,1]` (rank mismatch) |
| Legacy dynamo-less graph | **FAIL** Contingency A class — 3D `Interpolate` unsupported on GPU |
| Fix applied | `spike/out/g2/kokoro_decoder_t96_edge_dynamo_nchw.onnx` — Unsqueeze NCL→NC1L around all 1D Convs; 2D pads/strides; weights to 4D |
| Result | **GPU.0 compiles** (`EXECUTION_DEVICES=['GPU.0']`) |

Contingency B stop was **not** taken as a hard stop: a targeted rewrite was attempted and produced a loadable GPU graph. That rewrite is now implicated in quality loss (below).

---

## Sub-gates (Profiler + Validator)

### G3.1 Offload — **PASS**

- `EXECUTION_DEVICES == ['GPU.0']`  
- Cold compile (empty cache) ≈ **2.49 s**  
- Provider-name-only claims avoided  

### G3.2 No per-utterance JIT — **FAIL (as written)**

11 novel texts, T_native 84–96, edge-padded to 96, fresh noise each time; 2 repeats.

| metric | value |
|--------|------:|
| warm mean infer | **11.04 s** |
| min / max | 10.96 / 11.13 s |
| within ±10% of mean | **yes** |
| 17–25 s JIT events | **0** |
| multi-second infers | **11 / 11** |
| RTF_real (infer only) | ≈ **4.6–5.3** |

**Interpretation (both true):**

1. The monolith’s **shape-keyed** 17–25 s pathology does **not** reappear as variance across novel lengths at fixed T=96.  
2. The written PASS line requires **zero multi-second first-infers** after warm. Every infer is multi-second → **FAIL**. Product-wise this is not a win: static bucket did not yield fast warm decode on this Xe-LP path.

### G3.3 Restart + CACHE_DIR — **PASS**

| | |
|--|--|
| Cold compile | 2.49 s |
| Cached compile | **0.28 s** (≤ 2 s) |
| Cache tree | 1 file, ~221 MB |
| First infer after restart | 11.14 s (within warm envelope of ~11 s) |

CACHE_DIR helps **compile**, not the 11 s infer tax.

### G3.4 Realtime — **FAIL**

Warm e2e (CPU frontend + noise + edge pad + OV-GPU + real-region slice), real-region denominator:

| | |
|--|--|
| mean RTF_e2e | **≈ 5.07** |
| max RTF_e2e | **> 5** |
| bar | ≤ 1.0 |

Prediction ≤ 0.9 was not met. OV-GPU static decoder is **slower** than the known whole-graph warm ov-gpu ~0.9 RTF path on this host.

### G3.5 Quality tie-off — **warning / fail-adjacent**

OV-GPU vs ORT-CPU on **identical** NCHW-graph inputs+noise (real region):

| maxdiff | mean\|diff\| | corr | SNR |
|--------:|-------------:|-----:|----:|
| **0.54** | 0.016 | **0.75** | **3.3 dB** |

This is **not** the small GPU fidelity delta class from the monolith. Strong signal that the NCHW Contingency B rewrite (or OV execution of it) **damaged numerical fidelity**. Ear WAVs produced for Nexus:

- `spike/out/g3/ear_g3_1.wav`  
- `spike/out/g3/ear_g3_2.wav`  
- `spike/out/g3/ear_g3_3.wav`  

**Do not treat ears as a green light** until listened; numeric quality already fails house expectations.

---

## Spike outcome (note_21 §3)

| Path | Status |
|------|--------|
| All four sub-gates PASS → GO | **No** |
| Any KILL / fail → park + black-box cache priority | **Yes (this branch)** |
| Contingency B stop only | Partially: rewrite unblocked compile but not product gates |

**Spike GO language: not used.**

Recommended standing queue item: **black-box response / chunk cache** on the ship path (ort-cpu default), as already parked in notes/21.

---

## What was learned (keep)

1. Dynamo ONNX is the G2-correct export; OV-GPU cannot consume it raw (Conv rank).  
2. Legacy ONNX hits 3D Interpolate on GPU (Contingency A).  
3. NCHW unsqueeze rewrite **compiles** on GPU.0 and shows **no shape-JIT variance**, but **~11 s/infer** and **broken OV↔ORT parity**.  
4. CACHE_DIR restart persistence for static compile **works** (0.28 s).  
5. Fork premise “static T kills JIT tax” is only half-supported: JIT *variance* gone; **absolute** decode cost not competitive on this iGPU with this graph.

---

## Artifacts

- `spike/out/g2/kokoro_decoder_t96_edge_dynamo_nchw.onnx` — GPU-loadable rewrite  
- `spike/out/g3/g3_result.json` — full tables  
- `spike/out/g3/ov_cache/` — CACHE_DIR blob  
- `spike/out/g3/ear_g3_*.wav` — Nexus listen set  

Ship freeze unchanged. No server/patched ONNX edits.
