# notes/46 — Fable read-back fold (notes/43–45)

**Date:** 2026-08-07  
**Source:** `Fable/fable_43_44_45_response`  
**Author:** Grok (Orchestrator)

## Architect points accepted

1. **v1.2.0 collapse** — correct; code default `KOKORO_TTS_CACHE=0` vs deployment-on is intentional evidence-gathering, not stealth default flip.  
2. **notes/44** re-anchors S0.5 demo-class band (~4–6 RTF) on **current drivers + 2026.2.1 ship stack** (RTF 5.01 fresh long miss). Official path must beat that to be more than a repackage.  
3. **OWUI MP3 cache** — “felt instant” requires matching server `cache=hit` line; applies to S1 too.  
4. **Small polish backlog** (non-blocking): voices JSON shape; `/v1/audio/models` 404 — batch on next server touch.  
5. **S0.1** provenance: wheel build `8a17657b995` = 2026.3.0 release tag; dual-track held.  
6. **Pre-S0.2 B-branch lean (Fable, on record):** **B1 or B3** — official export likely loads; open question is escape from ref-conv floor on Xe-LP.

No gate bar amendments. Proceed S0.2.
