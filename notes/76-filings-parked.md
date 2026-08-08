# notes/76 — Filings PARKED (research incomplete)

**Date:** 2026-08-08  
**Author:** Grok 4.5 (Orchestrator)  
**Nexus decision:** Park upstream filings until duplicate/prior-art research can be completed.  
**Related:** notes/69, `issues/submit/`, WORKFLOW.md  

---

## Status

| Item | State |
|------|--------|
| VERIFY pack | **Intact** — `issues/submit/*.github.md` + `attachments/` |
| Submit | **Do not file** while parked |
| Active board | Filings **off** the hot path |
| Unpark trigger | Nexus completes research and sets per-draft **file / comment / drop** |

## Why park

Nexus is not ready to finish the upstream duplicate/acknowledgment search now. Parking avoids treating VERIFY-ready drafts as “file next” and keeps the dual-product ship board clean.

## What stays frozen

- `issues/submit/SUBMIT.md` (status banner = PARKED)
- `01-shape-jit.github.md`, `02-f16-matmul.github.md`, `03-conv-ref.github.md`
- attachments + stack captures from notes/69
- Outcome table in notes/69 §5 (still pending research)

## Unpark checklist (later)

1. Search `openvinotoolkit/openvino` (and related) per notes/69 §5  
2. Fill per-draft outcome: file / comment on existing / drop  
3. If file: follow `SUBMIT.md` order (#2 → #3 → #1)  
4. Record URLs in `issues/submit/FILED_URLS.md` (create when filing)  
5. Flip WORKFLOW + notes/69 status off PARKED  

## One-line

**Filings VERIFY pack parked intact until Nexus research completes; nothing submitted; no pack edits required to park.**
