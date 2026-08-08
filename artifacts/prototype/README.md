# Product B — Prototype evidence (GenAI era)

**Status:** organized for Architect review — **no further product moves until Fable**.  
**Product path:** `KOKORO_BACKEND=ovgenai-gpu` + `models/kokoro-82M-int8-ov/` (see root README §2, MODELS.md).  
**Historical probe tree:** `spike/ov263-genai/` (S0 scripts; ship freeze on server was for S0 era).

## Layout (this directory)

```
artifacts/prototype/
  s0/s0_4/          S0.4 ear WAVs (official pack)
  i0/i0_1/          I0.1 voice A/B ears
  i0/i0_2/          I0.2 integration ear set
  i0/i0_3/          I0.3 served-RTF matrix WAVs
  i0/i0_4/          I0.4 regression WAVs (+ local probe caches; gitignored)
  README.md         this file
```

Committed JSON results remain next to historical paths where already on main:

- `artifacts/i0_3/i0_3_result.json`
- `artifacts/i0_4/i0_4_result.json`
- `spike/ov263-genai/out/s0_*_result.json` (local; large pack gitignored)

## Code / model map (do not move without Architect)

| Kind | Path | Notes |
|------|------|--------|
| Server backend | `scripts/kokoro_server.py` (`ovgenai-*`) | Shared binary with PoC |
| I0 probe scripts | `scripts/i0_2_*.py`, `i0_3_*.py`, `i0_4_*.py` | Committed |
| S0 probe scripts | `spike/ov263-genai/scripts/` | Committed |
| Official pack | `models/kokoro-82M-int8-ov/` | Weights gitignored; `SHIP_PACK_IDENTITY.txt` tracked |
| S0 side venv | `venv-s0-ov263/` | **Retired for runtime** (ship venv has 2026.3+GenAI); keep or delete locally |
| Notes arc | `notes/45`–`67`, `68`–`69` | S0 → I0 → filings hold |
| Architect | `Fable/Fable-note_29`, `_30`, I0 responses | |

## Proposed later (Architect-owned)

See `notes/73-prototype-segregation.md` — options only; **wait for Fable**.

