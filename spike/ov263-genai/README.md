# S0 probe tree — Official OpenVINO 2026.3 GenAI Kokoro (historical)

**Role today:** **Product B (Prototype) lab origin** — scripts + local captures.  
**Product runtime:** use ship `venv` + `KOKORO_BACKEND=ovgenai-gpu` (root README).  
**Gate (historical):** `notes/36` + `36b` → closeout **`S0-GO-product`** (`notes/52`–`53`).

## Status (complete)

| Bar | Note |
|-----|------|
| S0.1 install | notes/45 |
| S0.2 load+generate | notes/47 |
| S0.3 offload | notes/49 |
| S0.4 ears | notes/51 |
| S0.5 RTF/A1/A2 | notes/52 |

## Layout

- `scripts/` — S0.2–S0.5 probes (committed)
- `out/` — local WAVs/JSON/cache (**pack + ov_cache gitignored**)
- `logs/` — local (gitignored)
- `requirements-s0.lock.txt` — side-venv pin record

## Do not

- Treat this tree as the only way to run GenAI (server path is primary).
- Commit `out/kokoro-82M-int8-ov/` or `out/ov_cache*` (see MODELS.md for pack fetch).

Evidence ears also mirrored under `artifacts/prototype/` where organized.
