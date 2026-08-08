# notes/39 — Response cache C1 design lock

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Status:** **LOCKED** — Nexus ack to proceed (chat); Fable design `Fable/Fable-note_28-response-chunk-cache-design.md`  
**Phase:** **C1 only** → target version **v1.2.0**. C2 deferred (v1.2.1).  
**Ship freeze:** lifted for `scripts/kokoro_server.py` this thread only. S0 side venv untouched.

---

## 1. Nexus ack

- Design accepted; proceed with **C1** implementation + probe matrix P0/P1/P2/P4/P5.  
- P3 (C2 partial) **out of scope** this pass.  
- README product claims still wait Validator sign-off after probes.

---

## 2. Answers to Fable note_28 §7

| # | Question | Decision |
|---|----------|----------|
| 1 | `model_fp` cheap vs strong | **Strong** — `sha256` of model file once at startup (~0.29 s for 310 MB on this host), held in memory. Prevents wrong-audio on silent model swap. |
| 2 | `KOKORO_CACHE_DIR` placement | Default **`/data/intel-igpu-tts/cache/tts`** under sandbox on `/data` (474 G free). Cap **500 MB** default. Do **not** colocate under OV compile dirs. |
| 3 | Concurrency | `uvicorn.run(app)` **single process**, no `--workers`. Sync FastAPI routes run in the threadpool; `OvBackend` already serializes infer with `threading.Lock`. **C1:** atomic `tmp` + `rename` for entry integrity; **process-local `threading.Lock`** around miss→write to limit duplicate synth; P5 still allows at-most duplicate work, never corrupt files. No cross-process file lock required until multi-worker is a product path. |

---

## 3. Binding amendment — env var names (collision)

**Problem:** `KOKORO_CACHE` is **already** the OpenVINO compile-cache directory (docstring, README, ov backends). Fable note_28 reused that name for TTS on/off.

**Lock (do not steal OV var):**

| Var | Default | Meaning |
|-----|---------|---------|
| `KOKORO_CACHE` | `…/cache/openvino` | **Unchanged** — OV compile CACHE_DIR |
| `KOKORO_TTS_CACHE` | `0` | `0` off, `1` on — **opt-in** |
| `KOKORO_TTS_CACHE_DIR` | `/data/intel-igpu-tts/cache/tts` | TTS response/chunk store root |
| `KOKORO_TTS_CACHE_MAX_MB` | `500` | lazy LRU-by-mtime cap |
| `KOKORO_TTS_CACHE_TIER` | `both` | C1 honors `response` \| `both`; `chunk` alone ⇒ C1 no-ops until C2 |

Header / debug names from note_28 stand: `X-Kokoro-Cache: hit \| partial \| miss` (C1 emits `hit`/`miss` only).

---

## 4. C1 behavior (locked subset of note_28)

```
key = sha256( schema_ver | backend_id | model_fp | voice | speed | sample_fmt | text_unit )
```

- `schema_ver` = `1`  
- `backend_id` = `ort-cpu` \| `ov-cpu` \| `ov-gpu` (no cross-serve)  
- `model_fp` = hex sha256 of `KOKORO_MODEL` bytes  
- `voice` = canonical label from `parse_voice_spec` (blends included)  
- `speed` = normalized after clip, e.g. `f"{speed:.6g}"`  
- `sample_fmt` = `24000:s16le:mono`  
- `text_unit` = exact request text passed to `synthesize` (same string as today after empty-strip gate)

**Storage:**

```
$KOKORO_TTS_CACHE_DIR/v1/
  ab/<hex>.pcm      # int16 LE mono @ 24 kHz, post-assembly (same samples as to_wav_bytes input)
  ab/<hex>.json     # sidecar: key fields, created, samples, duration_s
```

- Atomic write: `*.tmp` + `os.replace`  
- On hit: load PCM → wav (or transcode) — **do not** re-synth  
- Eviction: on write, if total size > max MB, delete oldest-mtime `.pcm`+`.json` pairs until under cap; touch mtime on hit  
- `X-Kokoro-RTF` on hit = wall/audio (serving RTF; honest tiny number)  
- Log line: include `cache=hit|miss`

**Not in C1:** chunk-tier lookup, trim changes, model/backend selection, README default flip.

---

## 5. Probe plan (C1)

| Probe | Bar |
|-------|-----|
| **P0** | Cache off; same request twice; byte-compare WAV bodies (ort-cpu required; ov-gpu optional if time) |
| **P1** | Cache on; 2nd response byte-identical to 1st; header `hit` |
| **P2** | Hot hit fox-class server wall < 100 ms **or** ≤ 10% of fresh ort-cpu synth time |
| **P4** | Tiny `MAX_MB` fill; cap honored; no 5xx |
| **P5** | Two concurrent identical cold requests; both 200; no corrupt entry |

Ears: waived on byte-equality if P0+P1 PASS (Validator note). Else Nexus ears by filename.

---

## 6. Mechanic scope

- File: `scripts/kokoro_server.py` (+ minimal README env table **documentation of flags only**, no performance claims)  
- Version → **1.2.0**  
- Stdlib only (`hashlib`, `json`, `os`, `time`, `threading`, `struct`/`wave` as already used)  
- No new deps  
- Do not touch `models/patched/`, S0 trees, trim math  

---

## 7. One-line

**C1 locked: strong model sha256, TTS env prefix `KOKORO_TTS_*` (OV `KOKORO_CACHE` preserved), disk PCM under `cache/tts`, opt-in, v1.2.0; Nexus go; Mechanic next.**
