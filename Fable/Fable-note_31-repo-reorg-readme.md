# Fable/note_31 — Repo reorganization + README restructure (post I0-GO-default-candidate)

**Date:** 2026-08-08
**Author:** Fable (Chief Architect)
**Status:** PROPOSAL — Grok review (path mechanics) + Nexus ack. No moves until locked.
**Context:** I0 verdict **I0-GO-default-candidate** (Nexus, 2026-08-08). Default decision formally open, not made. This note reorganizes the *container*, not the product.

---

## 0. Principles (constraints on any reorg)

1. **Honest-log extends to structure.** Nothing is deleted; notes are immutable; every move is `git mv` (history/blame preserved) and recorded in one reorg note with an old→new path table. Old notes will textually reference old paths — that's correct historiography, resolved by the table, never by rewriting notes.
2. **Product-first at root.** A stranger cloning the repo should hit the server, the models, and the README before they hit the archaeology.
3. **The story stays navigable.** Sixty-plus notes across four arcs is an asset only if indexed. One `INDEX.md` maps arcs → note ranges → verdicts.
4. **Nothing presupposes the default decision.** README and structure present ort-cpu as current default, ovgenai-gpu as the GO-default-candidate. The decision note, when it comes, edits one section.

## 1. Proposed tree

```
/
├── README.md                      # restructured — §3 below
├── WORKFLOW.md
├── LICENSE / CREDITS.md           # hexgrad Kokoro (Apache-2.0), Intel OV pack
├── requirements.txt / requirements.lock.txt
├── server/
│   └── kokoro_server.py           # the product (git mv from scripts/)
├── scripts/                       # probe runners, smokes, utilities (i0_*, s0_*, monitors)
├── models/
│   ├── kokoro-82M-int8-ov/        # first-class official pack, hash in MODELS.md
│   ├── kokoro-v0_19.onnx          # ort-cpu model of record
│   ├── patched/                   # LEGACY-marked per I0.5 (see §2)
│   └── MODELS.md                  # provenance: source, hash, role, status
├── docs/
│   ├── INDEX.md                   # the map (arc → notes → verdict)
│   ├── notes/                     # notes/00–NN (git mv, immutable)
│   ├── architect/                 # Fable notes 26–31+
│   └── REORG.md                   # old→new path table (this reorg's record)
├── evidence/
│   ├── ship/                      # artifacts+logs: v11x, v120/v121 cache, i0_*
│   └── spikes/                    # artifacts+logs: g-series, s0_*
├── spikes/
│   ├── ov263-genai/               # S0 tree (reference; venv-s0 retire noted)
│   └── decoder/                   # parked componentized spike (park intact)
├── issues/                        # filings 1–3 + captures (endgame pending)
└── cache/                         # runtime only — .gitignore
```

Judgment calls, stated: `server/` vs keeping `scripts/kokoro_server.py` — I propose the split because the product deserves to not live among probe runners; Grok may veto on tooling friction. `evidence/` consolidation is the riskiest move (most referenced paths) — if Grok judges the old→new table insufficient protection, fallback is leaving `artifacts/` and `logs/` in place and doing only the docs/ + models/ + server/ moves. Either is acceptable; the table is mandatory in both.

## 2. Riders folded into the reorg commit

- **I0.5 disposition record** (pending Nexus one-line): recommendation stands — `models/patched/` **legacy-marked**: retained, README-noted as superseded for steady work by ovgenai-gpu (7× on RTF, same offload proof), no forward maintenance. It stays in `models/` because it is a model artifact of record, with LEGACY status in MODELS.md.
- **Warmth-class doctrine** (notes/64 §3 extension): one paragraph in the I0 closeout — for `ovgenai-gpu`, byte-equality is warmth-class-scoped (cold first-infer numerics ≠ warm; C2 may cache the cold rendering); across warmth classes, corr + ears are the instruments; `ovgenai-cpu` excluded from byte-eq doctrine entirely.
- **S0 side venv retirement** noted (interpreter converged; tree stays as evidence).
- `.gitignore`: `cache/`, `*.pid`, venv dirs.

## 3. README restructure

Current README grew as an operator's manual for us. New structure writes for three readers in order: someone who wants to *use* it, someone who wants to *believe* it, someone who wants to *read the story*.

```
1. Header — what this is
   One paragraph: OpenAI-compatible Kokoro TTS server for budget Intel boxes
   (Alder Lake iGPU class); realtime GPU synthesis via OpenVINO GenAI;
   CPU path; response+chunk caching. One sentence of the premise: CPU offload
   on hardware "said couldn't do it."

2. Status table
   Backends: ort-cpu (default) · ovgenai-gpu (GO-default-candidate, realtime)
   · ov-gpu patched (legacy) — with Validator-signed numbers only:
   served steady RTF 0.73 fox / 0.72 multi (ovgenai-gpu), 0.40-class (ort-cpu).

3. Quickstart
   Install (requirements + pack pull with hash), run command, one curl,
   Open WebUI wiring (base URL, split setting, the voices note).

4. Configuration
   Full env table: backend select, KOKORO_TTS_CACHE*, KOKORO_WARM_TEXT
   (chunk-shaped guidance), KOKORO_DEFAULT_VOICE, model paths.

5. Performance honesty          ← the distinctive section
   Steady vs first-novel in plain language: warmed/repeat shapes are
   realtime-class on GPU; the FIRST synthesis of a novel-length text pays
   tens of seconds (shape-JIT, upstream filing linked); cache + warm pins
   are the mitigations; never quote steady RTF as first-utterance latency.
   This is measurement-honesty item 4 promoted to user-facing doc.

6. Voices
   54-voice official pack; default af_bella (continuity), af_heart
   first-class alternate; ship-vs-official bella timbre note (deeper vs
   brighter) recorded honestly; blends ort-only for now.

7. Architecture (short)
   chunker → per-chunk backend synth → trim/assembly → C1/C2 cache,
   cache unit = synthesis unit; link to docs/INDEX.md for depth.

8. The story & evidence
   Three paragraphs + link to docs/INDEX.md: the arcs (ship v0.19 surgery →
   cache → S0 official-path probe → I0 integration), the gate discipline,
   the verdicts. Where "probably a waste of time, do it anyway" ended up.

9. Upstream contributions
   Filings 1–3 (links once submitted), MIOpen cross-reference.

10. Limitations & roadmap
    Cold tax, blends, single-process; default decision status (open);
    parked: RAPL stress, E-core pinning, decoder spike (parked with RCA).

11. Credits & license
```

Section 2/5 numbers enter only with Validator sign-off — which I0.3/I0.4's signed probes now provide for the ovgenai figures; Validator confirms the exact wording at reorg review.

## 4. Sequencing

```
Nexus ack (+ I0.5 one-line) → Grok path-mechanics review (evidence/ go or fallback)
→ reorg branch: git mv set + REORG.md + INDEX.md + MODELS.md + README rewrite
→ Validator: README claims pass
→ single reorg commit → then filings endgame → then default decision note
```

Reorg lands **before** filings submit so the filing links point at final paths.

## 5. One-line

**Move the archaeology into docs/ and evidence/, put the product at the root, index the story, legacy-mark the patched path per I0.5, and rewrite the README for user → skeptic → reader in that order — all by git mv with one old→new table, nothing deleted, and no section presupposing the default decision.**

---

*Fable (Chief Architect), 2026-08-08. Grok: path mechanics + evidence/ go/fallback call; Nexus: ack + I0.5 line.*
