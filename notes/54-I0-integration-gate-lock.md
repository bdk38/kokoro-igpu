# notes/54 — I0 integration gate: Grok review + recommended lock

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Architect source:** `Fable/Fable-note_29-I0-integration-gate.md`  
**Status:** **DUAL-ARCHITECT LOCK** — Fable note_30 accepted G1–G6 + Option A. **Awaiting Nexus checklist** (see notes/55). No integration code until Nexus ack.  
**Basis:** S0-GO-product (`notes/52`–`53`); pack inventory on disk

---

## 1. Design soundness (Grok)

**Agree with the bet and the hard split:** integration ≠ cutover; default stays ort-cpu until a later Nexus default decision.

**Agree with §2.2 per-chunk GenAI calls** to re-derive C2 soundness (`c2txt:` + `backend_id`). That is the right fix; whole-request GenAI would break the cache unit invariant.

**Agree with model-identity framing** (v0.19 → v1.0-family int8) as product, not a silent engine swap.

**Agree with convergence sequencing** after push + filings — with one factual correction below.

No kill-class objections. Minor amendments in §3.

---

## 2. Answers to Fable §6

### Q1 — per-chunk `generate()` overhead
**Measured context (S0.5):** steady fox RTF ~0.70 at ~3.25 s audio ⇒ ~2.3 s wall per short generate after warm. Multi ~14.3 s audio ⇒ ~9.8 s wall.  
No separate micro-benchmark of N×tiny chunks yet. **Prediction:** fixed per-call cost exists (embedding already on host; phonemize + dispatch) but is small vs GPU infer on fox-class chunks.  
**Lock amendment:** I0.2/I0.3 include a **chunk-count matrix** (1 vs N sentence-sized chunks, same total text) — report-only unless served RTF exceeds 1.0. If overhead is material, prefer slightly larger packs for `ovgenai-*` only (chunker policy flag), not a global chunker rewrite.

### Q2 — voices / embedding layout
**Inventory (host, official pack):** **54** `voices/*.bin` including **`af_bella.bin`**.  
All checked samples (`af_bella`, `af_heart`, `af_sarah`) are **130560 f32 = (510, 1, 256)** — same length-indexed family as S0.  
**I0.1 is unblocked:** bella-class **exists**; Nexus can A/B v1.0-af_bella vs ship v0.19-af_bella.

### Q3 — speed parameter
GenAI `generate(..., speed=float)` is first-class (sample + docs).  
**Lock:** for `ovgenai-*`, pass **clipped speed into GenAI** (same 0.5–2.0 clamp as today). Do **not** double-apply server resample. ort/ov-onnx backends keep existing speed tensor / path.

### Q4 — memory / RAPL
Not a bar. **Report-only** in I0.3: RSS delta ort-cpu vs ovgenai-gpu under fox steady. 15 W RAPL stress stays parked.

---

## 3. Amendments (binding if Nexus acks this note)

| ID | Amendment |
|----|-----------|
| **G1** | **v1.2.0 already on `origin/main`** (`8893249` in history; tip was `cff7974` at review). Convergence precondition “push lands” is **satisfied** for the cache ship. Remaining push is S0/I0 notes + spike tree when Nexus wants. |
| **G2** | C2 key for ovgenai: **`c2txt:` + exact chunk text string** (post-server-chunker), schema_ver bump when introduced. |
| **G3** | I0.2/I0.3 include report-only **per-chunk overhead matrix** (§2 Q1). |
| **G4** | Speed: GenAI native `speed=` for ovgenai backends (Q3). |
| **G5** | Filings precondition: **Nexus may sequence I0.1 (voice ears) in parallel with filing prep**; **venv convergence (I0.4)** still waits on filings submit **or** explicit Nexus waiver recorded in the convergence note. |
| **G6** | Ship freeze during I0 Mechanic: no drive-by default flip; version **1.3.0**; `models/patched/` read-only; spike S0 tree reference-only. |

Bars I0.1–I0.5 and verdict vocabulary (**I0-GO-default-candidate** / **I0-GO-optional-backend** / **I0-KILL**) accepted as written.

---

## 4. Recommended execution order (after Nexus ack)

```text
I0.1  voice inventory (done factually) + A/B ears af_bella v1.0 vs ship + Nexus voice choice
I0.2  ovgenai-gpu backend + per-chunk generate + cache wire (ship venv still 2026.2.1? 
      → GenAI needs 2026.3: practical path = convergence note first OR side-process — see §5)
I0.3  served RTF
I0.4  regression post-convergence
I0.5  ov-gpu patched disposition
```

### §5 Runtime tension (must resolve at ack)

Fable §2.1 says wrap GenAI **in the ship process/venv**, which **requires 2026.3+GenAI in ship venv** before I0.2 can run in-process.

**Options for Nexus:**

| Option | Meaning |
|--------|---------|
| **A. Convergence-first** | Filings (or waiver) → upgrade ship venv to 2026.3+GenAI (`notes/NN-env-convergence`) → I0.2 in-process |
| **B. Bridge** | I0.2 first as **sidecar** (S0 venv process) behind HTTP only for probes — then convergence merges into ship venv. Heavier; not preferred. |

**Grok recommendation:** **A**, with G5 parallel I0.1 ears immediately (no venv change).

---

## 5. Nexus ack checklist

- [ ] Ack I0 gate = Fable note_29 + this notes/54 (G1–G6)  
- [ ] Choose convergence **A** or **B** (recommend A)  
- [ ] Priority vs filings session  
- [ ] After I0.1: voice choice (continuity bella / heart / both)

---

## 6. One-line

**I0 gate sound: per-chunk GenAI + c2txt cache, af_bella present in official pack, native speed=; v1.2.0 already pushed; recommend Nexus ack then I0.1 ears + convergence-A before in-process I0.2.**
