# notes/58 — Nexus filings waiver for I0 convergence

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Authority:** Nexus explicit direction — “Waiver → I0.2” after WORKFLOW refresh  
**Status:** **WAIVER RECORDED** — unlocks Option A ship-venv convergence without GitHub submit

---

## 1. What is waived

Per I0 lock **G5** (notes/54) and Fable note_29 §3:

> Filings submitted **or** explicit Nexus waiver before ship venv → 2026.3 + GenAI.

**Nexus waives the filings-submit precondition** for the purpose of:

1. Ship venv convergence to OpenVINO **2026.3** + **openvino-genai** (notes/59)  
2. **I0.2** in-process `ovgenai-gpu` / `ovgenai-cpu` backend work  

Filings themselves are **not cancelled**. Drafts remain under `issues/`; Nexus stated they will be **completed and filed at the end** (notes/57).

---

## 2. What is not waived

| Item | Still holds |
|------|-------------|
| Product default | **ort-cpu** until later Nexus default decision |
| I0 bars I0.2–I0.5 | Written before code; must still PASS |
| Ship freeze on silent default flip | G6 |
| Decoder spike park | No silent reopen |
| Upstream honesty | Drafts must still VERIFY before submit |

---

## 3. Repro environment for filings

2026.2.1-era repro material remains recoverable via:

- git history / prior `requirements.lock.txt` snapshots  
- `venv-s0-ov263` is **2026.3** (S0 path) — not a 2026.2.1 freeze  
- Host captures under `issues/captures/`  
- notes/44 patched ov-gpu soak on **2026.2.1** ship stack (pre-convergence)

Convergence note (59) must record pre/post ship wheel versions so filings can cite stack identity honestly.

---

## 4. One-line

**Nexus waived filings-submit as I0 convergence gate; I0.2 may proceed after notes/59 venv upgrade; filings still file-at-end.**
