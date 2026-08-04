# v1.1.4 structural trim validation

Date: 2026-08-04  
Server: `scripts/kokoro_server.py` **v1.1.4**, ov-gpu f32, `KOKORO_TRIM_DEBUG=1`  
Model: `models/patched/kokoro-v0_19.gpu4d.stft.onnx`  
Log: `logs/server_v114.log`  
Artifacts: `artifacts/v114/`  
Prior: `notes/12-v113-trim-retune.md`, Fable `note_8`

## What changed (v1.1.3 → v1.1.4)

- `TRIM_PAD_GAP_S = 0.15` — strip only if pre-gap ≥ 0.15 s (`kept:attached`)
- `TRIM_TERMINAL_SIL_S = 0.8` — strip only if silence after group ≤ 0.8 s (`kept:long-tail`)
- Ref = p90 of frames ≥ 0.1× clip max RMS; `TRIM_REF_FLOOR = 1e-3`
- Debug: `gap=` / `tail=` per group
- Version **1.1.4**

## Human ear verdict (user) — 2026-08-04

**PASS (only issues called out were the two below):**
- s2_wallet — passport complete, moan gone (log + implied ear OK)
- s1_well, s4_swans, fox, full_repro — not listed as problems

**FAIL — pad breath/moan still present:**
- `artifacts/v114/whisper_stop.wav`
- `artifacts/v114/s3_peter.wav`

## Duration vs prior

| clip | v112 | v113 | v114 | ear v114 |
|------|------|------|------|----------|
| s2_wallet | 5.11 | 4.03 clip | **4.39** | PASS |
| s3_peter | 4.01 moan | 3.19 clean | **4.01** | **FAIL moan** |
| whisper_stop | — | 4.78 moan | **3.63** | **FAIL moan** |
| full_repro | 17.11 | 16.11 | 16.09 | PASS |
| s1 / s4 / fox | … | … | stable | PASS |

## Failure analysis (post-ear)

### s3_peter — confirmed terminal-gate miss

Log:
```
g4: 3.78-3.98s dur=0.20s peak/ref=0.66 gap=0.62s tail=0.82s -> kept:long-tail
stripped=0 cut=4.01s
```

WAV still has energy 3.78–4.00s (peak/ref ~0.66–0.77).  
**tail=0.82 > TRIM_TERMINAL_SIL_S=0.8** by only **20 ms** → gate blocks strip.

v113 had cut=3.19s (moan gone, ear PASS). v114 restored the moan.

**Fix:** raise `TRIM_TERMINAL_SIL_S` to at least **0.85**, safer **0.90–1.00**.

### whisper_stop — long-tail gate kept the moan, not “stop”

Log:
```
g2: 3.28-3.60s dur=0.32s peak/ref=0.66 gap=0.64s tail=1.16s -> kept:long-tail
stripped=0 cut=3.63s ref=0.1434  (healthy ref — good)
```

Delivered WAV ends at 3.63s and **still contains** the 3.28–3.62s band (peak ~0.66×, tail0.5 peak 0.26). Ear: pad moan.

Revised interpretation vs earlier note:

| region | time | likely content |
|--------|------|----------------|
| g1 | ~1.52–2.64s | “…then whispered, stop” (or through whispered) |
| gap | 2.64–3.28s | 0.64 s quiet |
| g2 | 3.28–3.62s | **pad moan** (0.66×, 0.32 s) — NOT a word we must keep |
| after (v113 only) | 3.63–4.78s | more pad / silence (already cut in v114) |

v114’s long-tail gate was designed assuming g2 was the word “stop” with 1.14 s of pad after it. Ear says g2 **is** the moan. Cutting after g2 therefore **keeps** the moan and only drops sub-threshold tail.

So for whisper:
- ref fix worked
- cut improved vs v113 (4.78 → 3.63) but stopped one group too late
- correct cut is ~2.67s (end of g1 + margin), i.e. **strip g2**

g2 strip profile: weak 0.66×, short 0.32s, detached gap 0.64s, but tail 1.16s → fails terminal gate only.

**Same root knob as peter:** terminal gate. If ceiling rises to ~1.0, peter’s 0.82 strips; whisper’s 1.16 **still would not**.

Whisper needs either:
1. **Higher terminal ceiling alone is insufficient** (1.16 > 1.0)
2. **Strip last weak detached group even with long tail when it sits in pad window and peak/ref < R** (pad-final exception)
3. **Position gate:** strip if group starts after `n_real/n_bucket * audio_len` (or after last high-energy speech island)
4. **Don’t use long-tail to keep weak groups** — only use long-tail to protect groups with peak/ref above a speech floor (e.g. keep long-tail only if peak/ref ≥ 0.85 or 1.0). Then whisper g2 at 0.66 strips; a real soft “stop” at 0.84 might still strip (Fable caveat) unless also attached/gap-protected
5. Measure: if “stop” is inside g1, long-tail protection on weak trailing groups is simply wrong for this utterance

**Recommended combined fix for Fable:**
- `TRIM_TERMINAL_SIL_S`: 0.8 → **0.95** (clears peter 0.82; margin under whisper 1.16)
- **Plus** change long-tail keep rule: `kept:long-tail` only if `peak/ref >= TRIM_LONGTAIL_MIN_RATIO` (suggest **0.85** or **0.9**). Weak detached pad bursts with long trailing silence still strip.
  - peter 0.66 → strip (even if tail were long)
  - whisper g2 0.66 → strip
  - wallet port 0.36 attached → still kept:attached (unchanged)
  - real speech continuation 1.17× → kept:too-loud
  - risk: true soft final word 0.70–0.84× with long tail after it could strip — needs ear on a real soft ending that is not pad

Alternative simpler A/B: drop terminal gate entirely; rely on detached + weak + short + pad window. Re-check wallet/fox/full_repro.

### s2_wallet — SUCCESS (log + ear)

```
g5 moan stripped gap=0.46; g4 port kept:attached gap=0.10; cut=4.39s
```

Detachment gate is doing the right job. Do not loosen `TRIM_PAD_GAP_S` without cause.

## Status summary

| Item | Status |
|------|--------|
| ref floor | PASS |
| wallet passport + no moan | **PASS** (ear) |
| detachment gate 0.15 | **PASS** |
| peter moan | **FAIL** (terminal 0.82 > 0.8) |
| whisper moan | **FAIL** (long-tail kept pad group at 3.28–3.62) |
| s1/s4/fox/full_repro | PASS (ear) |
| WebUI Read Aloud | still open |

## Open for Fable (priority)

1. Raise `TRIM_TERMINAL_SIL_S` to **~0.95** (peter).
2. Fix whisper: do not keep weak pad groups via long-tail — e.g. long-tail keep only if `peak/ref >= ~0.85–0.9`, or strip final weak detached group inside pad window regardless of tail.
3. Re-probe: s3_peter, whisper_stop, s2_wallet (no passport regression), full_repro, fox.
4. WebUI multi-POST still outstanding after trim closes.

## Artifacts

- `artifacts/v114/*.wav`, `sentence_matrix.json`
- `artifacts/v113/s3_peter.wav` (clean moan-free reference, 3.19s)
- `logs/server_v114.log`
- this note

Server left running on `0.0.0.0:8880`.
