# notes/70 — Finished product identity + repo boundary (Grok team input)

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Audience:** Nexus + Fable (Chief Architect)  
**Status:** **DISCUSSION** — no tree moves, no default change from this note  
**Related:** Fable note_31 (reorg/README); notes/66–69 (I0.5, verdict, cutover, filings hold); live default today = `ovgenai-gpu` (notes/68)

---

## 0. Purpose

Nexus asked for team input before any large commit or reorg. Core direction (paraphrase):

> Make the **existing repo whole** as a **finished product**. The original work — Kokoro on Intel iGPU **without** requiring OV 2026.3 GenAI and **with** the **old ONNX** model — must be reproducible from the repo. **Proof is hearing it run**, not reading notes. A concept that only exists as lab notes never materialized.

This note is Grok’s position for Fable to amend and Nexus to decide against.

---

## 1. What “finished product” means (acceptance)

A stranger who never read our notes can:

1. **Clone** the repo (requires we **commit + push**).  
2. **Install** from pinned requirements (one primary path; see §4).  
3. **Fetch models** via documented URLs + **SHA256** (`MODELS.md` and/or a fetch script) — no tribal knowledge.  
4. **Start the server** with one documented command.  
5. **curl or Open WebUI** → **hear** intelligible speech.  
6. Optionally exercise **iGPU** (`ov-gpu` patched and/or `ovgenai-gpu`) with honest RTF language.

**Fail:** “Read notes/34 and trust us.”  
**Pass:** WAV or Read Aloud from a clean follow-of-README.

Notes, WORKFLOW, spikes, filings remain **lab book + provenance**, not the product itself. They must stay navigable (`INDEX.md`) but must not be the only proof.

---

## 2. Two eras in one tree (name them)

| Era | Identity | Artifacts |
|-----|----------|-----------|
| **A — ONNX / proof era** | “We made community Kokoro v0.19 speak on Xe-LP” | stock + patched ONNX, trim/warm, ort-cpu, ov-gpu offload proof, decoder spike **parked**, measurement honesty |
| **B — GenAI / integration era** | Official `kokoro-82M-int8-ov`, OV 2026.3+GenAI, I0, optional/default GPU path | `ovgenai-*`, pack under `models/`, S0/I0 notes, cache still applies |

Nexus direction: **Era A must be a complete, demoable product** regardless of speed. Era B is real work and may stay in-tree, but must **not erase** Era A’s front door.

Fable note_31 optimized for *navigable monorepo* and (at write time) an open default decision. **Update:** default was cut over to `ovgenai-gpu` (notes/68). Any README/reorg must not pretend the default is still undecided — unless Nexus **reverts** product default as part of finishing Era A framing (§3).

---

## 3. Default backend — decision surface for Nexus

Live code/docs today: **default `ovgenai-gpu` (v1.4.0)**.

For “this repo’s finished product = ONNX-era proof,” pick one:

| Option | Default | README primary path | When it fits |
|--------|---------|---------------------|--------------|
| **A** | `ort-cpu` | ONNX proof first | Strongest match to “original work always runs” |
| **B** | `ovgenai-gpu` | GenAI first; ONNX in “Reproduce the original proof” | Only if Era B *is* the product face |
| **C** | either | **Two equal Run blocks**: Proof (ONNX) + Modern (GenAI) | Honest dual product; default is secondary |

**Grok lean for *this* repo’s identity:** **A or C**.  
- **A:** stranger always gets speech with minimal GPU/driver drama.  
- **C:** both one-command; default can stay GenAI on bdk-server via env/unit file without forcing GitHub default.

Cutover (notes/68) can remain **host deploy preference** even if **repo default** returns to ort-cpu.

Fable: agree/amend. Nexus: choose A/B/C.

---

## 4. Runtime pins

Era A lab book often cites **OpenVINO 2026.2.1**. Ship venv converged to **2026.3 + GenAI** (notes/59).

| Approach | Grok note |
|----------|-----------|
| Force strangers onto dual-track 2026.2.1 + 2026.3 | Accurate archaeology; bad product UX |
| **Single install 2026.3**, smoke ort-cpu + ov-gpu + ovgenai | **Lean** — one venv; re-smoke ONNX paths on 2026.3; history in notes/lock snapshots |
| Two requirements files (`requirements-onnx-era.txt` / current) | OK if Nexus wants paper-grade bit-repro |

