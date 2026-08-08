# notes/40 — v1.2.0 C1 response cache probes

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator) + Mechanic (Grok Build)  
**Status:** **C1 CLOSED** (ort-cpu) — Validator byte-equality gate PASS; **Nexus ears 21/21 PASS** (supplementary).  
**Design:** `Fable/Fable-note_28-…` + lock `notes/39`  
**Fable read-back:** `Fable/fable_39_40_response`  
**Runtime:** ship dual-track OV **2026.2.1** + drivers 26.22.38646.7 / IGC 2.36.5, backend **ort-cpu**  
**Code:** C1 landed in tree then immediately extended by C2; **product ship = v1.2.0** (notes/43) with both tiers. Default `KOKORO_TTS_CACHE=0` until live soak.

---

## 1. What shipped in tree (uncommitted until Nexus push call)

| Item | Detail |
|------|--------|
| C1 response cache | Disk PCM under `$KOKORO_TTS_CACHE_DIR/v1/` |
| Env | `KOKORO_TTS_CACHE`, `_DIR`, `_MAX_MB`, `_TIER` — **not** stealing `KOKORO_CACHE` (OV) |
| Key | `sha256(schema\|backend\|model_fp\|voice\|speed\|sample_fmt\|text)` ; strong model sha256 at startup |
| Header | `X-Kokoro-Cache: hit\|miss` when enabled; omitted when off |
| Eviction | lazy LRU-by-mtime; **protect just-written key** (single-entry overshoot OK) |
| README | env flags only — **no** perf claims |

---

## 2. Probe matrix (bars from notes/39)

| Probe | Result | Evidence |
|-------|--------|----------|
| **P0** determinism, cache off | **PASS** | `p0_a.wav` == `p0_b.wav` (181244 B); no `X-Kokoro-Cache` |
| **P1** hit correctness | **PASS** | miss→hit; bodies byte-identical; headers `miss` then `hit` |
| **P2** hit latency | **PASS** | fox hit wall **20.6 ms** (fresh 1.58 s); ratio **1.3%**; long hit **20.8 ms** vs miss 4.47 s |
| **P4** eviction | **PASS** (after protect fix) | `MAX_MB=0.05`; keeps newest only; follow-up **hit** on #5 |
| **P5** concurrency | **PASS** | two cold identical → both 200, bodies equal, no `.tmp`; follow-up **hit** 2 ms |

### P1/P2 numbers (ort-cpu, fox)

| Step | cache | wall_s | X-Kokoro-RTF | bytes |
|------|-------|-------:|-------------:|------:|
| 1 | miss | 1.576 | 0.41 | 181244 |
| 2 | hit | 0.021 | 0.00 | 181244 |
| 3 | hit | 0.021 | 0.00 | 181244 |

Long passage hit wall 0.021 s; serving RTF header `0.00` (honest — not a synthesis claim).

### P4 note

First run with protect-less eviction deleted entries larger than the tiny cap (empty tree). QC fix: never unlink `protect_key` just written. Reprobe: `n_pcm=1`, total ~294 KB over 0.05 MB cap by design, **5hit=hit**.

### P5

| worker | status | cache | wall_s |
|--------|--------|-------|-------:|
| 1 | 200 | miss | 2.73 |
| 2 | 200 | miss | 2.81 |
| 3 follow-up | 200 | hit | 0.002 |

Bodies equal across workers; one pcm entry; duplicate cold work allowed.

---

## 3. Artifacts / logs

**21 WAVs** under `artifacts/v120_cache/`:

| Class | Filenames |
|-------|-----------|
| P0 | `p0_a.wav`, `p0_b.wav` |
| P1 | `p1_miss.wav`, `p1_hit.wav` |
| P2 | `p2_hit.wav`, `p2_long_miss.wav`, `p2_long_hit.wav` |
| P4 (pre-protect) | `p4_1.wav` … `p4_5.wav` |
| P4b (post-protect) | `p4b_1.wav` … `p4b_5.wav`, `p4b_5hit.wav` |
| P5 | `p5_1.wav`, `p5_2.wav`, `p5_3_hit.wav` |

- Logs: `logs/v120_p0_server.log`, `v120_p1_server.log`, `v120_p4b_server.log`, `v120_p5_server.log`  
- Probe cache dirs were under `/tmp/kokoro-c1-probe/` (ephemeral)

---

## 4. Validator verdict (formal gate)

- **P0+P1 byte-equality PASS** → ear gate **waived** for C1 *correctness* (note_28 §1 corollary).  
- **P2/P4/P5 PASS** on ort-cpu.  
- Product default remains **cache off** until Nexus wants opt-in default later.  
- README: flags only; no RTF marketing language added.

**Branch:** **K1 — clean** (note_28 §5). Open **C2** (chunk tier) when Nexus wants v1.2.1.

---

## 5. Nexus ears (supplementary confirmation — 2026-08-07)

Per Fable `fable_39_40_response`: byte-equality proves cache == fresh; it does **not** alone prove fresh is good. Nexus listened to the full artifact set.

**Verdict: PASS 21/21 by filename** — clear voices, **no additional utterances** (no pad-moan / extra speech), covering p0 / p1 / p2 / p4 / p4b / p5 classes.

Precedent stays clean:

- **Formal C1 correctness gate** = Validator byte-equality (waiver stands for future cache probes).  
- **Quality binding word** = Nexus ears (as always).  
- Side benefit: 21-sample ear pass on **post-rollback mixed stack** (wheel 2026.2.1 + new drivers) deepens notes/38’s two-utterance smoke.

---

## 6. Residual risks

1. ov-gpu not re-probed this session (C1 is backend-agnostic; keys include backend_id).  
2. Multi-worker uvicorn still not supported (process-local lock only) — matches current `uvicorn.run` single process.  
3. Exact-text keying: whitespace variants miss (intended).  
4. Uncommitted until Nexus commit/push call.

---

## 7. One-line

**v1.2.0 C1 CLOSED: P0–P5 PASS; Nexus ears 21/21 clear/no-extra; hit ~21 ms vs ~1.6 s fresh; K1 clean — commit on your call; C2/S0 next.**
