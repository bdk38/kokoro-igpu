# Phase 6 — Open WebUI wiring

**Date:** 2026-08-03  
**Open WebUI:** `open-webui` container v0.11.0 on `192.168.0.165:3000`  
**Kokoro server:** host process `scripts/kokoro_server.py` on `0.0.0.0:8880` (ORT-CPU)

## What changed

### 1. Open WebUI persistent config (`webui.db` `config` table)

| key | new value |
|-----|-----------|
| `audio.tts.engine` | `openai` |
| `audio.tts.model` | `kokoro` |
| `audio.tts.voice` | `af_bella` |
| `audio.tts.split_on` | `punctuation` |
| `audio.tts.openai.api_base_url` | `http://host.docker.internal:8880/v1` |
| `audio.tts.openai.api_key` | `not-needed` |
| `audio.tts.openai.params` | `{"speed": 1.0}` |
| `audio.tts.api_key` | `not-needed` |

Previous base URL was a leftover remote Kokoro at `http://192.168.0.243:8880/v1` with a blended voice string. Replaced with this host’s server + `af_bella`.

Open WebUI was restarted (`docker compose restart open-webui`) so config reloaded. Status after restart: healthy.

### 2. Network / firewall

- Kokoro rebound from `127.0.0.1` to `0.0.0.0:8880` so Docker can reach it.
- UFW was **DROP** on INPUT; Docker bridge → host timed out until:
  ```bash
  sudo ufw allow from 172.16.0.0/12 to any port 8880 proto tcp comment "kokoro-tts docker->host"
  ```
- After rule: container `curl http://host.docker.internal:8880/health` → OK.

### 3. Validation

**A. Container → Kokoro direct**
- `from_container.wav`: 24 kHz mono, 4.775 s
- Headers: `X-Kokoro-Backend: ort-cpu`, `X-Kokoro-RTF: 0.41`

**B. Open WebUI TTS proxy (authenticated)**
```bash
curl -H "Authorization: Bearer <admin-api-key>" \
  -H "Content-Type: application/json" \
  -d {input:...,voice:af_bella} \
  http://192.168.0.165:3000/api/v1/audio/speech
```
- HTTP 200
- `content-type: audio/mpeg` (Open WebUI transcodes upstream WAV → MP3 via ffmpeg inside the container)
- ~24 KB MP3, `x-process-time: ~2.7s`
- Artifact: `artifacts/server/webui_proxy.bin`

## How to use in the UI

Admin → Settings → Audio (already set in DB):
- TTS Engine: OpenAI
- API Base URL: `http://host.docker.internal:8880/v1`
- API Key: `not-needed`
- Model: `kokoro`
- Voice: `af_bella` (or any voice from `/v1/audio/voices`, or OpenAI aliases)

In chat: use the speaker / read-aloud control on a message.

## Runtime notes

- Kokoro server is a **foreground host process**, not yet a systemd unit. Currently PID listening on `:8880`.
- Product default remains ORT-CPU. GPU flip:
  ```bash
  KOKORO_BACKEND=ov-gpu \
  KOKORO_MODEL=/data/intel-igpu-tts/models/patched/kokoro-v0_19.gpu4d.stft.onnx \
  python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
  ```
- Open WebUI prefers MP3 downstream even when Kokoro returns WAV; container has ffmpeg so that path works.

## Phase 6 gate

**PASS** — Open WebUI reaches local Kokoro and returns playable speech through `/api/v1/audio/speech`.
