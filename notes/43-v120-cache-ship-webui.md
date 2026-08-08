# notes/43 — v1.2.0 cache ship + Open WebUI wire-up

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Status:** **SHIPPING** product **v1.2.0** = C1+C2 single release; WebUI live path  
**Nexus:** collapse 1.2.0+1.2.1 → one **v1.2.0**; wire server to Open WebUI before S0  
**Fable:** `fable_response_41_42` (one push; schema v2 supersedes interim disk)

---

## 1. Version collapse

| Was (dev labels) | Ship |
|------------------|------|
| C1 probes “v1.2.0” / artifacts `v120_cache` | folded |
| C2 probes “v1.2.1” / artifacts `v121_cache` | folded |
| FastAPI `version=` | **`1.2.0`** only |
| TTS disk `schema_ver` | **2** (independent of product semver) |

Rationale: C1 never landed alone on `origin/main`; shipping two patch bumps for one feature is noise. Product claim: **v1.2.0 adds opt-in response+chunk TTS cache**.

---

## 2. Enable for live WebUI soak

```bash
# host process (product default ort-cpu + cache on)
KOKORO_BACKEND=ort-cpu \
KOKORO_TTS_CACHE=1 \
KOKORO_TTS_CACHE_DIR=/data/intel-igpu-tts/cache/tts \
KOKORO_TTS_CACHE_TIER=both \
KOKORO_TTS_CACHE_MAX_MB=500 \
KOKORO_MODEL=/data/intel-igpu-tts/models/kokoro-v0_19.onnx \
/data/intel-igpu-tts/venv/bin/python \
  /data/intel-igpu-tts/scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

Open WebUI (notes/09, persistent DB):

- TTS Engine: OpenAI  
- API Base: `http://host.docker.internal:8880/v1`  
- Key: `not-needed`  
- Voice: `af_bella`  
- Response splitting: **punctuation** OK on ort-cpu (notes/15)

UFW: `8880/tcp` from `172.16.0.0/12` already allowed.

---

## 3. Live checks (filled at wire-up)

| Check | Result |
|-------|--------|
| `/health` on :8880 | _pending_ |
| version header / OpenAPI | _pending_ |
| container → host health | _pending_ |
| direct fox miss then hit | _pending_ |
| WebUI `/api/v1/audio/speech` (if key) | _pending_ |

---

## 4. One-line

**Single product v1.2.0 ships C1+C2 cache; WebUI soak next; S0 still staged after live confidence.**
