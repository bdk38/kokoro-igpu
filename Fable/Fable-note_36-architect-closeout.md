# Fable/note_36 — Architect close-out: dual-product ship complete, board closed

**Date:** 2026-08-08
**Author:** Fable (Chief Architect)
**Type:** ARCHITECT CLOSE-OUT — acknowledges notes/75–76; verifies final execution; states the closed board and the reopening rules. No work items created.
**Related:** notes/70–76, Fable note_31–35, WORKFLOW.md, tags `poc-complete` (kokoro-igpu) · `prototype-complete` (kokoro-igpu-genai).

---

## 1. Final verification (architect, against both pushed repos)

| Check | Result |
|-------|--------|
| genai polish commit `722d075` vs note_35 §4 spec | **Exact** — D1 docstring replacement word-for-word; README §Open WebUI verbatim at the specified position (after Smoke, before Configuration); igt fingerprint line in GPU start block; 2 files, 18 insertions, 1 deletion, nothing else |
| `prototype-complete` still on `8987f74` | confirmed — polish landed on main without moving the tag, per spec |
| `poc-complete` on `f2ff370` (monorepo) | confirmed unchanged |
| notes/76 filings park | Correct form: VERIFY pack frozen intact, written unpark trigger, per-draft outcome checklist, submit order preserved — the decoder-spike pattern (park with evidence, not abandonment) applied at project scale |

## 2. Prediction ledger, closed

The gate-before-numbers discipline asks that predictions be scored, so the final entries go on record:

| Prediction (note, pre-execution) | Actual | Score |
|----------------------------------|--------|-------|
| note_33: ov-gpu patched compiles + speaks on converged 2026.3 ("my prediction — nothing in S0/I0 touched its op set") | Compiled, spoke, single-venv product shipped | **Correct** |
| note_33/32: R0 stranger gate is cheap and converts "finished" from adjective to verdict | R0 found a P0 (hardcoded sandbox paths), a voices-SHA mismatch, and a phantom script — all fixed pre-tag | **Correct, and load-bearing** — without R0 the tag would have shipped a clone that silently loaded sandbox models |
| note_34 §4: R1 passes first or second attempt; likeliest finding class = HF fetch/hash friction, not server behavior | First-attempt PASS, **zero findings** | Pass-branch correct; finding-class never fired — cleaner than predicted, because R0 had already flushed the shared lineage |

The asymmetry between R0 (three findings, one P0) and R1 (zero) is itself the closing argument for the stranger-rehearsal gate: the first rehearsal pays for every rehearsal after it.

## 3. The closed board

For the first time in the project's history, every track is terminal:

| Track | Terminal state | Reopening rule |
|-------|----------------|----------------|
| **PoC (Product A)** | SHIPPED — `poc-complete`; frozen-runnable at committed pins; `reproduce/2026.2.1/` provenance | None needed — reproducibility anchors to committed files, so upstream cannot break it retroactively |
| **Prototype (Product B)** | SHIPPED — `prototype-complete` + docs polish on main; appliance default `ovgenai-gpu`, v2.0.0 | Backlog items (blends-on-genai, chunk-overhead matrix, RAPL/E-core stress) each require a **new written gate** before work |
| **Default backend question** | RESOLVED on both faces — ort-cpu is the PoC's face; ovgenai-gpu is the appliance's identity | Closed; the question the I0 gate earned has been answered by repo topology rather than by one repo's flag |
| **Filings (4 drafts)** | PARKED (notes/76) — VERIFY pack intact, Nexus duplicate research pending | Unpark checklist in notes/76; per-draft file / comment / drop; submit order #2 → #3 → #1 |
| **Componentized decoder fork (O1–O4)** | PARKED (notes/34) with full RCA | New Fable gate + Nexus ack only — never a silent reopen |

No active work item. No pending handoff. Nothing owed by any seat.

## 4. What the record shows (architect's summary for the shelf)

The project set out to make an 82M-parameter TTS model speak on a 15 W budget iGPU that the ecosystem said couldn't do it, and it ends with two tagged, stranger-reproducible products: the original proof, still runnable from its own pins ("the original is still here, and still runs — prove it to yourself"), and an appliance built on the official pack that a stranger can clone and serve at warm-steady RTF ~0.73 with the tax stated in the same breath.

The methods mattered as much as the result, and they are all in the notes chain: gates written before numbers; predictions scored whether they landed or not; cold and warm never mixed in a claim after note_11; ears binding over metrics at every quality gate; negative results parked with root cause instead of deleted; and the final discipline — a claim you can only read is a concept, a claim you can run is a product — enforced twice, by R0 and R1, before either tag was allowed to exist.

Every verdict word in this project (`S0-GO-product`, `I0-GO-default-candidate`, R0/R1 PASS, PARKED ×2) was defined before the data arrived. That is the record I'd want a skeptic to audit.

## 5. Standing offer

When Nexus unpark s the filings, the drafts are architect-signed as VERIFY-ready and I'll fold any duplicate-search findings into per-draft dispositions. When any B-backlog item or the decoder fork warrants revival, the gate comes first — same as always.

## 6. One-line

**Close-out: `722d075` verified exact against note_35, both tags unmoved, filings parked in correct form, prediction ledger scored and closed — two products shipped by stranger-gate verdict rather than by declaration, every track terminal with a written reopening rule, and the board is, for the first time, empty.**

---

*Fable (Chief Architect), 2026-08-08. Grok: commit alongside notes/75–76 under the standing Co-authored-by convention. Nexus: it was a privilege to architect this one — the ears were always the gate that mattered.*
