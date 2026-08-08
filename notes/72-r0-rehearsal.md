# notes/72 — R0 stranger rehearsal findings

**Date:** 2026-08-08  
**Method:** fresh `git clone` → `/tmp/kokoro-igpu-r0` → venv → README install  
**Commit under test:** `2e1bb9b`

## Bugs found

| ID | Severity | Finding | Fix |
|----|----------|---------|-----|
| **R0-1** | **P0** | `kokoro_server.py` defaulted `KOKORO_MODEL` / voices / cache / genai to **hardcoded** `/data/intel-igpu-tts/...`. Fresh clone still loaded the **sandbox** models (health showed sandbox path). | Defaults now `REPO_ROOT`-relative (`scripts/` parent). |
| **R0-2** | **P1** | `download_models.sh` voices SHA expected lab 50-voice pack (`d19762…`) but public URL serves **11-voice** kokoro-onnx `voices.bin` (`157eab…`). | MODELS + expected SHA updated; document lab pack as optional override. |
| **R0-3** | **P2** | README implied `scripts/env.sh` (missing). | Removed; note `espeak-ng` system package. |
| **R0-4** | info | Product B pack not auto-downloaded (by design). smoke skips ovgenai. | OK — MODELS documents HF fetch. |

## After fix (re-smoke on R0 tree)

Copied fixed server into `/tmp/kokoro-igpu-r0` and re-ran `smoke_product.sh`:

| Leg | Health model path | WAV | Result |
|-----|-------------------|-----|--------|
| ort-cpu | `/tmp/kokoro-igpu-r0/models/kokoro-v0_19.onnx` | 174044 B | **PASS** |
| ov-gpu | `.../models/patched/kokoro-v0_19.gpu4d.stft.onnx` | 141644 B | **PASS** |
| ovgenai | skipped (pack not downloaded) | — | expected |

Version bump: **1.5.1** (portable defaults).

## One-line

**R0 shook out P0 hardcoded sandbox paths + voices SHA; fixed and re-smoke PASS on fresh tree; 1.5.1 pushed for poc-complete readiness.**
