# v1.1.8 shape-key experiment (Fable note_15 / probe_v118)

**Date:** 2026-08-04  
**Probe:** `scripts/probe_v118_shape_key.py`  
**Backend:** ov-gpu f32 direct (no HTTP server)  
**Model:** `models/patched/kokoro-v0_19.gpu4d.stft.onnx`  
**OpenVINO:** 2026.2.1-21919-ede283a88e3-releases/2026/2  
**Logs:** `logs/probe_v118_phase1.log`, `logs/probe_v118_phase2.log`  
**Artifacts:** `artifacts/v118/`  
**Author:** Grok (measurement)

## Question

notes/19: warm does not transfer across *content* inside a compiled bucket.
Fable hypothesis: warm is keyed on the **exact internal dynamic shape**
(total output frame / sample count from the duration predictor), via
in-process GPU-plugin shape-specialized kernel JIT that CACHE_DIR does not
persist.

Discriminating test: different texts A and B with **exactly equal** raw
pre-trim sample counts. Fresh process: warm A, then first-ever B.

- B WARM + control C COLD => shape-keyed confirmed
- B COLD => keying deeper than total frame count
- B MID => partial/async; repeat before concluding

Bonus: A @ speed=1.05 should re-cold if key is frames-not-text.
CPU excess: if (cold_wall - warm_wall) ~= (cold_cpu - warm_cpu), cold cost
is host-side JIT.

## Phase 1 — screen 72 novel sentences (one process)

Compile bucket 96 cache-hit 0.9 s. Each candidate: one raw padded infer
(bypass trim), record n_samples / wall / process CPU.

### Summary