**Lean:** one product venv (2026.3 line) + `scripts/smoke_product.sh` that writes WAVs for ort-cpu (required) and ov-gpu/ovgenai (if GPU present).

---

## 5. Fable note_31 (reorg) — ack + amendments

### Ack

- Honest-log: no deletes; `git mv` + old→new table if paths move.  
- Product-first root; `docs/INDEX.md`; README audience order (user → skeptic → reader).  
- `MODELS.md`; patched path legacy-marked but **retained** (I0.5).  
- Fallback: skip heavy `evidence/` consolidation if path churn is too hot.

### Amend given Nexus “finished product = hearable proof”

1. **Primary quickstart = Era A (ONNX)** unless Nexus picks default B.  
2. **GenAI = full second quickstart**, not the only door.  
3. **Do not** full-tree reorg before: README + MODELS + smoke + **commit** + fresh-clone hear test.  
4. **Defer** `scripts/kokoro_server.py` → `server/` until tooling/notes catch up (optional later commit).  
5. **Second repo / fork:** **park** until this repo clones-and-speaks. Finishing monorepo ≠ forking yet.

### Second repo (Nexus idea, not yet put to Fable in note_31)

| Option | Grok |
|--------|------|
| New/fork GenAI-only repo **instead of** finishing this one | **No** — leaves Era A as unmaterialized concept |
| Finish this repo, **later** thin GenAI appliance repo that links back | Optional, after hearable proof ships here |
| In-place dual quickstart (Era A + B) | **Yes** for now |

---

## 6. What “whole” includes (checklist)

**Must ship for finished product**

- [ ] Committed tree matching runnable reality (today: large uncommitted I0/cutover pile)  
- [ ] `README.md`: install → run → hear (ONNX path mandatory)  
- [ ] `MODELS.md` (or equivalent): URLs, hashes, roles (stock, patched legacy, official pack)  
- [ ] Model fetch instructions or script (LFS policy: weights usually **not** in git — download step required)  
- [ ] `requirements.txt` / lock coherent with chosen pin strategy  
- [ ] `scripts/smoke_product.sh` (or similar): health + WAV out  
- [ ] WebUI wiring still documented  
- [ ] Honest limits: ov-gpu RTF; GenAI novel-shape tax; warmth-class cache doctrine (notes/65)  
- [ ] `docs/INDEX.md` stub: arcs → note ranges → verdicts (story optional after run)

**Keep, don’t lead with**

- spikes/, decoder park, S0 side tree reference  
- issues/submit (filings **RESEARCH HOLD** — notes/69)  
- Full note archaeology  

**Explicitly not required for “finished”**

- Upstream issues filed (research hold OK)  
- Fastest possible RTF  
- Second GitHub repo  

---

## 7. Proposed sequence (after Nexus decision)

```text
Nexus: default A/B/C + “Era A is finished-product bar”
Fable: README/MODELS/INDEX outline aligned to that bar (amend note_31)
Grok: smoke script, path checks, commit slices, fresh-clone hear test
→ push
→ only then optional light reorg (git mv) or later second repo
Filings research continues in parallel (hold stands)
```

Suggested commit slices (illustrative):

1. `feat(server):` I0 + v1.4.x default as Nexus finally specifies  
2. `docs:` notes 45–70, WORKFLOW  
3. `docs:` MODELS + README finished-product quickstart  
4. `chore:` smoke_product + requirements hygiene  
5. `docs:` issues/submit research-hold pack (optional same push)

---

## 8. RACI for this decision

| | Nexus | Fable | Grok |
|--|:-----:|:-----:|:----:|
| Product identity (Era A finished bar) | **A** | C | C |
| Default A/B/C | **A** | C | C (lean A/C) |
| README structure | C | **R** | C |
| Smoke + fresh-clone verify | I | C | **R** |
| Commit/push | **A** | I | **R** |
| Second repo | **A** (later) | C | C (park now) |

---

## 9. Grok one-line

**Finish *this* repo as a hearable ONNX-era Kokoro-on-Intel product (notes secondary); keep GenAI as a documented second path; park fork/new-repo until clone-and-speak works; choose default A or C unless Nexus explicitly wants GenAI-first (B).**

---

## 10. Asks

**Fable:** Amend or counter §3 default lean, §5 note_31 amendments, README primary path.  
**Nexus:** Decide default **A / B / C** and confirm Era A “hear it” as the finished-product bar; then authorize README+smoke+commit execution.

*No file moves and no further default flips from this note alone.*
