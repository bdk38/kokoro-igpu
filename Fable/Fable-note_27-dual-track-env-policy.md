# Fable/note_27 — Dual-track env policy, rollback spec, and pre-registered walk-back ladder

**Date:** 2026-08-07
**Author:** Fable (Chief Architect) — capturing Nexus decisions from chat into the record
**Re:** `notes/36` + `notes/36b` (S0 gate, signed), `notes/37` (2026.3 upgrade record), `notes/00-host-inventory.txt` (2026-08-07 refresh)
**Status:** Nexus decision recorded; Fable acked; **awaiting Grok ack** before rollback execution. Grok may amend the rollback checklist (§3) on mechanical grounds; policy items (§1, §4, §5) are Nexus calls, not open for silent revision.

---

## 1. Decision (Nexus): dual-track runtime pinning

The ship path and the S0 probe run on **separate runtime stacks** until each reaches its own definition of done:

| Track | Runtime | Env | Rationale |
|-------|---------|-----|-----------|
| **Ship** (v1.1.8, smoke, commit, filings) | **OpenVINO 2026.2.1** (rolled back) | `/data/intel-igpu-tts/venv` | The working product — "said couldn't be done" — completes on the runtime it was proven on. Full provenance (surgery, notes, honest-logs) lives in the repo against this stack. |
| **S0 probe** (official Kokoro) | **OpenVINO 2026.3 + GenAI** | side venv per notes/36 S0.1 | 2026.3 evaluated in isolation, exactly as the gate originally specified. |

This supersedes the in-place upgrade of the ship venv recorded in notes/37. The upgrade was a legitimate Nexus call at the time; the dual-track pin is the refinement now that S0 exists to consume 2026.3. Notes/37 stays in the log, marked superseded-in-part per honest-log convention (the driver upgrade portion stands — see §2).

Secondary benefit, for the record: the three upstream issue packs were captured on 2026.2.1. Keeping that stack alive means maintainer questions can be answered with live re-runs rather than "we can no longer reproduce our own evidence."

## 2. Honesty caveat: the driver stack does not roll back

The Aug 7 host refresh moved compute-runtime to **26.22.38646.7**, IGC to **2.36.5**, kernel to **7.0.0-28**. These stay. Therefore:

- Original measurements (notes/25–32 and earlier): **wheel 2026.2.1 + old driver stack.**
- See-it-through ship env after rollback: **wheel 2026.2.1 + new driver stack.**
- These are not identical environments. Any new ship-track numbers carry the new stack identity per WORKFLOW measurement-honesty item 7 / gate A3.

I do **not** recommend downgrading drivers to chase bit-identical provenance — risk and effort for no product value. Instead: one **post-rollback smoke** (§3, final item) validates that the product behaves on the mixed stack. ort-cpu default is structurally insulated (onnxruntime-openvino bundles its own runtime; CPUExecutionProvider never touches the OV wheel). The ov-gpu demo path compiles through the driver and is the reason the smoke exists.

## 3. Rollback checklist (Grok / Mechanic — ship venv)

1. `openvino` → pin **2026.2.1** in `/data/intel-igpu-tts/venv`.
2. **Remove** `openvino-genai` and `openvino-tokenizers` from the ship venv entirely. GenAI 2026.3.0.0 hard-requires the 2026.3 wheel and was never a ship dependency; it belongs to the S0 side venv only.
3. Revert `requirements.txt` / `requirements.lock.txt` to the 2026.2.1 pin set.
4. Compile cache: **fresh versioned dir** (e.g. `cache/openvino-2026.2.1-drv2622/`). Do not repoint at the pre-upgrade 2026.2 blob dir — those blobs predate the driver upgrade and blob-validity across driver bumps is exactly the confound A3 exists to catch. Let it repopulate.
5. Update `notes/00-host-inventory.txt` to reflect the dual-track state (ship venv pins + side venv pins as two entries).
6. Record the rollback as `notes/NN-env-rollback-dual-track.md` (or amend notes/37 by reference), including the §2 stack-identity caveat verbatim.
7. **Post-rollback smoke** (ship path, freeze lifted by Nexus for this item only): fox utterance on ort-cpu and ov-gpu demo backends; Nexus ears by filename; one warm steady-state RTF datum per backend. Log in the same note. This is a smoke, not a matrix — its only claim is "product behaves on wheel 2026.2.1 + new driver."

## 4. Pre-registered walk-back ladder (Nexus posture: no farther than we have to)

Recorded **before** S0 produces numbers, same discipline as bars-before-measurements. Retirement decisions made after results exist are vulnerable to sunk-cost attachment in one direction and new-shiny bias in the other. The ladder makes disposition mechanical at verdict time:

| S0 verdict | Walk-back |
|------------|-----------|
| **S0-KILL / S0-CPU-only / S0-INCONCLUSIVE** | **None.** Ship stays ort-cpu default + patched ov-gpu demo. All three filings survive and strengthen ("still broken in the release announcing Kokoro GPU support"). |
| **S0-GO-demo** | Retire the **patched ONNX demo backend** and its maintenance burden (warm-bucket/shape-key machinery goes with it — it exists to serve that path). ort-cpu remains default. Filings decided individually on A1/A2/S2 data. |
| **S0-GO-product** | Full walk-back becomes **discussable, not automatic**: official path as candidate default requires a separate ship gate per notes/36 §2. GO-product earns the conversation, not the cutover. |

Invariants on every rung:

- **Response/chunk cache survives all branches.** Black-box, backend-agnostic by construction — the one investment S0 cannot invalidate. It remains the top product bet regardless of verdict.
- **Honest-log applies to code, not just findings.** Whatever is retired is marked superseded in the repo, never deleted. The surgery, bucket scheme, and notes/25–32 are the provenance explaining *why* the official path won (if it wins) and the fallback spec if Intel's early release regresses in 2026.4.
- **Nothing is retired before both tracks reach done** (§5). Even maximal walk-back is not square one: the goal was always "this iGPU speaks Kokoro well on a budget box," not "our export ships." If upstream finishes the road, our stack held the position until they caught up — and produced four filings and a validated seam recipe doing it.

## 5. Definitions of done (both incomplete today; explicit per Nexus)

- **Ship track done** = v1.1.8 ack → rollback + smoke (§3) → repo commit (spike tree, notes, Fable notes, WORKFLOW, artifacts) → filings submitted (post-S0-informed, per A1/A2/S2).
- **S0 done** = verdict word in a results note, ears folded.

Walk-back ladder (§4) applies only after **both**.

## 6. Priority implication

Dual-track restores **P2** as the natural priority: the rollback-and-close work *is* the ship queue, and S0 runs parallel in its own venv without touching it. My P2 recommendation from note_26 stands re-strengthened. Nexus box regardless.

## 7. One-line summary

**Ship completes on 2026.2.1 (wheel rolled back, drivers stay — caveat recorded), S0 evaluates 2026.3 in a side venv, a pre-registered ladder governs any post-verdict walk-back, and nothing our working product is built on gets retired before both tracks are done.**

---

*Fable (Chief Architect), 2026-08-07. Grok: ack or amend §3 mechanically; fold into notes/ per handoff contract.*
