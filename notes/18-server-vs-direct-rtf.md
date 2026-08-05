# Server vs direct RTF (Fable note_12 follow-up)

**Date:** 2026-08-04  
**Trigger:** After steady-state direct RTF ~0.60, Fable asked why the server still looked like 18–25 s/request.

## Method

Fox sentence via `POST /v1/audio/speech`, `ov-gpu` f32, bucket 96.  
`intel_gpu_top -l -s 500` during requests.  
A: existing `cache/openvino` (~9.8G). B: empty fresh CACHE_DIR.  
C: `test_kokoro_ov_direct.py --tokens 96 --warmup 1 --runs 3`.

## Results

### A — server + existing cache

| req | wall_s | x-kokoro-rtf | notes |
|-----|--------|--------------|--------|
| 1 | 18.99 | 5.91 | first infer after compile |
| 2 | 2.97 | 0.92 | steady |
| 3 | 2.91 | 0.90 | steady |

- Log: `[ov-gpu] compiled bucket=96 in 0.9s` (cache hit)
- gputop during work: **act ~1050–1090 MHz**, **RCS 95–100%**, gpu ~6–7 W  
  → not a clock/power collapse

### B — server + empty cache

| req | wall_s | rtf |
|-----|--------|-----|
| 1 | 19.03 | 5.92 |
| 2 | 3.56 | 1.10 |
| 3 | 2.90 | 0.90 |

- Log: `compiled bucket=96 in 11.1s` (cold compile)
- Steady same as A → **not** a stale-blob-makes-every-request-slow story

### C — direct n=96

- warmup 31.8 s; steady mean **4.27 s**; samples 168600 → audio 7.03 s → **RTF_steady ≈ 0.61**

## Interpretation

1. **Tonight (2026-08-04 evening) cold-first-infer fully explains multi-second first requests:** only req1 is ~19 s; req2/3 are ~2.9 s. CACHE_DIR and clocks are not the steady-state culprit.
2. **But do not hard-close history as "always only cold":** the v114 probe log (same process lifetime) shows startup warmup on bucket 96, then *five sequential bucket-96 requests* each at 18.5–24.8 s. If cold-start were the whole story, s1 onward should have been ~3 s. That all-requests-slow behavior is **unexplained and unreproducible tonight** — anomaly on record. Candidates: mid-day venv/driver change (OV version was not logged then — v1.1.6 now prints `openvino=` at startup), competing GPU consumer, or power/scheduling state without gputop. If it recurs in the field, the record should say "we saw this once," not "this cannot happen."
3. **Steady server fox ≈ 0.90 RTF** (~2.9 s wall) with clocks pegged — production-interesting once warm.
4. **CACHE_DIR helps compile time** (0.9 s vs 11 s), not steady infer.
5. Gap vs direct n=53 RTF ~0.62: server **pads to bucket 96** so it pays ~96-token compute for ~55 real tokens; RTF uses trimmed audio length → looks worse than tight-N direct.
6. OpenVINO issue drafts stay valid (direct-test numbers).

## Follow-up: v1.1.6 `KOKORO_WARM_BUCKETS` (validated)

- Fable shipped startup pre-warm + OV version log.
- **All-zero pad pre-warm is insufficient:** zeros ~31 s still left first fox at ~18 s RTF.
- **Real-text `synthesize` pre-warm works:** `pre-warmed bucket~96 via synthesize in 18.6s` then req1/2/3 **2.94 / 2.85 / 2.88 s, RTF 0.91 / 0.89 / 0.89**.
- Ops: set `KOKORO_WARM_BUCKETS=96,192` (etc.) for serving.

## Ops takeaway

- Prefer **ort-cpu** when first-token latency matters and shapes vary.
- **ov-gpu** fine for demo / batch after warming buckets (96/192/…).
- Do not cite single first-request walls as steady RTF.
