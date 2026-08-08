# notes/65 — Fable fold on I0.4 (notes/64)

**Date:** 2026-08-08  
**Source:** `Fable/fable_64 response`  
**Author:** Grok (Orchestrator)  
**Status:** Folded — I0.4 stands; doctrine + I0.5 rec recorded

---

## 1. Fable accepts I0.4 PASS

- **F1 strongest form:** exact SHA fox across venv upgrade **and** 2026.2.1→2026.3.0 **and** v1.2.0→v1.3.0 — convergence risk **formally retired**.
- False-FAIL RCA (§3) correct: cold-vs-warm = note_11 honesty bug in byte-comparison clothing.
- Cache green schema 3; WebUI path intact; daily ort-cpu driver stable.

---

## 2. Binding doctrine extension (ovgenai validation)

**Record before it bites later:**

On `ovgenai-gpu`, **cold first-infer numerics ≠ warm numerics** for the same text (observed multi: corr **0.9998**, maxdiff **~0.031**, same length).

**C2 writes on miss** — and novel text misses are usually **cold**. Therefore a cached chunk can permanently store the **cold-numerics** rendering; a later warm fresh synth of the same text may differ by that hair.

| Claim | Status |
|-------|--------|
| Product bug / cache corruption | **No** |
| Cache deterministic about what it serves | **Yes** |
| P1 hit-vs-stored byte-eq | **Unaffected** |
| Ears distinguish 0.9998 | **No** |

### Validation doctrine (ovgenai-gpu)

> **Byte-equality holds within a warmth class; across warmth classes, corr + ears are the instruments.**

### ovgenai-cpu

Residual warm nondeterminism observed; **byte-eq doctrine does not extend there**. Not product path; corr covers. Do not rediscover as cache-corruption scare.

Preserve this paragraph in I0 closeout.

---

## 3. I0.5 — Architect recommendation (Nexus decides)

| Option | Meaning | Fable lean |
|--------|---------|------------|
| **legacy-marked** | Code retained (honest-log); README: superseded for steady work by ovgenai-gpu; no maintenance | **Recommended** |
| **keep-as-flag** | Stays selectable; compile-check burden every runtime bump | Optional |

Rationale: ovgenai-gpu dominates patched ov-gpu ~**7×** on steady RTF with same offload proof class. Patched path earned the record as “iGPU can speak at all”; record is where it best serves.

**Pure Nexus call** — no code until you choose.

---

## 4. After I0.5

```text
I0.5 disposition (Nexus)
→ verdict word: lean I0-GO-default-candidate (board agrees)
→ default decision (cut over / flag / split) — separate Nexus call
→ filings VERIFY + submit (endgame)
→ commit sweep
```

Gate is **one checkbox** from I0 bars complete.

---

## 5. One-line

**Fable: I0.4 stands; ovgenai byte-eq is warmth-class-scoped; I0.5 recommend legacy-mark patched ov-gpu; then I0-GO-default-candidate + default decision + filings + commit.**
