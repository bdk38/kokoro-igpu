# Fable/note_28 — Response/chunk cache design (ship path)

**Date:** 2026-08-07
**Author:** Fable (Chief Architect)
**Status:** C1 **CLOSED** (notes/39–40). C2 **IMPLEMENTED + PROBED** (notes/41 lock, notes/42 PASS). Feature complete pending Nexus commit.
**Greenlight:** Nexus, 2026-08-07 (post v1.1.8 ship, post 36b ack; parallel to S0)
**Orchestrator fold:** env names amended to `KOKORO_TTS_*` (preserve OV `KOKORO_CACHE`) — notes/39 §3.
**Scope:** `scripts/kokoro_server.py` — ship-path freeze lifted for this thread only. S0 side venv untouched and untouching.
**Related:** notes/35 (v1.1.8), notes/38 (dual-track), Fable/note_27 §4 (cache survives all S0 branches)

---

## 1. What's changing and why

A server-side cache of synthesized audio, so repeat traffic costs zero compute. Two tiers, phased:

- **C1 — Response cache.** Key the entire request; on hit, stream stored bytes. Zero synth, zero concat.
- **C2 — Chunk cache.** Key each sentence chunk (the server's existing synthesis unit); on partial hit, synthesize only the missing chunks and assemble as normal.

Why this is the right bet, restated from note_27: it is **black-box and backend-agnostic**. It never touches a graph, never cares about shapes, works identically for ort-cpu and ov-gpu, and survives every S0 verdict. It also directly attacks our two worst latency classes: the ov-gpu novel-shape cold (7.35 RTF on the v1.1.8 smoke → ~0 on hit) and repeat ort-cpu traffic (0.40 RTF → ~0 on hit). Read Aloud traffic — same passages re-read — is the natural hit-rich workload.

### The soundness argument (why C2 cannot degrade quality)

The server **already** synthesizes chunks independently and concatenates with the v1.1.5-class trim logic. A cached chunk is the byte-identical output of the same synthesis the server would have run. Therefore assembly from cached chunks is byte-identical to fresh assembly — coarticulation across chunk boundaries is not sacrificed because it was never present. This is the same reasoning that killed the fragment-reuse idea (notes: spectrum-as-fingerprint, rejected — sub-chunk reuse *would* break coarticulation) while leaving chunk-level reuse clean: **the cache unit equals the existing synthesis unit.** No new seam is introduced, which is why this idea survived the monolith while the others died.

Corollary for validation: if P0 (determinism) passes, cached-vs-fresh equality is checkable by **byte comparison** and the ear gate can be waived by the Validator on byte-equality — a cheaper, stronger gate than ears.

---

## 2. Design

### 2.1 Key composition

```
key = sha256( schema_ver | backend_id | model_fp | voice | speed | sample_fmt | text_unit )
```

| Field | Content | Notes |
|-------|---------|-------|
| `schema_ver` | int, starts 1 | Bump invalidates everything on layout/logic change |
| `backend_id` | `ort-cpu` \| `ov-gpu` | Different backends may not be bit-identical to each other; never cross-serve |
| `model_fp` | model file fingerprint: `size:mtime_ns` (cheap) | Full sha256 of a ~300 MB ONNX at startup is acceptable once — Grok's call on cheap vs strong; record choice |
| `voice` | voice id string | |
| `speed` | float, normalized repr (e.g. `1.0`) | |
| `sample_fmt` | rate + encoding of stored PCM | |
| `text_unit` | **C1:** full request text, exact bytes post any existing server normalization. **C2:** chunker output text, exact | Key on *post-chunker* text so the chunker itself stays free to evolve (chunker version folds into `schema_ver`) |

Response format (wav/mp3 container) is **not** in the key: store canonical trimmed PCM once, encode on the way out. Container encode is cheap; caching per-container multiplies storage for nothing.

### 2.2 Storage layout

```
KOKORO_CACHE_DIR/tts-cache/v1/
  ab/abcdef….pcm        # raw PCM (int16, native rate), post-trim
  ab/abcdef….json       # sidecar: key fields, created, samples, duration
```

- Two-hex-char sharding to keep directories sane.
- **Store post-trim chunk waveforms** (C2) / post-assembly waveform (C1) so served output is byte-identical to the non-cached path.
- Atomic writes: write to `tmp/` + `rename()`. Readers tolerate missing/partial by treating as miss.

### 2.3 Eviction

Size-capped LRU-by-mtime, lazy: on write, if dir size > `KOKORO_CACHE_MAX_MB`, delete oldest-mtime entries until under (touch mtime on read hit to approximate LRU). No background threads, no daemon. Simple beats clever at this scale — a 500 MB cap holds roughly 90 minutes of 24 kHz int16 audio, which is a lot of distinct utterances for one household server.

### 2.4 Request flow (C1+C2 composed)

```
request → build C1 key → hit? → stream stored bytes            [zero compute]
                       ↘ miss → chunk text → per-chunk C2 keys
                                → synth only missing chunks     [partial compute]
                                → assemble (existing trim path)
                                → write C2 entries + C1 entry
                                → stream
```

C1 check first (zero-cost win), C2 fills the gap. Both tiers independently flaggable.

### 2.5 Configuration (env, matching house style)

| Var | Default | Meaning |
|-----|---------|---------|
| `KOKORO_CACHE` | `0` | `0` off, `1` on — **opt-in at ship**, flip default later on evidence |
| `KOKORO_CACHE_DIR` | `<sandbox>/cache/tts` | storage root |
| `KOKORO_CACHE_MAX_MB` | `500` | eviction cap |
| `KOKORO_CACHE_TIER` | `both` | `response` \| `chunk` \| `both` — lets probes isolate tiers |

### 2.6 API honesty

- New response header `X-Kokoro-Cache: hit | partial | miss` (C1 hit / C2 partial / cold).
- `X-Kokoro-RTF` on a hit reports the true (tiny) wall/audio ratio — the header never lies — but README language must say cached RTF is a serving number, not a synthesis number. **No README claim changes until the Validator signs the probe matrix** (standing rule).
- Per-chunk debug lines gain a `cache=hit|miss` field alongside the existing peak/ref/gap/tail verdicts, so evidence logs stay one-stop.

---

## 3. Phasing

| Phase | Content | Version |
|-------|---------|---------|
| **C1** | Response cache + eviction + headers + debug fields | v1.2.0 (dev phase) |
| **C2** | Chunk tier + partial assembly | v1.2.0 (same product ship; was labeled 1.2.1 in dev) |
| **Ship** | C1+C2 together | **product v1.2.0** (Nexus collapse — notes/43) |

Rationale: C1 is small, self-contained, and delivers the demo-visible win (repeat request → instant). C2 touches the chunk loop and deserves its own probe pass. Mechanic gets one locked design per phase; no drive-by merging.

---

## 4. Probes and gates (bars before numbers)

### P0 — Determinism (gate for the byte-equality validation path)

Same request twice, cache **off**, both backends. Byte-compare WAVs.
**Predicted: PASS** — Kokoro inference is sampling-free and both backends should be run-to-run deterministic on fixed hardware. **If FAIL** (nondeterministic bytes): not a kill — validation degrades from byte-equality to corr ≥ 0.9999 + Nexus ears on the standard set, and the note records which backend wobbles and where.

### P1 — Hit correctness

Request twice with cache on: second response byte-identical to first, header `hit`.
**PASS:** byte-equal. **KILL (bug-class):** any byte drift on a hit — that's a storage/encode defect, fix before proceeding.

### P2 — Hit latency

Fox-class and one long passage, cache hot.
**Predicted:** total server time < **100 ms** fox-class on hit (disk read + WAV header + stream); effective RTF ≤ 0.03.
**PASS:** hit ≤ 10% of the same request's fresh synth time on ort-cpu. (Generous bar; prediction says we beat it by an order of magnitude.)

### P3 — C2 partial assembly (phase C2 only)

Cache a 3-sentence passage, then request a 4-sentence passage sharing sentences 1–3.
**PASS:** header `partial`; only sentence 4 synthesized (debug lines prove it); output byte-identical to a fresh cache-off synthesis of the full passage.
**KILL (bug-class):** assembly from cached chunks differs from fresh — violates §1's soundness argument, halt and diagnose.

### P4 — Eviction

Fill past `KOKORO_CACHE_MAX_MB` with generated variety; verify cap honored, oldest evicted, no serving errors mid-eviction.

### P5 — Concurrency smoke

Two simultaneous identical cold requests (race on same key): both succeed, no corrupt entry (atomic-rename discipline), at most duplicated work, never a broken file.

### Ears

**Waived on byte-equality** (P0+P1+P3 pass) per §1 corollary — Validator signs the waiver explicitly in the results note. If P0 fails, standard ear set applies (fox + 2 shorts + 1 long, by filename).

---

## 5. Predicted branches

| Branch | Signature | Implication |
|--------|-----------|-------------|
| **K1 — clean** | P0–P5 PASS | Ship C1; open C2; README gains cache section post-Validator |
| **K2 — nondeterminism** | P0 byte drift (suspect ov-gpu first if anywhere) | Ear-gated validation path; cache still ships; note records drift magnitude |
| **K3 — assembly drift** | P3 fails byte-equality | Halt C2, keep C1; diagnose trim/concat state leak — would indicate the chunk loop carries hidden state, itself a finding |
| **K4 — hit latency disappoints** | P2 > bar | Profile: encode-on-the-fly cost vs disk; consider caching encoded container after all (design §2.2 revisited by amendment, not silently) |

## 6. What not to touch

- `models/patched/`, model files, backend selection logic — cache sits strictly **above** synthesis.
- Trim/assembly logic — C2 *calls* it, never modifies it (P3 enforces).
- S0 side venv, `spike/ov263-genai/` — different track entirely.
- README/default claims until Validator signs the matrix.
- No new dependencies: stdlib `hashlib`, `os`, `json` only.

## 7. Open questions for Grok before Mechanic dispatch

1. `model_fp` cheap (`size:mtime_ns`) vs strong (startup sha256, cached)? Strong is one-time ~seconds; my lean is **strong** — it's the field that prevents the subtlest wrong-audio bug.
2. Any host constraint on `KOKORO_CACHE_DIR` placement (disk budget, filesystem) I should reflect in defaults?
3. Concurrency reality check: current server request handling (single worker? threaded?) — determines whether P5 needs a real lock or rename-atomicity alone suffices.

## 8. One-line

**Two-tier disk cache keyed on the exact synthesis unit the server already uses — zero new seams, byte-identical on hit, ear gate replaced by byte-equality where determinism holds, phased C1→C2, all bars written before numbers.**

---

*Fable (Chief Architect), 2026-08-07. Grok: review + answer §7; Nexus: ack phasing; then Mechanic dispatch on C1 with this note as the locked design.*
