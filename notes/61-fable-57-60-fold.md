# notes/61 — Fable fold on notes/57–60 + I0.2 close

**Date:** 2026-08-08  
**Source:** `Fable/fable_57_58_59_60_response`  
**Author:** Grok (Orchestrator)  
**Status:** Folded — amendments bind I0.3/I0.4 prep; no bar reopen on I0.2

---

## 1. Fable accepts

- Waiver (58) + convergence (59) + **I0.2 PASS with G4 speed ears** — single-application `speed=1.2` confirmed; double-resample defect class **ruled out**.
- I0.2 correctly ear-bound for quality; cache byte-eq deferred is OK if **homed in I0.4**.

---

## 2. Binding amendments (I0.3 / I0.4)

| ID | Amendment | Action |
|----|-----------|--------|
| **F1** | I0.4 pre/post is **not** within-post determinism alone | Hash post-convergence ort-cpu fox against **`artifacts/webui_soak/fox_miss.wav`** (notes/43, v1.2.0 on **2026.2.1**). Multi-chunk vs v121 P0 artifacts same pattern. |
| **F2** | ovgenai within-backend P0/P1 byte-eq | **Fold into I0.4** alongside cache P0/P1 re-runs (do not drop). |
| **F3** | Cold multi ~142 s | Expected: per-chunk ⇒ **N novel JITs** vs S0.5 whole-text one-shot. **I0.3 steady only** for verdict. |
| **F4** | Warm-text for ovgenai | Pin **chunk-shaped** utterances, not only long whole passages (wrong shapes). |
| **F5** | Pack must not live only under spike | **Done this fold:** `models/kokoro-82M-int8-ov` is a **real copy** + `SHIP_PACK_IDENTITY.txt` (bin sha256 `c879cdd8…`). Spike tree remains reference. |
| **F6** | Filing #2 VERIFY | Can re-repro f16/f32 ONNX issue on **ship 2026.3** live — no 2026.2.1 resurrection required (notes/58 §3 still documents recoverability). |

### Fable I0.3 prediction (on record before run)

Served steady fox **≤ 0.85** RTF (S0.5 direct ~0.70 + server/cache/assembly overhead), under bar ≤ 1.0.

---

## 3. Early I0.4 teaser (executed at fold)

| Artifact | SHA256 |
|----------|--------|
| Pre: `artifacts/webui_soak/fox_miss.wav` (2026.2.1 / v1.2.0) | `6c7c7e6d3ee0b6962db29ae3da600dc53f54bcf0173b2bde8c84922dfb83d771` |
| Post: ort-cpu fox after convergence (notes/60 §4 / `/tmp/ort_a.wav`) | **same** |

**Exact match** — Fable’s “v1.3.0 didn’t touch ort-cpu synth; ORT bundles runtime” prediction **held** on fox. Full I0.4 still runs multi + cache matrix formally.

---

## 4. Pack identity (F5)

```text
models/kokoro-82M-int8-ov/          # first-class ship artifact (copy)
models/kokoro-82M-int8-ov/SHIP_PACK_IDENTITY.txt
openvino_model.bin.sha256=c879cdd88275b9bfa25e51204d969013d701ea8699e15f99fd1957caf75a29ab
voices=54
```

Symlink into `spike/ov263-genai/out/...` **removed**.

---

## 5. Board (aligned with Fable)

```text
I0.2 CLOSED PASS
→ I0.3 served-RTF (steady; chunk-shaped warm pins; fox+multi ≤1.0)   [verdict hinge]
→ I0.4 regression + F1/F2 (+ early fox pre/post already green)
→ I0.5 ov-gpu disposition
→ verdict word
→ filings at end
```

Default remains **ort-cpu** until later Nexus decision.

---

## 6. One-line

**Fable fold: I0.2 stands; I0.4 gains pre/post soak refs + ovgenai byte-eq; cold multi explained; pack promoted to models/; I0.3 next with chunk-shaped warm and ≤0.85 fox prediction.**
