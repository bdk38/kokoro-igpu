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

## 3. Live checks (2026-08-07 wire-up)

| Check | Result |
|-------|--------|
| Product version | OpenAPI **`1.2.0`** |
| Process | host PID in `/tmp/kokoro-server.pid`; log `logs/kokoro_v120_webui.log` |
| Cache | `KOKORO_TTS_CACHE=1` tier=`both` dir=`cache/tts` schema_ver=2 |
| `/health` :8880 | **ok** ort-cpu |
| container → `host.docker.internal:8880/health` | **ok** |
| direct fox miss → hit | miss wall **1.58 s** RTF 0.41; hit **20–35 ms** RTF 0.00; `X-Kokoro-Cache` correct |
| container POST speech | **200**, `x-kokoro-cache: hit` (shared C1 after host warm) |
| WebUI DB TTS | already set: engine=openai, base=`http://host.docker.internal:8880/v1`, model=kokoro, voice=af_bella, **split_on=paragraphs** |
| WebUI authenticated proxy | skipped (no usable API key in automated path); UI Read Aloud uses same upstream URL — ready for Nexus ears in chat |

Artifacts: `artifacts/webui_soak/fox_{miss,hit,hit2}.wav`, `from_container.wav`.

Git: local commit **`8893249`** `feat(server): v1.2.0 opt-in response+chunk TTS cache (C1+C2)` — ahead of origin by 1 (push on call).

---

## 4. How to use in Open WebUI now

1. Server is listening **0.0.0.0:8880** with cache on (restart command in §2 if it dies).  
2. Admin → Settings → Audio already points at host Kokoro (notes/09).  
3. Chat → Read Aloud / speaker on a message.  
4. First utterance of a passage pays synth; **repeat same text** should feel instant (C1). Shared multi-chunk prefixes get C2 partial.  
5. Watch `logs/kokoro_v120_webui.log` for `cache=hit|partial|miss`.

---

## 5. One-line

**v1.2.0 live on :8880 with C1+C2 cache; WebUI container reaches host; fox hit ~20 ms; Read Aloud ready for your ears before S0.**
