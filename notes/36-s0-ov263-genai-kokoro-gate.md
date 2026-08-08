# notes/36 — Gate proposal: S0 Official Kokoro on OpenVINO 2026.3 (Xe-LP)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator) — draft for full team buy-in  
**Status:** **ACTIVE / FULLY ACKED** (Fable note_26 A1–A3 via 36b; Nexus ack all three 2026-08-07). Dual-track: S0 uses **side venv 2026.3 only** (notes/38).  
**Audience:** Nexus (bdk), Chief Architect (Fable), Orchestrator (Grok)  
**Related:** `notes/34-spike-closeout-summary.md`, `notes/25`–`32`, `WORKFLOW.md`, OpenVINO 2026.3 release notes  
**Path:** **New spike probe** (isolated). Does **not** reopen parked G0–G3.

---

## 0. Why this note exists

The componentized decoder-export spike is **PARKED** with full RCA (`notes/33`–`34`). Before packing that story as final, OpenVINO **2026.3** (4 Aug 2026) shipped first-party Kokoro surface area we did not have when G3 failed:

| 2026.3 claim (release notes) | Relevance |
|------------------------------|-----------|
| **Kokoro-82M** early release on **CPU and GPU** | Same model family, official path |
| GenAI: Kokoro in **`Text2SpeechPipeline`** | Managed pipeline vs our ONNX/export stack |
| OVMS preview: Kokoro on OpenAI **`/audio/speech`** | Possible alternate serve path |
| GPU plugin notes | Memory / blob / MoE / ASR — **no** explicit fix for our Conv-rank / 3D interpolate / 1D ref-conv blockers |

Ship track runs **OpenVINO 2026.2.1** (dual-track, notes/38). S0 installs **2026.3.0 + GenAI** in a **side venv only**. PyPI has both.

This is a **new gate**, not a quiet reopen of the parked fork. Per `WORKFLOW.md`: written bars + Nexus ack **before** implementation; Fable owns design soundness; Grok owns silicon truth.

---

## 1. What's changing and why

### Bet (one sentence)

**Official OpenVINO 2026.3 Kokoro (GenAI `Text2SpeechPipeline` and/or documented conversion path) may deliver a usable GPU Kokoro path on this Xe-LP host without our componentized export — or it may not. Measure before packing the spike as closed forever and before investing ship-path integration.**

### Why not “just reopen G3”

| Parked spike (G0–G3) | This proposal (S0) |
|----------------------|--------------------|
| *Our* dynamo decoder ONNX + OV-GPU | *Upstream* GenAI/OV Kokoro graph |
| Failed: Conv rank on good graph; NCHW rewrite RTF≈5, ref-conv 98% | Unknown whether upstream graph hits the same ops |
| Goal: prove componentized static-T fork | Goal: does first-party Kokoro work on **this** iGPU? |
| Revival needs new export strategy | Probe needs new env + official model path only |

Same product question (“can this iGPU speak Kokoro well?”), **different technical claim**.

### Sequence (hard-gated)

```text
S0.0  Team ack (this note)
  → S0.1  Install 2026.3 side env + GPU visible
  → S0.2  Obtain/convert official Kokoro assets + load on GPU
  → S0.3  Offload proof (devices/kernels/top — not provider name)
  → S0.4  Quality (parity band + Nexus ears by filename)
  → S0.5  Speed honesty (cold vs steady RTF)
  → VERDICT: narrow GO / demo-only / KILL
       │
       ├─ optional S1  OVMS /audio/speech (only if S0 load+speech works)
       ├─ optional S2  Re-test *our* G2 dynamo ONNX on 2026.3 GPU (Conv rank still?)
       └─ optional S3  True G3 revival — **requires a separate Fable gate note**, never automatic
```

No later optional gate starts without an explicit Nexus call after S0 verdict.

---

## 2. Binding go/kill bars (S0)

All bars are written **before** measurement. Softening a bar after numbers exist requires Nexus + note amendment — same discipline as `Fable/note_17`.

### S0.1 — Install and device

