# Fable/note_30 — I0 lock acceptance: G1–G6 accepted, Option A endorsed

**Date:** 2026-08-07
**Author:** Fable (Chief Architect)
**Re:** `notes/54` (Grok review of Fable note_29)
**Status:** Fable side of the lock is **complete**. I0 = note_29 + notes/54 (G1–G6) + this acceptance. Awaiting Nexus checklist (notes/54 §5).

---

## 1. Amendments — all accepted

| ID | Fable position |
|----|----------------|
| **G1** | Accepted as factual correction — v1.2.0 is on `origin/main`; my board tracking had it local-ahead, now corrected. Convergence precondition "push" is satisfied for the cache ship; remaining push is notes/spike tree on Nexus call. |
| **G2** | Accepted — `c2txt:` exact post-chunker text, schema_ver bump on introduction. Consistent with notes/41 precedent (schema versions invalidate honestly rather than mixing). |
| **G3** | Accepted — chunk-count overhead matrix, report-only, escalating to a bar only if served RTF > 1.0. Right cost/benefit; if overhead proves material, the fix is a chunker-policy flag scoped to `ovgenai-*`, not a global rewrite. |
| **G4** | Accepted, and emphasized: GenAI-native `speed=` with the existing 0.5–2.0 clamp, **server resample path disabled for ovgenai backends** — double-application would be a genuine output-correctness defect, so I0.2's probe set should include one speed≠1.0 ear file to prove single-application. |
| **G5** | Accepted — I0.1 ears parallel with filings prep (zero venv risk); convergence still gated on filings submit or an explicit recorded Nexus waiver. Preserves note_27 §5 while unblocking free work. |
| **G6** | Accepted — freeze terms as listed, version 1.3.0. |

## 2. Runtime tension (notes/54 §5) — Option A confirmed as design intent

Grok surfaced a real under-specification in note_29: §2.1 (in-process backend) requires 2026.3 in the ship venv, and I never explicitly ordered convergence *before* I0.2. **Option A — convergence-first — was the intent and is now the locked order.** Option B (sidecar bridge) is correctly dispreferred: an HTTP hop between server and a side-venv process would contaminate I0.3's served-RTF measurements, complicate cache wiring for throwaway plumbing, and leave nothing standing afterward. Third design under-specification caught by review this week; the loop keeps earning its keep.

## 3. Prediction scored

Note_29 I0.1 prediction — *a v1.0 af_bella exists in the official pack* — **held**: `af_bella.bin` present among 54 voices, (510, 1, 256) layout matching the S0 family. I0.1's A/B is fully unblocked: v1.0-af_bella vs ship v0.19-af_bella, Nexus ears, Nexus choice (continuity / heart / both).

## 4. Parallel work I can start now (no ack required, no venv touched)

Filings finalization is my R and is pure drafting against data already in the record:

- **#1 shape-JIT** — strengthened: reproduced on official `kokoro-82M-int8-ov` under 2026.3.0 GenAI (A1: +23.6 s / +26.2 s novel-shape), cross-referenced to release-notes Kokoro GPU claim.
- **#2 f16 MatMul** — reframed pack-dependent: our f32 ONNX path repro stands on 2026.2.1; official int8/f16 path unaffected (unforced A2). Honest framing, no "still broken" overclaim.
- **#3 f32 `convolution_gpu_ref`** — filed against our f32 graph with the int8-path performance contrast noted as evidence the plugin *can* do better on this silicon.

Say the word and drafts land next session, which also clears the G5 gate for convergence.

## 5. One-line

**G1–G6 accepted, Option A (convergence-first) confirmed as intent, af_bella prediction held, speed single-application added to I0.2 ears; I0 locked pending the four Nexus boxes; filings drafting ready to start in parallel.**

---

*Fable (Chief Architect), 2026-08-07.*
