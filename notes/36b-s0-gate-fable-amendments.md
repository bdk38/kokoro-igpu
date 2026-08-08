# notes/36b — S0 gate: Fable sign-off folded (binding amendments)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator) — fold of Architect sign-off  
**Base gate:** [notes/36-s0-ov263-genai-kokoro-gate.md](36-s0-ov263-genai-kokoro-gate.md)  
**Fable source:** `Fable/Fable-note_26-s0-gate-signoff.md`  
**Status:** **FULL TEAM ACK** — Architect A1–A3 + **Nexus ack all three** (2026-08-07). Bars/verdicts unchanged. **S0 executable.**

---

## Architect checklist (complete)

- [x] S0.1–S0.5 bars sound (with A1–A3)  
- [x] Verdict vocabulary OK  
- [x] S2/S3 separation — no silent G3 reopen  
- [x] Freeze list OK  
- [x] No new predicted branch beyond B1–B5  

Fable design priority opinion: **P2** (after v1.1.8 ack; parallel OK). Nexus decides.

---

## Binding amendments (report-only — no pass/kill changes)

### A1 — Shape-JIT novel-length probe is **REQUIRED** (report-only)

After steady-state on fox is established, run **≥1 novel-length utterance** (text not previously synthesized in the session). Record **first-infer vs second-infer** wall time for that utterance.

- Still **not** a kill bar (unless multi-minute / unusable).  
- Exists so S0 can inform filing #1 (shape-keyed JIT) without a second session.  
- Fable pre-measurement prediction: novel-shape penalty survives into 2026.3 in the ~17–25 s class (within ~2×); collapse would be architecturally interesting.

### A2 — Record official GPU **execution precision** (report-only)

Capture resolved inference precision on the official GPU path (`ov::hint::inference_precision` or equivalent compiled-model / profile evidence): **f16 vs f32**.

- Informs filing #2 (f16 MatMul): ears PASS on f16 → likely supersede; forced f32 → filing strengthened.

### A3 — Driver / compute-runtime versions in `versions.json` (required artifact field)

Alongside pip freeze subset, record at least:

- `intel-opencl-icd` / compute-runtime version (dpkg and/or `clinfo` Driver Version)  
- IGC (`libigc2`) version  
- kernel `uname -r`  

(Current host after 2026-08-07 upgrade: driver **26.22.38646.7**, IGC **2.36.5**, kernel **7.0.0-28-generic** — re-query at probe time.)

---

## Unchanged from notes/36

- Sequence S0.1→S0.5 hard-gated  
- Verdict words: `S0-GO-product` | `S0-GO-demo` | `S0-CPU-only` | `S0-KILL` | `S0-INCONCLUSIVE`  
- S0 alone does **not** revive componentized fork; S3 needs new Fable gate  
- Ship freeze: no `scripts/kokoro_server.py`, no `models/patched/` from S0 Mechanic  
- Work tree: `spike/ov263-genai/`  
- CACHE_DIR restart remains **optional** but strongly preferred in-session if any GO-* lands  

---

## Nexus buy-in — **COMPLETE** (2026-08-07)

- [x] Ack S0 as notes/36 **+** 36b (A1–A3)  
- [x] Priority: **P2** (after v1.1.8 — done; parallel OK with commit queue / cache design)  
- [x] Ear ownership for S0.4 filenames — **Nexus** (PASS/FAIL by filename when quality in scope)

**Grok ack:** A1–A3 binding; dual-track env (notes/38) — S0.1 creates side venv only; no bar moves mid-run.

### Execution posture

- v1.1.8 shipped/pushed (`8854d24`) — ship queue head is now **repo commit** (spike + notes + WORKFLOW + dual-track), filings still post-S0-informed.  
- Response/chunk cache design may run **parallel** (Fable) — backend-agnostic.  
- S0.1+ may start on Nexus/Grok call without further gate edits.

---

*Fold complete. Canonical gate = notes/36 + this 36b. Fable note_26 + note_29 provenance. Nexus full ack 2026-08-07.*
