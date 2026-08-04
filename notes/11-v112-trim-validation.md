# Grok note_6 — v1.1.2 validation (2026-08-04)

Server: ov-gpu f32, patched model, `KOKORO_TRIM_DEBUG=1`, `0.0.0.0:8880`
Log: `logs/server_v112.log`
Artifacts: `artifacts/v112/`

Note: FastAPI `version=` string in file still says `1.1.1`; logic is v1.1.2 (structure trim + lock + debug).

## Protocol run

1. Restarted with trim debug.
2. Single-curl full repro text (one request).
3. Per-sentence curls for the four repro sentences + fox.
4. 4-way concurrent fox lock probe.
5. Human listen pass (user).

## Full repro (single POST)

- HTTP 200, backend ov-gpu, RTF **4.32**, audio **17.11 s**, wall ~74 s
- tokens=247 → n_real=249 → bucket 288
- `[trim] groups=13 stripped=0 cut=17.11s` (raw 17.62s → only trailing silence)
- Post-hoc energy: last group 16.68–17.08s, dur=0.40s, **peak/ref=0.64** — above `TRIM_MOAN_RMS_RATIO=0.6`, so intentionally kept
- No mid-text drop at server: full passage present in one WAV

WAV: `artifacts/v112/full_repro.wav`

## Per-sentence trim log

- s1_well: tokens 71, 73/96, 6.25→5.11s, stripped=1, RTF 4.86 — moan stripped
- s2_wallet: tokens 63, 65/96, 5.58→5.11s, stripped=0, RTF 4.29 — list pause kept (v1.1.1 regression target)
- s3_peter: tokens 51, 53/96, 4.80→4.01s, stripped=0, RTF 5.71 — trailing group peak/ref~0.74 kept
- s4_swans: tokens 59, 61/96, 5.65→4.13s, stripped=1, RTF 5.38 — moan stripped
- fox: tokens 53, 55/96, 4.72→3.07s, stripped=2, RTF 6.06 — double burst stripped

### Wallet sentence (critical)

v1.1.1 would cut after “the wallet,”. v1.1.2:

- stripped=0
- groups include a strong continuation after the list pause (g2 ~3.46–4.36s peak/ref 1.39)
- residual weak tail g3 4.82–5.10s peak/ref **0.825** not stripped (above 0.6)

Server-side false-positive skip is fixed. Residual pad tail is a separate knob issue (see ear verdict).

## Concurrency / lock

4 parallel fox POSTs: **all HTTP 200**, identical 147404-byte WAVs, no `Infer Request is busy`.
Wall 11.76s with staggered finish times (3.1 / 6.0 / 8.8 / 11.8s) → lock serializes as designed.
Reported RTF includes queue wait (0.97 … 3.80) — expected.

## Human ear verdict (user) — 2026-08-04

**Completeness / naturalness: PASS on all tested sentences.**
All sentences were complete and sounded natural. No mid-utterance skips on the server single-request path. The v1.1.1 “wallet / passport” false cut is gone to the ear.

**Pad breath/moan still present on:**

- `artifacts/v112/s3_peter.wav` — pad breath/moan at end
- `artifacts/v112/s2_wallet.wav` — pad breath/moan at end
- `artifacts/v112/full_repro.wav` — pad breath/moan at end

**Implied clean (not called out):** s1_well, s4_swans, fox — matches trim log stripped≥1 on those.

### Metric reconciliation (why trim missed these)

Surviving trailing groups that ears flag as moan, all failed the 0.6 peak/ref gate:

- full_repro tail group: peak/ref **0.64**, 0.40 s
- s2_wallet tail: peak/ref **0.825**, 0.28 s
- s3_peter tail: peak/ref **0.74**, 0.22 s

So v1.1.2 structure logic is correct (does not cut real continuation; wallet peak/ref ~1.39 survived), but `TRIM_MOAN_RMS_RATIO = 0.6` is **too strict** for real OV-GPU pad bursts on this host. Pad energy is often 0.64–0.83× head ref, not below 0.6.

### Suggested next knob (for Fable)

Raise `TRIM_MOAN_RMS_RATIO` toward **~0.85–0.90** and re-run the same artifact set:

- Must still keep wallet continuation (peak/ref ~1.39) and full-sentence completeness
- Must strip peter/wallet/full_repro tails (0.64–0.83)
- Re-check s1/s4/fox stay clean (no new last-word clip)

Optional: log per-stripped-group peak/ref in `KOKORO_TRIM_DEBUG` so the next tune is data-first.

## Status split

| Item | Status |
|------|--------|
| v1.1.1 mid-sentence false trim | **Fixed** (ear + log) |
| OV infer lock / no busy 500 | **Fixed** |
| Sentence completeness (server curl) | **PASS** |
| Pad moan fully gone | **FAIL** on peter, wallet, full_repro |
| WebUI Read Aloud skips | Not re-tested this round; server path no longer explains them via trim |
| Product default speed (OV-GPU RTF) | Still 4–6×; unchanged |

## Open for Fable

1. Loosen moan RMS ratio (primary) using the three failing peak/ref numbers above.
2. Minor: bump FastAPI version string to `1.1.2`.
3. After retune: same probe script `scripts/probe_v112.py` + ear on `s2_wallet`, `s3_peter`, `full_repro`, plus regression on fox/s1/s4.

## Artifacts

- `artifacts/v112/full_repro.wav` + `.headers` + `.json`
- `artifacts/v112/s{1..4}_*.wav`, `fox.wav`
- `artifacts/v112/sentence_matrix.json`
- `scripts/probe_v112.py`, `scripts/probe_v112_lock.py`
- this note: `Grok/note_6-v112-results.md`
