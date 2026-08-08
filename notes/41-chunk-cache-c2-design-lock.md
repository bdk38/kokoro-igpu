# notes/41 — Chunk cache C2 design lock (v1.2.1)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Status:** **LOCKED** — Nexus go (chat: continue C2)  
**Parent design:** `Fable/Fable-note_28-response-chunk-cache-design.md`  
**Prior:** C1 closed notes/39–40 (ears 21/21)  
**Target version:** **1.2.1**

---

## 1. Goal

Add **C2 chunk-tier** cache on the existing synthesis unit so partial reuse works when `chunk_text` emits shared prefix chunks. Compose with C1:

```
C1 full-text hit? → serve (header hit)
else → per chunk_text unit: C2 lookup → synth misses only → assemble
     → write C2 misses + C1 full entry
     → header: hit (0 synth) | partial (mixed) | miss (0 chunk hits)
```

---

## 2. Critical clarification (vs Fable P3 wording)

`chunk_text` **merges** short sentences into one token-id chunk until ~510 tokens. Therefore:

- C2 key unit = **`chunk_text` output (token id list)**, not raw sentence strings.  
- Fable’s example “3 sentences then 4th sentence” only yields `partial` if packing emits **multiple** chunks with a **stable shared prefix**.  
- **P3 probe (amended):** use multi-chunk texts with prefix-stable packing (verified by chunk count), not three tiny sentences.

Soundness unchanged: cache unit = synthesis unit (infer on that id list + existing trim inside backend).

---

## 3. Key / storage

Reuse C1 machinery (`build_tts_cache_key`, same dir `v1/ab/*.pcm|json`):

| Field | C2 value |
|-------|----------|
| schema_ver | **2** (bump — see §4 audio path) |
| text_unit | `c2ids:` + comma-separated decimal token ids (exact infer input sans pad bos/eos) |
| other fields | same as C1 (backend, model_fp, voice label, speed, sample_fmt) |

C1 text_unit remains full request string. C1 and C2 entries share one LRU pool (same root).

Meta JSON: add `"tier": "chunk" | "response"`.

---

## 4. Assembly / quantization (byte-identity)

Per-chunk int16 quantize then dequant before concat **always** in `synthesize` (cache on or off):

1. infer → float (or load pcm → float)  
2. `pcm = float_to_pcm(chunk)` — write C2 on miss  
3. piece = pcm_to_float(pcm)  
4. concat pieces + gap (gap = float zeros, then same final encode path)  
5. final C1 pcm = float_to_pcm(concat) as today  

**Why:** mixing cached pcm chunks with end-only quantize would break P3 byte-equality. One deterministic path for all modes.

**schema_ver → 2** invalidates v1.2.0 C1 disk entries (correct; old values would not match new assembly).

---

## 5. Tiers / env (unchanged names)

| `KOKORO_TTS_CACHE_TIER` | C1 | C2 |
|-------------------------|----|----|
| `both` (default) | on | on |
| `response` | on | off |
| `chunk` | off | on |

`KOKORO_TTS_CACHE=0` → both off.

---

## 6. API / logs

- `X-Kokoro-Cache: hit | partial | miss`  
  - `hit` = C1 hit **or** all chunks C2 hit (zero infer)  
  - `partial` = ≥1 chunk hit and ≥1 infer  
  - `miss` = no chunk hits (all inferred)  
- Log: `cache=hit|partial|miss` plus `c2_hits=N c2_miss=M` when C2 active  
- Do not change trim math; do not touch models/S0  

---

## 7. Probes (bars before numbers)

| ID | Bar |
|----|-----|
| **P0** | cache off; two identical multi-chunk requests; byte-equal (reconfirm after quantize path) |
| **P1** | tier=both; full repeat → 2nd `hit`, byte-equal (C1) |
| **P3** | Seed text T_prefix (≥2 chunks). Cache on. Request T_prefix. Then T_full = prefix-stable longer text sharing chunk_text prefix. Expect `partial` or fewer infers; **body byte-equal** to cache-off T_full. Debug: c2_hits≥1, c2_miss≥1. |
| **P3b** | tier=chunk only (no C1): repeat same full text → 2nd request all C2 hits, header `hit`, byte-equal, near-zero infer |
| **P5** | two concurrent cold identical; 200; no corrupt entries |

Ears: waived on byte-equality if P0+P3 PASS; else Nexus by filename.

---

## 8. Mechanic scope

- `scripts/kokoro_server.py` → version **1.2.1**  
- README: one line that tier `chunk` exists; no perf claims  
- Stdlib only; protect_key eviction stays  
- Out of scope: sentence-forced chunking product change, ov-gpu matrix, default cache on  

---

## 9. One-line

**C2 locked: key on chunk_text token ids; schema_ver 2 + always per-chunk pcm roundtrip; partial header; P3 amended for multi-chunk prefix; v1.2.1.**
