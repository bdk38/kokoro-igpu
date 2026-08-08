# notes/73 — Prototype (Product B) segregation — inventory + hold for Architect

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Status:** **ORGANIZED LOCALLY · AWAITING FABLE** — sibling repo shell exists; no populate yet  
**Context:** PoC tagged `poc-complete` @ `f2ff370` (R0 fix on main). Nexus: segregate spike→prototype files; wait on Architect before going further.

---

## 1. What Product B is

| Layer | Location |
|-------|----------|
| **User-facing product** | `KOKORO_BACKEND=ovgenai-gpu` in `scripts/kokoro_server.py` + README §2 |
| **Model** | `models/kokoro-82M-int8-ov/` (first-class; weights not in git) |
| **Lab origin** | S0 under `spike/ov263-genai/` → I0 notes/scripts → ship integration |
| **Verdicts** | S0-GO-product; I0-GO-default-candidate; repo default remains **ort-cpu** (PoC face) |

---

## 2. Done this pass (safe, reversible)

1. **Evidence home:** untracked I0/S0 WAVs moved under  
   `artifacts/prototype/{s0,i0}/…`  
   with `artifacts/prototype/README.md` map.
2. **Committed JSON** left at `artifacts/i0_3/`, `artifacts/i0_4/` (already on main).
3. **spike/ov263-genai/README.md** rewritten: historical S0 complete; product path = server.
4. **gitignore:** prototype/spike OV caches, spike logs.
5. **No** `git mv` of server, scripts, or notes (Architect owns next layout).

---

## 3. Inventory (current)

### Committed (main)

| Path | Role |
|------|------|
| `scripts/kokoro_server.py` | `ovgenai-gpu` / `ovgenai-cpu` backends |
| `scripts/i0_{2,3,4}_*.py` | Integration probes |
| `spike/ov263-genai/scripts/s0_*.py` | S0 probes |
| `spike/ov263-genai/requirements-s0.lock.txt` | Side-venv pin record |
| `notes/45`–`67` (+ 68–69) | S0/I0/filings arc |
| `models/.../SHIP_PACK_IDENTITY.txt` | Pack identity |
| `artifacts/i0_3/i0_3_result.json`, `i0_4/i0_4_result.json` | Matrix JSON |
| `issues/submit/*` | Upstream drafts (research hold) |

### Local only (not required for PoC clone)

| Path | Role | Size class |
|------|------|------------|
| `models/kokoro-82M-int8-ov/*.{bin,xml,voices}` | Pack weights | ~153 MB |
| `venv-s0-ov263/` | Retired side venv | ~5 GB — **candidate delete** after Architect ack |
| `spike/ov263-genai/out/` | S0/I0 raw outs + caches | ~757 MB tree |
| `artifacts/prototype/**` | Organized ear/matrix WAVs | ~19 MB |

### Chat dumps (untracked)

`Fable/fable_*` response files — leave for Architect/Nexus; not product.

---

## 4. Options for Fable (do not execute yet)

| Option | Meaning |
|--------|---------|
| **B0 Hold** | Keep as now: map docs only (this note + prototype README) |
| **B1 Light** | Commit `artifacts/prototype/**/*.wav` (LFS) + READMEs; delete `venv-s0-ov263` |
| **B2 Tree** | `git mv` notes/scripts into `docs/prototype/` or `prototype/` per note_31-style — **Architect design** |
| **B3 Split repo** | **Remote exists (empty):** https://github.com/bdk38/kokoro-igpu-genai — populate after Architect design |

**Grok lean:** **B1** after Fable ack — evidence durable on GitHub; drop 5 GB dead venv; no path churn in server.

---

## 5. Explicit non-goals until Architect

- Moving `ovgenai` out of `kokoro_server.py`
- Renaming spike → prototype directory via mass `git mv`
- Second GitHub repo
- Changing repo default away from ort-cpu
- Filings submit (research hold)

---

## 6. One-line

**Prototype evidence under artifacts/prototype/; sibling repo kokoro-igpu-genai is empty shell; awaiting Fable before populate or monorepo B1.**

---

## 7. New remote (Nexus, 2026-08-08) — **empty shell**

Nexus cannot fork a self-owned repo; created a **sibling**:

| | |
|--|--|
| **URL** | https://github.com/bdk38/kokoro-igpu-genai |
| **Access** | Confirmed from bdk-server (`git clone` OK) |
| **Contents now** | `README.md` stub (“Runs Kokoro TTS on Intel iGPU hardware.”) + `LICENSE` only |
| **HEAD** | `6fe076f` on `main` |
| **Relation to PoC** | Sibling of https://github.com/bdk38/kokoro-igpu (`poc-complete`) — not a GitHub fork graph |

**Orchestrator stance until Fable:** do **not** push product code into genai repo yet. PoC monorepo remains source of truth for integrated `ovgenai-gpu`. Population plan (seed from monorepo slice vs greenfield) is **Architect + Nexus**.

**Suggested Fable questions:**
1. What is the genai repo’s product face (server-only thin tree vs full I0 lab)?
2. Does monorepo keep a thin Prototype § + submodule/subtree link, or drop Product B docs to “see sibling repo”?
3. Seed commit: copy server+MODELS+requirements vs extract history?
4. Default backend in genai repo = `ovgenai-gpu` (yes/no)?

