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

1. **Historical 18–25 s/request was cold first-infer** (and/or first-request-only timing), not steady-state server throughput.
2. **Steady server fox ≈ 0.90 RTF** (~2.9 s wall for ~3.2 s audio) with clocks pegged — production-interesting on this UHD class once the shape is warm.
3. **CACHE_DIR helps compile time** (0.9 s vs 11 s), not steady infer.
4. Gap vs direct n=53 RTF ~0.62: server **pads to bucket 96** so it pays ~96-token compute for ~55 real tokens; RTF uses trimmed audio length → looks worse than tight-N direct. Still sub-realtime after warmup.
5. OpenVINO issue drafts stay valid (direct-test cold/steady numbers). Optional follow-ups: bucket warmup at startup, tighter buckets, README “demo-only” softens to “warm steady ~0.9 RTF / cold first shape multi-second”.

## Ops takeaway

- Prefer **ort-cpu** when first-token latency matters and shapes vary.
- **ov-gpu** fine for demo / batch after warming buckets (96/192/…).
- Do not cite single first-request walls as steady RTF.
