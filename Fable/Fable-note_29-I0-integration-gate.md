# Fable/note_29 — I0 Integration gate: official GenAI Kokoro as ship backend candidate

**Date:** 2026-08-07
**Author:** Fable (Chief Architect) — R per walk-back ladder (note_27 §4: GO-product earns the conversation via a separate ship gate)
**Status:** PROPOSAL — awaiting Grok review/amend + Nexus ack. Bars written before any integration code.
**Basis:** S0 closeout `notes/53` (**S0-GO-product**), notes/45–52, note_27 (ladder), note_28 + notes/39–42 (cache), notes/44 (comparables), notes/43 (v1.2.0 ship)
**Suggested fold slot:** `notes/54`

---

## 0. One-sentence bet

**The official OpenVINO 2026.3 GenAI Kokoro path (int8 v1.0-family pack, steady GPU RTF ~0.70) can be integrated as a selectable backend behind the existing v1.2.0 server API — inheriting the TTS cache and warm-pin machinery — without degrading the shipped product, and only then does the default question get asked.**

Integration ≠ cutover. The default stays **ort-cpu** until I0's verdict opens that decision explicitly, per the ladder.

---

## 1. Model identity — this is not just an engine swap (Nexus flag, promoted)

Nexus, on the record: *"we did stray from our original model to something newer and not as large."* Correct, and the gate treats it as a product-identity change with its own bars:

| Axis | Ship today | I0 candidate |
|------|-----------|--------------|
| Checkpoint | Kokoro **v0.19** | official **v1.0-family** (82M) |
| Precision | f32 ONNX | **int8** OV IR (f16 compute default, A2) |
| Size on disk | ~310 MB | **~109 MB** |
| Voice heard | af_bella (v0.19) | af_heart (v1.0) — audibly different, per S0.4 Nexus note |
| Provenance | community ONNX export, our patches | Intel official pack `OpenVINO/kokoro-82M-int8-ov` |

Consequences the bars must cover:

- **Voice continuity is a product decision, not an assumption.** I0.1 inventories the official pack's `voices/` directory. Prediction (falsifiable): a v1.0 **af_bella** exists in the pack. If it does, Nexus ears compare v1.0-af_bella against ship v0.19-af_bella and *choose* — continuity voice, new default voice, or offer both. If it doesn't, the voice change is user-visible by necessity and gets documented as such.
- **Cross-checkpoint numeric corr stays informative-only** (S0.4 precedent). Ears are the quality instrument across checkpoints, full stop.
- **The size win is real product value** on a budget box (−200 MB disk, smaller resident weights) and belongs in the eventual README language — after Validator sign-off, as always.
- Honest-log continuity: v0.19 + our patched graphs remain in the repo regardless of outcome. If Intel's pack regresses or disappears in a future release, the ship path of record still exists.

---

## 2. Architecture

### 2.1 Backend slot

`kokoro_server.py` gains backend id **`ovgenai-gpu`** (and trivially `ovgenai-cpu`) alongside `ort-cpu | ov-cpu | ov-gpu`. Wraps `Text2SpeechPipeline` from the S0-proven recipe (notes/47: explicit `ov.Tensor` speaker embedding, `language="en-us"`). Runs in the ship venv — which forces §3's convergence question.

### 2.2 The synthesis-unit question (C2 soundness re-derivation — read this twice)

The cache's soundness argument (note_28 §1) is **cache unit = synthesis unit**. On the ship path that unit is our `chunk_text` token-id chunk. The GenAI pipeline takes raw text and does its **own** phonemization/processing internally — so if we hand it whole requests, our C2 chunk keys no longer correspond to its synthesis unit, and the soundness argument breaks for this backend.

**Design decision (locked unless amended):** the server keeps its own chunker in front, and calls `generate()` **once per chunk**, concatenating with the existing assembly path. Then:

- The synthesis unit for this backend = one `generate()` call = one chunk → **C2 soundness argument re-derives cleanly.**
- C2 `text_unit` for this backend keys on **chunk text string** (`c2txt:` prefix), not our tokenizer's ids — the GenAI pipeline's internal tokenization is its own business and our ids don't describe it. `backend_id` in the key already firewalls cross-backend serving.
- Per-chunk generates also bound worst-case latency per unit and keep the per-chunk debug/evidence lines (peak/ref/gap/tail/cache) uniform across backends.
- **Trade-off named honestly:** per-chunk calls forgo any cross-sentence prosody the GenAI pipeline might apply to whole passages, same as the ship path today. Ears at I0.2 judge whether chunked GenAI output is clean at the seams (predict: yes — same concat discipline that passed 21/21 and 4/4).

C1 needs no re-derivation — it keys the whole request and stores final assembled PCM; backend-agnostic by construction.

### 2.3 Warm/cold strategy (A1 physics apply unchanged)

S0.5 A1: novel shapes cost ~25–30 s first-infer on this backend too. Mitigations, all ports of existing machinery:

- `KOKORO_WARM_TEXT` concept ports to the GenAI backend (pin utterances at startup; same shape-key physics proven by A1).
- TTS cache (C1/C2) neutralizes repeat traffic identically to today.
- README for this backend documents the first-novel tax in plain language; no hiding it behind steady-state numbers (measurement-honesty item 4 lineage).
- Out of I0 scope, parked for later: async background warm; official-path `CACHE_DIR` behavior across restarts (S0.3 hinted partial blob-cache coverage — worth its own small probe someday).