| | |
|--|--|
| **Work** | Fresh **side** venv (do not upgrade ship `venv` in place). Install `openvino==2026.3.*`, `openvino-genai==2026.3.*`, plus whatever the official Kokoro path requires (optimum-intel / notebook deps as discovered). |
| **PASS** | Import OK; `ov.Core().available_devices` includes GPU (or `GPU.0`); versions recorded in the measurement note. |
| **KILL** | Cannot install a working 2026.3+GenAI stack on this host, or GPU not visible under 2026.3. |

### S0.2 — Load official Kokoro on GPU

| | |
|--|--|
| **Work** | Follow **upstream** conversion/load path only (GenAI docs, release assets, optimum-intel, or official notebook). No hand-patched ONNX from `models/patched/` as the S0 primary path. Record exact model ID, commit/tag, convert command, and IR/ONNX layout. |
| **PASS** | `Text2SpeechPipeline(model_path, "GPU")` (or equivalent documented API) constructs and completes **one** `generate(...)` without compile/runtime exception. |
| **KILL** | Load/compile fails with our known classes (3D `linear_onnx` Interpolate; Conv data rank vs filters rank; similar ProgramBuilder failures) **and** no official documented workaround that is not “run on CPU.” |
| **Branch (not auto-KILL)** | Loads only on **CPU** → record as **CPU-only official path**; S0.3–S0.5 GPU bars N/A; overall S0 cannot earn GPU GO. |

### S0.3 — Real offload

| | |
|--|--|
| **Work** | During GPU generate: capture execution devices and/or OV profiling and/or `intel_gpu_top` RCS/CCS busy window. House rule unchanged: **provider string ≠ offload proof.** |
| **PASS** | Evidence that the heavy graph runs on **GPU.0** (or documented multi-device split with GPU owning the bulk of TTS compute — split must be described, not hand-waved). |
| **KILL** | “GPU” pipeline silently runs on CPU, or offload cannot be evidenced. |

### S0.4 — Quality

| | |
|--|--|
| **Work** | Fixed utterance set (below). Save WAVs under `spike/ov263-genai/out/` (or `artifacts/s0/` if promoting). Compare sanity to ort-cpu reference where practical (duration band, no extra utterances); **Nexus ears are binding** for ship-quality language. |
| **PASS** | Nexus ear **PASS by filename** on **≥ 3** short utterances **and** **≥ 1** multi-sentence passage; no pad-moan / missing words / garbage class failures. |
| **KILL** | Ears FAIL on majority of set, or systematic defect (moan, skip, unintelligible) with no quick upstream config fix. |
| **Note** | Numeric corr vs our v0.19 ORT path is **informative only** if model revision differs (v1.0 / 82M official vs our v0.19). Do not KILL solely on cross-checkpoint corr. |

### S0.5 — Speed honesty

| | |
|--|--|
| **Work** | Methodology per `WORKFLOW.md`: name cold first-infer vs steady-state; discard or separately report warmup; fixed text set; RTF = wall / audio duration. |
| **Report always** | Cold compile+first infer; steady mean±spread on ≥5 generates after warmup; optional restart+`CACHE_DIR` if the official path exposes it. |
| **Product-interest PASS (narrow GO speed clause)** | Steady-state e2e RTF **≤ 1.0** on fox-class **and** one multi-sentence sample on this host. |
| **Demo-class outcome (not KILL, not product GO)** | GPU works + ears PASS + steady RTF still in **~4–6** (or similar) band — same class as current patched whole-graph demo. Record as **demo-only official path**. |
| **KILL (speed)** | Only if GPU path is **worse in a disqualifying way** after offload proof (e.g. multi-minute per utterance with no path to steady), or unusable instability. Slow-but-demo is **demo-class**, not speed-KILL. |

### Overall S0 verdict vocabulary (use exactly these)

| Verdict | Meaning | Product implication |
|---------|---------|---------------------|
| **S0-GO-product** | S0.1–S0.5 all PASS including RTF ≤ 1.0 + ears | Worth ship-path design to integrate or replace ov-gpu demo / consider default policy later (separate ship gate) |
| **S0-GO-demo** | Load + offload + ears PASS; RTF > 1 but usable demo | Official path may replace **our patched ONNX demo** maintenance burden; **ort-cpu remains default**; cache still top latency bet |
| **S0-CPU-only** | Official Kokoro works on CPU, not GPU here | Interesting for packaging comparison; does not change iGPU story |
| **S0-KILL** | Cannot load/run usefully on this host on GPU (and no valuable CPU-only story) | Park S0; keep prior spike park; continue ship queue |
| **S0-INCONCLUSIVE** | Blocked on missing upstream assets/docs after good-faith attempt | Stop; file what blocked; do not invent a graph |

