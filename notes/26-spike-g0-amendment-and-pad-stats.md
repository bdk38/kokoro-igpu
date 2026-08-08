# notes/26 — G0 amendment record + padding-statistics sub-experiment

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Design:** `Fable/note_18` (Nexus-acked)  
**Path:** Spike only

---

## 1. G0 amendment (binding) — folded into gate record

Per note_18 §2, note_17 G0 is amended:

**G0 PASS** = `unexpected_keys == []` **and** every missing key is on the structural allowlist:

1. `*.norm.weight` / `*.norm.bias` on AdaIN `InstanceNorm1d` (`affine=True`, absent from v1.0 ckpt)
2. `generator.stft.*` buffers under `disable_complex=True`

Any missing key outside the allowlist, or any unexpected key = **hard stop**.  
Allowlist check is automated in `spike/pad_stats.py` (`missing outside allowlist = 0, unexpected = 0` printed) and will be required in the G2 export script.

**notes/25 under amended gate:** G0 **PASS**. G1 unchanged PASS.  
Nexus ear PASS on the three G1 WAVs logged in note_18.

---

## 2. Padding-statistics sub-experiment (note_18 §3.4) — DONE

**Why before G3:** Instance norms over time mean padded seam frames change the math on *real* frames. This run shows that is not theoretical.

### Method

```bash
/data/kokoro-openvino/venv-peek/bin/python spike/pad_stats.py
```

| Item | Value |
|------|--------|
| Script | `spike/pad_stats.py` |
| Result JSON | `spike/out/pad_stats/pad_stats_result.json` |
| WAVs | `spike/out/pad_stats/unpadded_T90.wav`, `padded_{zero,edge}_T96_{full,realregion}.wav` |
| Native T | **90** |
| Bucket T | **96** |
| Real region | leading **54 000** samples (90 × 600) |
| Seed | 0 (same NSF draw intent both paths) |
| G0 allowlist | **PASS** (0 outside, 0 unexpected) |

Compare: `decoder(native T)` vs `decoder(padded→96)[:54000]` — pad is trailing time.

### Results (real region only)

| mode | maxdiff | mean\|diff\| | corr | rms_ratio (pad/nat) | branch |
|------|--------:|-------------:|-----:|--------------------:|--------|
| **zero** | **0.199** | 0.00588 | **0.9727** | 1.030 | **P2** |
| **edge** (replicate) | **0.0693** | 0.00259 | **0.9970** | 1.048 | **P1_weak** |

note_18 bars:

- **P1:** corr ≥ 0.999 (expected small nonzero maxdiff)
- **P2:** corr < 0.99 or gross level shift

### Verdict

```text
primary_branch_zero_pad = P2
edge_branch             = P1_weak
verdict                 = P2_then_edge_P1_weak
recommended_action      = use_edge_replication_padding_for_export
```

**One line:** Zero-pad to T=96 **fails** the padding honesty bar (corr 0.973). Edge-replication recovers to corr ≈ 0.997 (above 0.99, short of 0.999) with ~5% RMS lift — **export must not use zero-pad**; use edge-replication (or redesign finer T buckets) before any G3 OV matrix.

---

## 3. Why this would have polluted G3

G3’s “no novel-text JIT” and RTF claims assume the static-T decoder is a faithful stand-in for variable-length speech. If we zero-pad features into a fixed bucket, **the un-padded region’s waveform moves** (maxdiff ~0.2, corr ~0.97). That would look like quality/RTF noise or false “OV vs PT” gaps inside G3. Catching it here keeps G3 about compile/cache/offload, not pad-norm contamination.

---

## 4. Implication for G2 / G3

| Path | Status |
|------|--------|
| G2 export default pad | **edge-replication**, not zeros |
| G2 parity methodology | Real region after trim only; document pad mode in the note |
| G2 ears | Still required (P1_weak is not bit-exact; house rule) |
| G3 | Do **not** start until G2 uses a pad mode that is at least P1_weak and ear-clean |
| Optional follow-up | Finer T lattice (e.g. step 4–8) if ears reject edge pad or we need corr ≥ 0.999 |

Ship freeze unchanged. G2 export code **not started** in this note — pad decision is the blocker that is now measured.

---

## 5. Predicted log signatures (note_18 §4) vs actual

| Expected | Actual |
|----------|--------|
| G0 allowlist: outside=0, unexpected=0 | **Met** |
| P1/P2 table + one-line branch | **Met** — zero=P2, edge=P1_weak |
