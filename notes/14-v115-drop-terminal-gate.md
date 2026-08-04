# v1.1.5 drop terminal-silence gate — validation

Date: 2026-08-04  
Server: `scripts/kokoro_server.py` **v1.1.5**, ov-gpu f32, `KOKORO_TRIM_DEBUG=1`  
Model: `models/patched/kokoro-v0_19.gpu4d.stft.onnx`  
Log: `logs/server_v115.log`  
Artifacts: `artifacts/v115/`  
Prior: `notes/13-v114-structural-trim.md`, Fable `note_9`

## What changed (v1.1.4 → v1.1.5)

- **Removed** `TRIM_TERMINAL_SIL_S` / long-tail keep branch entirely
- Strip rule is four tests only: weak + short + detached + in-pad-window
- Kept: healthy ref + `TRIM_REF_FLOOR`, detachment gate, debug `tail=` (telemetry only)
- Version **1.1.5**

## Fable predicted vs measured durations

| clip | predicted | measured v115 | match |
|------|-----------|---------------|-------|
| s3_peter | ~3.19 | **3.19** | yes |
| whisper_stop | ~2.67 | **2.67** | yes |
| s2_wallet | 4.39 | **4.39** | yes |
| full_repro | 16.09 | **16.09** | yes |
| fox | 3.21 | **3.21** | yes |
| s1_well | 5.11 | **5.11** | yes |
| s4_swans | 4.13 | **4.13** | yes |

## Duration history (key clips)

| clip | v112 | v113 | v114 | v115 |
|------|------|------|------|------|
| s2_wallet | 5.11 moan | 4.03 clipped | 4.39 PASS | **4.39** |
| s3_peter | 4.01 moan | 3.19 clean | 4.01 moan | **3.19** |
| whisper_stop | — | 4.78 moan | 3.63 moan | **2.67** |
| full_repro | 17.11 | 16.11 | 16.09 | **16.09** |
| fox | 3.07 | 3.07 | 3.21 | **3.21** |

## Trim log highlights

**s3_peter** (was FAIL @ v114):
```
g4: 3.78-3.98s 0.66× gap=0.62 tail=0.82 -> stripped
g3: 3.06-3.16s 1.61× -> kept:too-loud
cut=3.19s stripped=1
```

**whisper_stop** (was FAIL @ v114):
```
g2: 3.28-3.60s 0.66× gap=0.64 tail=1.16 -> stripped
g1: 1.52-2.64s 1.51× -> kept:too-long
cut=2.67s stripped=1
```
No trailing moan group in delivered WAV (only g0/g1).  
**Ear must confirm “stop” is inside g1** (ends ~2.64s). If “stop” is missing, g2 was the word after all → spectral path, use v113 4.78s offline.

**s2_wallet** (must not regress):
```
g5 moan stripped; g4 port kept:attached gap=0.10; cut=4.39s
```

**fox**: outer moan stripped; 0.02s blip kept:attached; cut=3.21s  
**s1 / s4 / full_repro**: moans stripped; cuts unchanged vs v114  
**warmup**: former kept:long-tail 0.63× now stripped (cut 1.07s) — consistent with falsification

## Pre-ear status

| Item | Log status |
|------|------------|
| peter moan stripped | **PASS** (matches v113 clean 3.19s) |
| whisper moan stripped | **PASS** in log; **ear on “stop” required** |
| wallet port + no moan | **PASS** unchanged |
| s1/s4/fox/full_repro | **PASS** in log |
| terminal gate gone | confirmed (no `kept:long-tail` verdicts) |

## Human ear checklist (user)

Primary:
1. `artifacts/v115/s3_peter.wav` — complete, **no** pad moan (compare v113 clean if needed)
2. `artifacts/v115/whisper_stop.wav` — **“stop” audible?** + no pad moan
3. `artifacts/v115/s2_wallet.wav` — full passport, no moan

Regression:
4. s1_well, s4_swans, fox, full_repro

If all seven PASS → **trim thread closes** per Fable note_9.  
Remaining board: WebUI Read Aloud multi-POST under RTF≫1; repo commit; OpenVINO issues; stress-test spec.

## Artifacts

- `artifacts/v115/*.wav`, `sentence_matrix.json`
- `scripts/probe_v115.py`
- `logs/server_v115.log`
- compare refs: `artifacts/v113/s3_peter.wav` (clean), `artifacts/v114/*` (prior fails)
- this note

Server left running on `0.0.0.0:8880` (ov-gpu, trim debug on).

## Human ear verdict (user) — 2026-08-04

**ALL PASS.** Every probe WAV is complete with no pad breath/moan.

- s3_peter — clean (moan gone)
- whisper_stop — **“stop” present**, no moan
- s2_wallet — passport complete, no moan
- s1_well, s4_swans, fox, full_repro — complete, no moan

Fable’s g1-contains-stop interpretation confirmed. Duration predictions all matched measured cuts.

### Trim thread: CLOSED on v1.1.5

Working ruleset (four tests + healthy ref):
- weak: peak/ref < 0.9
- short: dur < 0.6 s
- detached: pre-gap ≥ 0.15 s
- in pad search window
- ref = p90 of loud frames; refuse trim if ref < 1e-3

Removed as falsified: first-quiet cut (v1.1.1), ratio-only multi-strip without detach (v1.1.3), terminal-silence / long-tail keep (v1.1.4).

### Still open (not trim)

1. WebUI Read Aloud multi-POST skips under OV-GPU RTF ≫ 1 (client/playback leg)
2. Repo commit of final server + notes
3. OpenVINO upstream issues (f16 MatMul, f32 ref conv kernels)
4. Stress-test / packaging follow-ups as queued

Server at validation close: v1.1.5 ov-gpu f32 on `:8880` with trim debug on.
