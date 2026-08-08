# notes/55 — I0 lock: dual-architect complete (awaiting Nexus)

**Date:** 2026-08-07  
**Status:** **FULLY ACKED** — Nexus 2026-08-07; I0.1 in progress  
**Code:** I0.1 only until convergence  

---

## Canonical I0 definition

| Doc | Role |
|-----|------|
| `Fable/Fable-note_29-I0-integration-gate.md` | Design + bars I0.1–I0.5 |
| `notes/54-I0-integration-gate-lock.md` | Grok review, §6 answers, G1–G6 |
| `Fable/Fable-note_30-I0-lock-acceptance.md` | Fable accepts G1–G6; **Option A** locked |
| **This note** | Dual-architect complete; Nexus ack surface |

### Locked order (Option A)
```text
I0.1 voice A/B ears (parallel OK; no venv change)
Filings submit or Nexus waiver  →  ship venv → 2026.3+GenAI (convergence note)
I0.2 ovgenai-gpu in-process (per-chunk generate, c2txt, native speed=)
I0.3 served RTF
I0.4 regression
I0.5 ov-gpu patched disposition
→ verdict opens default question (does not decide it)
```

### Fable note_30 extras folded
- **G4 emphasized:** I0.2 ear set includes **one speed≠1.0** file to prove single-application (no double resample).  
- **af_bella prediction held** (54 voices, (510,1,256)).  
- Filings drafting is Fable R; ready in parallel when Nexus says go.

---

## Nexus checklist (notes/54 §5) — **COMPLETE** (2026-08-07)

- [x] **Ack I0** = note_29 + notes/54 (G1–G6) + note_30  
- [x] **Convergence Option A** confirmed  
- [x] **Priority:** **I0.1 ears first** (filings parallel when Fable drafts)  
- [x] **Voice policy (I0.1):** **BOTH first-class** — default **af_bella** continuity; **af_heart** selectable (HF A; excellent ears). Ship bella deeper / official bella brighter (notes/56).  

---

## On your ack, Grok will

1. Run **I0.1** — generate v1.0 `af_bella` vs ship v0.19 `af_bella` (+ optional heart) WAVs for ears  
2. Hold **I0.2** until convergence (filings or waiver)  
3. Not touch ship default or ship venv until ordered  

---

## One-line

**I0 dual-architect locked (Option A, G1–G6); Nexus ack opens I0.1 ears; in-process backend waits on convergence.**