**Spike GO language for the parked componentized fork is not available from S0 alone.**  
Fork revival = **optional S2/S3** + **new Fable gate note** + Nexus ack.

---

## 3. Predicted branches (falsifiable)

| Branch | Signature | Implication |
|--------|-----------|-------------|
| **B1 — Official graph avoids our blockers** | GPU load OK; no Conv-rank / 3D interpolate errors; offload proof | Upstream export/IR differs from stock ONNX and our dynamo decoder; S0 continues to ears/RTF |
| **B2 — Same plugin wall, new wrapper** | Failures match notes/29–32 (Interpolate assert, Conv 3D vs 4D, ref-conv domination) | 2026.3 marketing ≠ Xe-LP fix; strengthens filings; S0-KILL or demo-only if a rewrite sneaks through slow |
| **B3 — Loads on GPU but ref-bound slow** | Offload proof + profile ≈ `convolution_gpu_ref__f32` majority; RTF ≫ 1 | Same physical limit as G3 rewrite / whole-graph demo; **S0-GO-demo** at best |
| **B4 — CPU-only “GPU” support** | Device string accepted but exec on CPU, or GPU compile always fails | Document; no iGPU win |
| **B5 — Model/asset gap** | No published Kokoro IR, broken notebook, GenAI API present but model missing | S0-INCONCLUSIVE; not a silicon KILL |

---

## 4. Do not touch (ship freeze for this probe)

Unless Nexus explicitly lifts for a **ship-path** task (e.g. approved v1.1.8):

| Off-limits to S0 Mechanic / probe edits | Allowed |
|----------------------------------------|---------|
| `scripts/kokoro_server.py` | `spike/ov263-genai/` (code, scripts, out/) |
| `models/patched/` | Side venv e.g. `venv-ov263/` or `/data/intel-igpu-tts/.venv-ov263` |
| Product README default claims | Measurement note `notes/37-…` (or next free NN) after run |
| Quiet edits to parked `spike/out/g2` canonical ONNX | Read-only use of G2 ONNX **only** if Nexus opens **S2** |
| Redefining S0 bars after seeing RTF | Fable amendment note + Nexus ack |

Ship queue (v1.1.8, response/chunk cache, commit, filings) remains **parallel-capable**: S0 must not block v1.1.8 approval or cache design unless Nexus serializes them.

---

## 5. Fixed probe set (measurement contract)

### Short ears (always)

1. `The quick brown fox jumps over the lazy dog.`  
2. `Hello from the OpenVINO GenAI Kokoro probe.`  
3. `Remember the keys and wallet.`  

### Long ear (always)

4. Multi-sentence passage (≥ 2 sentences; may reuse swans / spike long-ear text for continuity with notes/27).

### Timing set

- Fox (short) × cold + steady  
- One long passage steady  
- Optional: novel shorts for shape-JIT observation (report only; not a G3-style kill unless multi-minute)

### Artifacts

```text
spike/ov263-genai/
  README.md          # how to recreate env + commands
  out/
    versions.json    # pip freeze subset, ov devices
    ear_short_1.wav …
    ear_long_1.wav
    timing_table.md  # or .json
    offload_proof.txt / profile json if available
notes/NN-s0-ov263-genai-results.md   # decisive table + verdict word
```

---

## 6. Roles (RACI-style, under handoff contract)

| Work | Nexus | Fable | Grok orch. | Mechanic | Profiler | Validator |
|------|:-----:|:-----:|:----------:|:--------:|:--------:|:---------:|
| Ack / kill / serialize vs ship queue | **A** | C | C | — | I | C |
| Gate text soundness (this note) | A (final) | **R** review/amend | R draft | — | I | C |
| Side env + probe scripts | I | C | **A** | R | I | I |
| Offload + RTF matrix | I | C | A | I | **R** | C |
| Parity sanity + ear fold-in | **R** ears | C | A | — | C | **R** |
| Verdict word in notes | A | C | **R** | — | C | R |
| Product/default README changes | **A** | C | R | I | I | **R** (block until matrix) |
| Optional S2/S3 new gates | A | **R** author | C | I | C | C |