---

## 3. Runtime convergence — the end of dual-track (sequenced, not silent)

The server process runs in one venv. Integration therefore requires the **ship venv → OV 2026.3 + GenAI**, ending the dual-track pin from note_27/notes/38. Preconditions, per note_27 §5's own rule (ladder applies only after both tracks done):

1. **v1.2.0 push lands** (commit `8893249` — currently local, one Nexus call).
2. **Filings submitted** in their S0-informed final form (#1 strengthened; #2 reframed pack-dependent; #3 against our f32 graph with int8-path contrast). The 2026.2.1 repro environment is preserved by the repo lockfiles even after the venv moves — record that in the convergence note.
3. Then and only then: ship venv upgrade, recorded as `notes/NN-env-convergence.md`, superseding-in-part notes/38 per honest-log.

Regression exposure from the upgrade, with predictions:

| Path | Exposure | Prediction |
|------|----------|-----------|
| **ort-cpu default** | None structural — ORT bundles its own runtime | Byte-identical output pre/post upgrade (I0.4 verifies) |
| **TTS cache** | None — stdlib only | P0/P1 quick re-run green |
| **ov-gpu patched demo** | Recompiles under 2026.3 | Works or doesn't; either way it is **superseded for steady work** by the GenAI backend (notes/52 §7.3) and its disposition is an I0 outcome (§5), not a casualty |

---

## 4. Bars (written before code)

| Bar | Work | PASS | KILL / branch |
|-----|------|------|---------------|
| **I0.1 voice inventory + parity ears** | List official pack voices; if af_bella-class exists, generate matched set; Nexus ears + choice (continuity / new default / both) | Nexus voice decision recorded | No bella-class voice → not KILL; voice-change-documented branch |
| **I0.2 backend integration** | `ovgenai-gpu` behind existing API, per-chunk generate (§2.2), C1+C2 wired, warm-text port | Serves via `/v1/audio/speech`; within-backend P0/P1 byte-equality green; Nexus ears clean incl. chunk seams (short + multi set) | Seam artifacts ears-FAIL with no config fix → halt, re-derive chunking |
| **I0.3 served performance** | RTF through the **server** (not direct): fox + multi steady after warm; novel-tax measured once; A3 stack fields | Steady served RTF ≤ **1.0** fox and multi | Served overhead pushes > 1.0 → diagnose before verdict (predict ≤ 0.8 on S0.5's 0.70 direct) |
| **I0.4 regression** | ort-cpu byte-compare pre/post venv upgrade; cache P0/P1 re-run; `/health`, WebUI smoke | All green | ort-cpu drift = stop-ship for convergence, investigate |
| **I0.5 demo-path disposition** | ov-gpu patched backend: compile check under 2026.3; Nexus call | Explicit disposition recorded: keep as flag / mark legacy (code retained, honest-log) | — |

Ears throughout are **binding** (cross-checkpoint → byte-equality can't vouch for quality; it only vouches for cache consistency within the new backend).

### Verdict vocabulary

| Verdict | Meaning |
|---------|---------|
| **I0-GO-default-candidate** | All bars PASS → Nexus default decision formally opens (ort-cpu vs ovgenai-gpu vs per-use split). Not decided by this gate. |
| **I0-GO-optional-backend** | Integration sound; something (voice choice, served RTF margin, taste) argues ort-cpu stays default; ships as env-selectable backend |
| **I0-KILL** | Integration unsound on this host (seams, regression, instability) → official path stays a spike result; ship unchanged |

---

## 5. Scope and freeze

- **Touch:** `kokoro_server.py` (version → 1.3.0), requirements/lockfiles, README backend table (flags only until Validator).
- **Don't touch:** trim/assembly math (I0.2 *calls* it), `models/patched/` contents, spike tree (read-only reference), S0 side venv (retire only after convergence note lands).
- Loop per WORKFLOW: this note (design) → Grok review/amend + Nexus ack → lock note → Mechanic → probes → verdict.

## 6. Open questions for Grok pre-lock

1. GenAI `generate()` per-chunk call overhead — any fixed per-call cost (pipeline state, embedding upload) that punishes many-small-chunks? If material, chunk-packing size may want tuning for this backend.
2. Does the pack's `voices/` include the full v1.0 voice set (bella check), and are embeddings length-indexed the same way ((510,1,256) suggests yes)?
3. Speed parameter: GenAI API surface for rate control, or do we keep our resample-based speed path uniform across backends?
4. Memory: int8 pack resident + GenAI runtime vs current ort-cpu resident — headroom on 15 W box under RAPL (ties to the parked stress experiment, not a bar here).

## 7. One-line

**I0 integrates official GenAI Kokoro as a selectable backend behind the shipped API — per-chunk generates to keep C2 sound, warm-pin and cache ported, voice/checkpoint change treated as product-identity with Nexus ears binding, convergence sequenced after push + filings — and only its verdict opens the default question.**

---

*Fable (Chief Architect), 2026-08-07. Grok: review, answer §6, lock as notes/54-I0-lock on Nexus ack.*
