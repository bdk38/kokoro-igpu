# v1.1.3 trim retune validation

Date: 2026-08-04  
Server: `scripts/kokoro_server.py` **v1.1.3**, `KOKORO_BACKEND=ov-gpu`, f32, `KOKORO_TRIM_DEBUG=1`  
Model: `models/patched/kokoro-v0_19.gpu4d.stft.onnx`  
Log: `logs/server_v113.log`  
Artifacts: `artifacts/v113/`  
Prior: `notes/11-v112-trim-validation.md`, Fable `note_7`

## What changed (v1.1.2 → v1.1.3)

- `TRIM_MOAN_RMS_RATIO`: 0.6 → **0.9**
- `TRIM_MOAN_MAX_S`: 0.8 → **0.6**
- Per-group debug verdicts under `KOKORO_TRIM_DEBUG=1`
- FastAPI version string: **1.1.3**

## Probe set

`scripts/probe_v113.py`: s1_well, s2_wallet, s3_peter, s4_swans, fox, whisper_stop, full_repro.

## Duration delta vs v1.1.2

- s1_well: 5.11 → 5.11 (0)
- s2_wallet: 5.11 → **4.03** (−1.08)
- s3_peter: 4.01 → **3.19** (−0.82)
- s4_swans: 4.13 → 4.13 (0)
- fox: 3.07 → 3.07 (0)
- full_repro: 17.11 → **16.11** (−1.00)
- whisper_stop: n/a → 4.78

## Human ear verdict (user) — 2026-08-04

**PASS (natural, complete, no pad moan):**
- s1_well.wav
- s3_peter.wav
- s4_swans.wav
- fox.wav
- full_repro.wav

**FAIL:**
- **s2_wallet.wav** — word “passport” cut off at **pass^port** (second half missing)
- **whisper_stop.wav** — pad breath/moan still at end

So v1.1.3 fixed the three prior moan cases on peter/full_repro (and log-stripped wallet’s true moan), but over-trimmed inside “passport” and still missed whisper’s pad tail.

## Failure analysis (for Fable)

### 1) s2_wallet — “passport” split across groups

Trim log:
```
g5: 4.82-5.08s dur=0.26s peak/ref=0.70 -> stripped   (true moan; good)
g4: 4.10-4.36s dur=0.26s peak/ref=0.36 -> stripped   (THIS is the damage)
g3: 3.46-4.00s dur=0.54s peak/ref=1.17 -> kept:too-loud
cut=4.03s  stripped=2
```

Waveform compare v112 (complete, 5.11s) vs v113 (4.03s):

- Shared strong region 3.46–4.00s (peak ~1.2–1.4×) = start of “passport” / “pass…”
- v112 continues 4.10–4.36s at **weaker** energy (~0.24–0.43× frame ratio) before the later moan at 4.82–5.08s
- v113 classified 4.10–4.36s as its own gap-separated group and stripped it as a pad burst (short + peak/ref 0.36 < 0.9)

So “passport” has an **internal ≥100 ms dip** that splits one word into two RMS groups. The trailing syllable/release is soft enough to pass all three moan tests. Ratio 0.9 did not cause this by itself — **0.36× would also strip at 0.6** — the new aggressiveness is that we now walk multiple trailing groups; v1.1.2 left stripped=0 on wallet and kept everything through the moan.

This is Fable’s predicted soft-short-after-pause hazard, realized on a **mid-word** gap rather than a whispered final word.

v112 wallet post-hoc had passport-ish span 3.46–4.36s as one longer group; v113’s frame grouping still splits at the dip when re-analyzed at same thresholds — the keep vs strip decision on g4 is the regression.