---

## 7. What S0 is optimized to answer

1. Did Intel ship a **real** Kokoro GPU path we can run on **Alder Lake UHD**, or only a label?  
2. If real, is it **product-fast**, **demo-fast**, or **CPU-only** here?  
3. Does 2026.3 change the **filing / park** story for our Conv-rank and ref-conv evidence?  
4. Should ship engineering prefer **official GenAI/OVMS** over maintaining **patched v0.19 ONNX** for the demo backend?

What S0 is **not**:

- Not permission to claim ort-cpu dethroned without Validator + Nexus  
- Not automatic revival of componentized export  
- Not a substitute for response/chunk cache on the ship path  

---

## 8. Optional follow-ons (explicit open only)

### S1 — OVMS preview `/audio/speech`

Only if S0.2–S0.4 show life. Compare API shape vs `kokoro_server.py`; not a default cutover.

### S2 — Our G2 dynamo ONNX × OpenVINO 2026.3 GPU

Single question: **does ProgramBuilder still reject Conv rank on `kokoro_decoder_t96_edge_dynamo.onnx`?**  
PASS/FAIL only on compile+one infer; not a full G3 matrix.  
Informs whether filings need a “fixed in 2026.3” update.

### S3 — Componentized fork revival

**Forbidden** without a **new** Fable gate note superseding park. S0-GO-product or S2 compile PASS are **inputs** to that discussion, not the gate itself.

---

## 9. Evidence basis for opening this proposal

**Verified**

- OpenVINO 2026.3 release notes list Kokoro-82M early release on CPU/GPU; GenAI Kokoro in `Text2SpeechPipeline`; OVMS Kokoro `/audio/speech` preview.  
- Host lab OV: **2026.2.1** (`/data/intel-igpu-tts/venv`).  
- PyPI: `openvino 2026.3.0`, `openvino-genai 2026.3.0.0`.  
- Parked spike RCA: notes/29–32 (Conv rank, ref-conv 98%, interpolate assert).  

**Inferred / unknown (why we measure)**

- Exact Kokoro export graph and whether it avoids 1D/3D GPU holes.  
- Any Xe-LP RTF expectation (none published for Kokoro in the notes we used).  
- GenAI public speech-generation doc page may still lag (SpeechT5-centric); release notes ahead of tutorials is possible.

---

## 10. Buy-in checklist

### Fable (Architect) — please mark

- [ ] Gate bars S0.1–S0.5 are sound / suggest amendments  
- [ ] Verdict vocabulary acceptable (GO-product / GO-demo / CPU-only / KILL / INCONCLUSIVE)  
- [ ] Optional S2/S3 separation accepted (no silent G3 reopen)  
- [ ] Freeze list acceptable  
- [ ] Any additional predicted branch or bar **before** run  

*Fable may reply via `Fable/note_26` (or next) amending this file by reference — Orchestrator will fold amendments into this note or `notes/36b` before execution.*

### Nexus — please mark

- [ ] **Ack S0** as written (or ack with listed amendments)  
- [ ] Priority vs ship queue:  
  - [ ] **P1** — run S0 before v1.1.8 / cache  
  - [ ] **P2** — run S0 after v1.1.8 ack (parallel OK)  
  - [ ] **P3** — defer S0; pack spike; ship queue only  
- [ ] Ear ownership confirmed for S0.4 filenames  

### Grok — after dual ack

- [ ] Create `spike/ov263-genai/` + side venv  
- [ ] Execute S0.1→S0.5 without bar moves  
- [ ] Write results note + fold Nexus ears  
- [ ] Stop at verdict; do not start S1–S3 without new call  

---

## 11. One-line ask

**Team: treat OpenVINO 2026.3 first-party Kokoro as a new falsifiable probe (S0), not a reopen of the parked decoder spike; ack or amend these bars before any 2026.3 install work.**

---

*Draft: Orchestrator (Grok 4.5), 2026-08-07. Not active until Nexus ack + Fable sign-off.*