- 72/72 landed in bucket 96 (0 skipped)
- Labels on first hit: **71 COLD, 1 WARM**
- The single WARM was c32: n_samples=120000 matching earlier c28
  (same shape already JIT'd in this process)
- Wall (all): min 3.23 / med 20.26 / max 27.17 s
- Cold only (n=71): wall med **20.27 s**, cpu med **20.59 s**
- Lattice GCD of unique sample counts: **600 samples** (25 ms @ 24 kHz)
- Collision groups with exact equal n_samples: **17**
- Auto-picks (prefer max |n_real| delta among collisions):

| role | name | n_real | n_samples | text |
|------|------|--------|-----------|------|
| A | c02 | 62 | 119400 | My brother painted the garden fence a deep shade of green. |
| B | c48 | 45 | 119400 | Heavy fog rolled off the bay before dawn. |
| C | c05 | 59 | 121200 | Every morning the baker stacks warm loaves in the window. |

A/B share shape with **17-token** real-length gap — strongest form of the claim.

### Warm-survival revisits (end of phase 1)

- revisit_first c00 (n_samples=131400): wall **21.49 s COLD** after ~70 novel shapes
- revisit_last c71 (n_samples=116400): wall **3.10 s WARM**

Sample counts matched phase-1 first hits (determinism OK).  
**Interpretation:** in-memory shape cache is **finite**; early shapes are
evicted under a long novel-shape gauntlet. Last shape still resident.

### Phase-1 same-shape later hits (observational, not the verdict)

Most later candidates that matched an earlier n_samples stayed **COLD**
(~19–20 s), not WARM. Only clear in-gauntlet warm transfer: c28 -> c32 at
120000 samples (c32 wall 3.23 s). Later 120000 hits (c52, c64) were cold
again — consistent with eviction or incomplete residency under load.

This does **not** overturn phase 2; it says the shape cache is real but
**not unbounded**. Phase 2 is the controlled few-shape test.

### Cold RTF distribution (upstream fodder)

Every phase-1 first infer is a novel-shape cold sample on Xe-LP f32:

- typical cold wall ~19–25 s for ~4.5–5.5 s raw audio
- raw RTF cold cluster ~3.9–5.0 (med wall/raw ~4.0)
- one outlier MID-ish: c19 wall 13.17 s (still labeled COLD by probe threshold)

CPU vs wall on colds: median (cpu - wall) only **+0.25 s**, but a subset
shows cpu ~38–43 s with wall ~22–25 s (delta up to ~16 s). Two cold modes
appear in the log (cpu-bound burst vs wall-matched). Phase 2's clean
excess check uses the wall-matched mode.

## Phase 2 — fresh process (THE TEST)

```
A=c02 B=c48 shared n_samples=119400
control C=c05 n_samples=121200
```

| step | name | n_samples | wall_s | cpu_s | label |
|------|------|-----------|--------|-------|-------|
| 1 | A1 | 119400 | 19.67 | 19.90 | **COLD** |
| 2 | A2 | 119400 | 3.05 | 3.07 | **WARM** |
| 3 | A3 | 119400 | 2.98 | 2.99 | **WARM** |
| 4 | **B1_TEST** | **119400** | **3.04** | **3.05** | **WARM** |
| 5 | B2 | 119400 | 3.00 | 3.02 | **WARM** |
| 6 | C1_control | 121200 | 19.56 | 19.73 | **COLD** |
| 7 | A @ speed=1.05 | 116400 | 18.97 | 19.14 | **COLD** |

No n_samples drift vs phase 1 on speed=1.0 rows. Determinism holds.
Control C cold => process can still be cold; B warm is not global warmup.
A@1.05 changed output length 119400 -> 116400 and re-colded.

### Probe verdict (printed)

```
SHAPE-KEYED CONFIRMED: first-ever B ran WARM (wall=3.04s vs A3=2.98s)
while control C ran COLD. Warm state is keyed on internal output shape,
not content.
A@speed=1.05 ran COLD (expected COLD if key is frames-not-text).
CPU-excess check: cold-vs-warm wall delta 16.6s, cpu delta 16.7s
(similar deltas => the cold cost is host-side JIT).
```

## Interpretation

1. **Warm is shape-keyed, not content-keyed.** Different text, different
   n_real (62 vs 45), identical raw sample count => B first-ever is warm
   after A. notes/19 "content" observation was a proxy for "usually unique
   internal shape per utterance."

2. **Key is output frame count (or something so tightly coupled that equal
   samples + speed change is enough).** Same text at speed 1.05 produces a
   new sample count and pays full cold again. Text identity is irrelevant.

3. **Cold cost is host-side JIT, ~17 s** on this box for bucket-96 shapes
   in the wall-matched mode (phase 2: d_wall 16.6 s ~= d_cpu 16.7 s).
   GPU execution when warm is ~3.0 s wall for ~5.0 s raw (~0.60 RTF raw),
   matching direct-test steady numbers from earlier notes.

4. **CACHE_DIR does not persist the shape kernels.** Compile of [1,96] is
   0.9 s cache hit every process; first use of each concrete internal shape
   still costs ~17–25 s. Matches notes/18 "cache shortens compile, not
   first-infer setup" with a sharper mechanism.

5. **In-process cache has limited residency.** Phase 1 revisit of c00 after
   ~70 novel shapes was cold again; c71 (last) stayed warm. Under varied
   Read Aloud traffic, expect repeated colds whenever a new shape appears
   or an old one was evicted — not a one-time per-process tax.

6. **Phase-1 same-shape colds under gauntlet** are compatible with (5):
   equal n_samples is the key when the kernel is still resident; it is not
   a guarantee after heavy novel-shape churn. Product language should not
   promise "once any sentence of length N was seen, all equal-N are warm
   forever."

7. **v114 fully explained:** five sequential probe sentences, five shapes,
   five colds. notes/18 fox req2 warm was same shape (same text) repeat.

## Product / docs impact (for Fable README pass)

Safe claims:

- ov-gpu steady on a **resident shape**: ~0.6 RTF raw / ~0.9 RTF
  trimmed-at-bucket-96 (prior server fox), after one cold hit of that shape.
- Cold: ~17–25 s host JIT per **novel internal shape** (not per bucket,
  not per text string as such).
- `KOKORO_WARM_BUCKETS` / pre-warm synthesize pins **whatever shape that
  pre-warm text produces**. Useful for a canned demo line; useless as a
  general varied-traffic accelerator unless traffic collides on shapes.
- Speed changes re-cold (new durations => new shape).
- ort-cpu remains the product default for Open WebUI varied Read Aloud.

Upstream issue 2 breadcrumb (add to draft):

- Per-shape kernel JIT on GPU plugin, not covered by CACHE_DIR model cache
- ~17 s host CPU per new output length on UHD Xe-LP f32 Kokoro
- Equal output sample count => warm transfer across different tokenizations
- Finite in-process residency (eviction under many shapes)
- Speed knob changes shape and re-triggers JIT

## Files

- `artifacts/v118/phase1_matrix.json` — 72 cold-ish samples + revisits + lattice
- `artifacts/v118/phase1_picks.json` — A/B/C
- `artifacts/v118/phase2_result.json` — verdict sequence
- `logs/probe_v118_phase1.log`, `logs/probe_v118_phase2.log`
- `scripts/probe_v118_shape_key.py`

## Bottom line

**SHAPE-KEYED CONFIRMED** (phase 2).  
**Cold cost ~= host JIT (~17 s), not GPU exec.**  
**Cache is in-process, shape-keyed, capacity-limited; CACHE_DIR does not help.**  
**README / WARM_BUCKETS wording can now be precise** — Fable unblocked.

No server was left running (probe is direct OV).
