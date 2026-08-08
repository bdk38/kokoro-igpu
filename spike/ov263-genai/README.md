# S0 — Official OpenVINO 2026.3 GenAI Kokoro probe

**Gate:** `notes/36` + `notes/36b` (fully acked)  
**Ship freeze:** do not edit `scripts/kokoro_server.py` or `models/patched/` from this tree.  
**Runtime:** side venv `/data/intel-igpu-tts/venv-s0-ov263` only (never ship `venv`).

## Status
- S0.1 PASS — `out/versions_s0_1.json`, `notes/45`
- S0.2 PASS — official `OpenVINO/kokoro-82M-int8-ov` GPU load+generate; `notes/47`, `out/s0_2_*`

## Layout
- `scripts/` — probe scripts
- `out/` — WAVs, versions, captures
- `logs/` — run logs

- S0.3 PASS — offload proof GPU.0 + igt RCS; `notes/49`, `out/s0_3_result.json`
