# Phase 5 — OpenAI-compatible server validation

**Date:** 2026-08-03  
**Script:** `scripts/kokoro_server.py`  
**Default:** ORT-CPU + original `models/kokoro-v0_19.onnx`

## Run

```bash
source /data/intel-igpu-tts/scripts/env.sh
cd /data/intel-igpu-tts
pip install fastapi uvicorn   # done in venv
python scripts/kokoro_server.py --host 127.0.0.1 --port 8880
```

Warmup OK. Listening on `http://127.0.0.1:8880`.

## Endpoint checks

### GET /health
```json
{"status":"ok","backend":"ort-cpu","model":"/data/intel-igpu-tts/models/kokoro-v0_19.onnx","gpu_precision":null}
```

### GET /v1/models
Returns `kokoro` and `tts-1`.

### GET /v1/audio/voices
- 50 Kokoro voices
- default `af_bella`
- OpenAI aliases: alloy/echo/fable/onyx/nova/shimmer

### POST /v1/audio/speech

Fox (`af_bella`, wav):
- HTTP 200, `audio/wav`
- headers: `X-Kokoro-Backend: ort-cpu`, `X-Kokoro-RTF: 0.40`, `X-Kokoro-Format: wav`
- 90600 samples @ 24 kHz (3.775 s) — matches harness ORT fox length

Long multi-sentence (`voice=nova` alias → `af_nova`):
- HTTP 200
- `X-Kokoro-RTF: 0.45`
- 244200 samples (10.175 s) including chunk gaps

Errors:
- unknown voice → 400 `unknown voice ... see /v1/audio/voices`
- empty/whitespace input → 400 `empty input`

Artifacts: `artifacts/server/{health.json,fox.wav,long.wav,*.headers}`

## Notes

- No ffmpeg on host → mp3/opus/flac would fall back to wav (by design).
- FastAPI warns that `@app.on_event("startup")` is deprecated in favor of lifespan handlers — cosmetic.
- Server process left running on 127.0.0.1:8880 for further wiring tests (kill when done).
- OV-GPU path not smoke-tested via API this round; env flip is:
  `KOKORO_BACKEND=ov-gpu KOKORO_MODEL=models/patched/kokoro-v0_19.gpu4d.stft.onnx`

## Phase 5 gate

**PASS** for product path (ORT-CPU OpenAI-compatible TTS).

Open WebUI wiring (Phase 6): TTS Engine OpenAI, base `http://bdk-server:8880/v1`, any key, voice `af_bella`, format wav.
