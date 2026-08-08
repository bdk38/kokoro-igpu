# notes/63 — Fable fold on I0.3 (notes/62)

**Date:** 2026-08-08  
**Source:** `Fable/fable_62_response`  
**Author:** Grok (Orchestrator)  
**Status:** Folded — I0.3 stands; no bar change

---

## 1. Prediction score

| Prediction | Actual | Result |
|------------|--------|--------|
| Served steady fox **≤ 0.85** | **0.728** | **HELD** |
| Served overhead small vs S0.5 ~0.70 | **~+0.03 RTF** | **HELD** |
| Multi steady ≤ 1.0 | **0.724** | **PASS** (bar) |
| Cold multi = multi-chunk JIT (F3) | **97 s** first multi | **Confirmed on served path** |

Fable explicitly endorses declining cold-confounded chunk-overhead rows (note_11 discipline) and deferring fair 1-vs-N steady to **I0.4-optional**.

---

## 2. Filing implication

Novel-tax row **+28.8 s served** completes filing **#1 (shape-JIT)** evidence across:

- direct GenAI (S0.5)  
- served product path (I0.3)  
- two wheels / stacks as applicable  

→ include in VERIFY pack when filings session runs.

---

## 3. Remaining bars (mechanical)

| Bar | Scope | Fable lean |
|-----|--------|------------|
| **I0.4** | pre/post fox (already matched notes/61); cache P0/P1; ovgenai byte-eq; WebUI smoke; optional 1-vs-N steady | no plausible fail given path |
| **I0.5** | patched ov-gpu disposition (Nexus records) | mechanical |

**Architect lean on eventual verdict word (not decided):** **`I0-GO-default-candidate`** on current evidence — opens default question; does **not** flip default.

---

## 4. Default-question frame (Fable — early, for Nexus)

Founding premise: **CPU offload on a budget headless box**. ort-cpu became default because GPU was not realtime; **ovgenai-gpu served ~0.73 steady** now can free CPU for the rest of the box.

| Option at verdict time | Meaning |
|------------------------|---------|
| **Cut over** | default → ovgenai-gpu |
| **Flag** | default stays ort-cpu; ovgenai selectable |
| **Split** | ovgenai-gpu default + ort-cpu fallback |

**Honest counterweights:** first-novel tax (tens of seconds; cache + chunk warm mitigate, don’t erase); checkpoint change (I0.1 already ruled); ort-cpu reliability.

**No Nexus answer required until I0.4–I0.5 + verdict word.** Frame only.

---

## 5. Board

```text
I0.1–I0.3 PASS
→ I0.4 regression matrix
→ I0.5 ov-gpu disposition
→ verdict word (lean I0-GO-default-candidate)
→ Nexus default decision (separate)
→ filings at end (#1 gets I0.3 novel row)
```

---

## 6. One-line

**Fable: I0.3 fox ≤0.85 held; overhead ~+0.03; F3 confirmed; filing #1 strengthened; lean I0-GO-default-candidate after I0.4/I0.5; default-question frame parked for Nexus — no flip now.**
