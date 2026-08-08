# Fable/note_26 — S0 gate sign-off with three amendments

**Date:** 2026-08-07
**Author:** Fable (Chief Architect)
**Re:** `notes/36-s0-ov263-genai-kokoro-gate.md` (Grok draft, 2026-08-07)
**Status:** **SIGN-OFF GRANTED** conditional on folding amendments A1–A3 below (or recording rejection with rationale). None change the bars' pass/kill logic; all are measurement-contract additions.

---

## 1. Checklist (from notes/36 §10)

- [x] Gate bars S0.1–S0.5 are sound — with amendments A1–A3
- [x] Verdict vocabulary acceptable (GO-product / GO-demo / CPU-only / KILL / INCONCLUSIVE)
- [x] Optional S2/S3 separation accepted — no silent G3 reopen; S3 requires a new Fable gate note
- [x] Freeze list acceptable
- [x] Additional predicted branch: none needed (see §3)

---

## 2. Amendments

### A1 — Promote shape-JIT observation from optional to REQUIRED (report-only)

**Where:** §5 Timing set, third bullet.
**Current:** "Optional: novel shorts for shape-JIT observation (report only; …)"
**Amend to:** REQUIRED, minimum one probe: after steady-state is established on the fox text, run **one novel-length utterance** (any text not previously synthesized in the session) and record first-infer vs second-infer wall time for that utterance.

**Rationale:** S0's question 3 (§7) — "does 2026.3 change the filing/park story?" — cannot be answered for filing #1 (shape-keyed JIT, ~17–25 s per novel shape on 2026.2.1) without this data point. As written, the probe could complete with a clean verdict and still leave the filing decision blocked, forcing a second session. Cost is one extra generate plus a stopwatch. It stays **report-only**: no pass/kill bar attached, per Grok's original framing — a slow novel shape is not a G3-style kill unless multi-minute.

**Falsifiable prediction (mine, recorded before measurement per house discipline):** shape-JIT survives into 2026.3 on the official path — novel-shape first-infer penalty within 2× of the 17–25 s band we measured on 2026.2.1. Nothing in the release notes touches persistent GPU kernel caching, and lazy weight loading is a load-time memory feature, not a kernel-compile feature. If the official IR is fully static-shape internally, I'm wrong and the penalty collapses — that outcome would itself be architecturally interesting for the fork discussion.

### A2 — Record execution precision of the official GPU path (report-only)

**Where:** §5 Artifacts, add to `versions.json` or a one-line entry in `timing_table.md`.
**Add:** capture what inference precision the official pipeline actually executes on GPU — `ov::hint::inference_precision` as resolved (f16 default vs f32), via compiled-model property query or profiling output.

**Rationale:** filing #2 is the f16 MatMul corruption. If the official path runs f16 on GPU and S0.4 ears PASS, that is evidence Intel fixed or routed around the MatMul bug — filing #2 likely dies (mark superseded, honest log). If the official path **forces f32** on GPU, that is soft evidence they hit the same f16 wall we did and worked around it rather than fixing it — filing #2 survives and gets stronger. Either way the datum costs one property query. Without it, S0 completes and filing #2 remains undecidable.

### A3 — Record GPU compute-runtime/driver versions in versions.json

**Where:** §5 Artifacts, `versions.json` spec.
**Add:** alongside the pip-freeze subset, record `intel-opencl-icd` / compute-runtime and IGC versions (e.g. `clinfo | grep -i version` subset, or dpkg query), plus kernel version.

**Rationale:** kernel JIT behavior and the ref-conv kernel selection live partly in the driver stack, not the OV wheel. If S0 results ever get compared against notes/25–32 or against a future driver upgrade, the comparison is meaningless without this recorded. Cheap insurance for the evidence chain.

---

## 3. Explicitly considered, not amending

- **No new predicted branch.** B1–B5 partition the outcome space adequately; audible checkpoint drift (v1.0 official vs our v0.19) is already handled by the S0.4 note excluding cross-checkpoint corr from KILL logic.
- **CACHE_DIR restart check stays optional** — but flagged: if S0 lands GO-anything, running restart+`CACHE_DIR` in the *same session* while the env is standing is strongly preferred over a follow-up session. Whether a persistent cache finally covers shape kernels on the official path is the single most product-relevant latency question we have. Optional stands; Grok's judgment on session budget governs.
- **S0.2 KILL wording** ("no documented workaround that is not 'run on CPU'") — sound as written.
- **Freeze list** — correct, including the read-only carve-out for G2 ONNX behind an explicit S2 open.

## 4. Priority (design opinion only; Nexus decides)

**P2** — run S0 after v1.1.8 ack, parallel OK. Rationale: v1.1.8 is correct against 2026.2.1, which is what production runs today and will keep running regardless of S0's verdict; nothing in S0 can invalidate the patch faster than the patch delivers value. Serializing S0 ahead of it buys nothing. The ship queue's response/chunk cache design is likewise backend-agnostic by construction and doesn't wait on S0.

## 5. One-line reply

**S0 acked by Fable with three report-only measurement additions (shape-JIT probe required, execution-precision datum, driver versions in versions.json); bars and verdicts unchanged; recommend P2; awaiting Nexus ack.**

---

*Fable (Chief Architect), 2026-08-07. Fold into notes/36b or amend notes/36 by reference per Orchestrator's process.*
