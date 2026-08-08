# notes/75 — WORKFLOW dual-repo refresh + Fable note_35 polish

**Date:** 2026-08-08  
**Author:** Grok 4.5 (Orchestrator)  
**Type:** execution record  
**Related:** Fable note_35, notes/74, WORKFLOW.md, docs/INDEX.md  

---

## 1. WORKFLOW.md

Refreshed for post-ship board:

- Status: both products **SHIPPED** (`poc-complete` + `prototype-complete`)
- Dual remotes: lab monorepo `/data/intel-igpu-tts` + appliance `/data/kokoro-igpu-genai`
- Paths table: Product A/B shipped; S0/I0 closed; filings RESEARCH HOLD
- Open board: filings hold, optional note_35 polish, gated B backlog, decoder PARKED
- Tooling map: dual-remote paths; side venv deleted; `issues/submit/`
- Onboarding pointers → notes/70–74, Fable note_33–35
- Revision row 2026-08-08 dual-product ship closeout

## 2. Fable note_35 §4 — genai docs polish (no re-tag)

Repo: https://github.com/bdk38/kokoro-igpu-genai  
Base tag: `prototype-complete` @ `8987f74` (unchanged)

| Item | Action |
|------|--------|
| **D1 docstring** | Replaced ONNX fallback/legacy ad copy with lineage sentence + shelf URL |
| **README §Open WebUI** | After Smoke, before Configuration (Paragraphs/None; cache+warm deploy tip) |
| **igt fingerprint** | Comment in GPU start block |

Executed on genai main as .

Suggested commit message (executed):  
`docs: WebUI wiring + docstring lineage tidy (Fable note_35)`

**No re-tag** per Architect.

## 3. Monorepo hygiene this turn

- `docs/INDEX.md` — sibling no longer “empty shell”; arcs 70–75
- `Fable/Fable-note_35-…` committed with this note when staged
- WORKFLOW + INDEX + notes/75

## 4. Board after this note

| Track | State |
|-------|--------|
| PoC | SHIPPED `poc-complete` |
| Prototype | SHIPPED `prototype-complete` + note_35 docs polish on main |
| Filings | RESEARCH HOLD (notes/69) |
| B backlog / decoder | gated / PARKED |

## 5. One-line

**WORKFLOW matches dual-repo ship; note_35 docs-only polish applied on genai main without moving `prototype-complete`; open board remains filings research hold.**