**Repair directions (server):**
1. **Don’t strip a group if it is immediately followed by another strip-candidate and together they bridge to strong speech** — weak; g4 is followed by moan not speech.
2. Better: **require pad burst to be the final energy before trailing silence**, and/or require a longer pre-burst gap than intra-word gaps (e.g. gap ≥ 150–200 ms), and/or **merge groups across gaps unless gap looks “pad-like” (very deep near-zero)**.
3. **Position gate** Fable held back: only strip groups that start past `n_real/n_bucket` fraction (with slack). Wallet g4 at 4.10/5.58 ≈ 0.73 vs n_real/bucket = 65/96 ≈ 0.68 — borderline; full_repro moan was ~0.95 of estimate.
4. **Syllable/second-pass**: after stripping, if cut sits shortly after a high-energy peak with incomplete decay, extend cut to include next short group below ratio but above a floor (e.g. 0.25×) once.
5. Simplest A/B: only strip **one** trailing moan group (not walk multiple), or only strip if peak/ref < 0.9 **and** mean/ref < 0.35 (g4 is weak throughout; “port” may have higher mean than pure moan).

Concrete numbers for g4 (from v112 aligned frames 4.10–4.36): peak/ref ≈ 0.36, dur 0.26s — classic strip. Need a structural signal, not only a ratio nudge. **Lowering ratio alone will not restore “port”** without also keeping the 0.70× moan.

### 2) whisper_stop — broken ref + sub-threshold pad

Trim log:
```
g1: 4.72-4.76s dur=0.04s peak/ref=4.12 -> kept:too-loud
n_real=35 n_bucket=96 audio=4.78s groups=2 stripped=0 cut=4.78s
ref=0.0002 thresh=0.0000
```

**Root cause: head reference collapsed.** `ref ≈ 0.0002` means the keep_min head window was essentially silence (speech starts ~0.38s; ref_min/keep_min can sit in leading near-zeros). With ref≈0:

- thresh≈0 → almost every frame is “speech”
- peak/ref ratios become huge/nonsensical (4.12, 434 on warmup)
- strip logic cannot identify pad bursts
- cut stays at full padded length → user hears pad moan

Post-hoc with a sane ref (p90 over whole clip ≈ 0.114): real final word sits 3.28–3.64s at **0.841×**, then long near-silence with faint pad texture ~4.12–4.24s and a blip ~4.72s. If ref were healthy, last speech group should end ~3.64s and cut ≈ 3.67s — moan would drop without touching “stop” (0.841× is under 0.9 but **duration 0.36s** would be at risk of strip under current rules — ear says “stop” must stay; 0.841××0.36s is exactly Fable’s caveat envelope).

**Repair directions:**
1. **Fix ref**: compute ref from percentile of frames already above a floor, or from the loudest 300–500 ms in the unprotected head, or skip leading silence before ref (first frame ≥ global median / first speech island). Refuse trim when `ref < epsilon` (fail-safe already returns early on ref<=0 but 0.0002 slips through).
2. After ref fix, re-evaluate “stop” at 0.841× / 0.36s — may need **min peak floor to strip** only if also after long gap **and** near bucket end, or keep last group always if peak/ref > 0.5.

Warmup line had the same class of bug: `ref=0.0000` / peak/ref=434.

## Status summary

| Item | Status |
|------|--------|
| peter / full_repro moan | **PASS** (ear) |
| s1 / s4 / fox regression | **PASS** (ear) |
| wallet moan removed | yes, but **passport clipped** — FAIL |
| whisper_stop | **FAIL** moan remains (ref bug) |
| mid-sentence false trim (v1.1.1 class) | still OK on well/swans/fox/full |
| OV lock | unchanged OK |
| WebUI Read Aloud | not re-tested |

## Open for Fable (priority)

1. **Hard fail-safe on ref** — if ref below a real epsilon (e.g. 1e-3 or percentile of non-silent frames empty), skip trim or recompute ref from speech frames only. Fixes whisper_stop class and warmup nonsense ratios.
2. **Wallet “port” group** — structural fix so a soft continuation syllable after a short intra-word dip is not stripped when a stronger sibling group immediately precedes it inside the pad window. Ratio-only retune cannot separate 0.36× “port” tail from 0.70× moan.
3. Re-probe after fix: s2_wallet, whisper_stop, full_repro, peter, fox; ear again.
4. Still open: WebUI multi-POST skips under RTF≫1.

## Artifacts

- `artifacts/v113/*.wav`, `sentence_matrix.json`
- `artifacts/v112/s2_wallet.wav` (complete passport + moan reference)
- `scripts/probe_v113.py`
- `logs/server_v113.log`
- this note

Server left running on `0.0.0.0:8880` (ov-gpu, trim debug on).
