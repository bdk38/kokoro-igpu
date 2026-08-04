# Phase 4f — Real-text harness results (`tts_harness.py`)

**Date:** 2026-08-03  
**Model:** `models/patched/kokoro-v0_19.gpu4d.stft.onnx`  
**Voice:** `af_bella`  
**Tokenizer:** phonemizer/espeak-ng + vendored v0.19 cleanup (kokoro-onnx not installed)  
**Script:** `scripts/tts_harness.py`

## Runs

1. Fox sentence, GPU f32 — `logs/harness_fox_f32.log`, `artifacts/harness/fox_f32/`
2. Fox sentence, GPU f16 — `logs/harness_fox_f16.log`, `artifacts/harness/fox_f16/`
3. Long passage, GPU f32 — `logs/harness_long_f32.log`, `artifacts/harness/long_f32/`

## Tokenization

- Fox: 53 phoneme tokens → feeds `tokens=(1,55)` (pad 0 both ends)
- Long: 195 phoneme tokens → feeds `tokens=(1,197)`
- Phonemes look sane (IPA with stress marks); no vocab drops reported

## Summary tables (from harness)

### Fox / f32

text: "The quick brown fox jumps over the lazy dog."

backend     infer_s  audio_s    RTF   mel_L1       frames
ort-cpu       1.529     3.77  0.405      ref            -
ov-cpu        1.593     3.77  0.422   0.2604     350vs350
ov-gpu       11.453     3.90  2.937   1.6131     362vs350

### Fox / f16

backend     infer_s  audio_s    RTF   mel_L1       frames
ort-cpu       1.674     3.77  0.443      ref            -
ov-cpu        1.530     3.77  0.405   0.2604     350vs350
ov-gpu        FAIL at infer (compile OK)

GPU f16 error after compile on GPU.0:

```
MatMul_93790: Incompatible MatMul matrix dimension.
First input dimension=9 at COL_INDEX_DIM=2 doesn't match
the second input dimension=1 at ROW_INDEX_DIM=0
```

### Long / f32

text: three-sentence passage (~195 tokens)

backend     infer_s  audio_s    RTF   mel_L1       frames
ort-cpu       5.161    12.38  0.417      ref            -
ov-cpu        4.836    12.38  0.391   0.2735   1157vs1157
ov-gpu       31.045    12.72  2.440   1.7704   1189vs1157

## Waveform stats vs ORT-CPU (post-hoc)

### Fox f32
- ort-cpu: n=90600, std=0.072
- ov-cpu:  n=90600, corr=0.9724, max_abs=0.234, len_ratio=1.000
- ov-gpu:  n=93600, corr=-0.055, max_abs=0.879, len_ratio=1.033, finite (no NaNs)

### Long f32
- ort-cpu: n=297000, std=0.094
- ov-cpu:  n=297000, corr=0.9765, max_abs=0.262, len_ratio=1.000
- ov-gpu:  n=305400, corr=-0.019, max_abs=0.955, len_ratio=1.028, finite (no NaNs)

## Interpretation

1. **ORT-CPU** is the solid reference: RTF ~0.40–0.44 on real text (well under 1.0).
2. **OV-CPU** matches length exactly, corr ~0.97, mel_L1 ~0.26–0.27. Slightly better RTF than ORT on the long passage (0.391 vs 0.417). Quality is "same speech-ish" per earlier phase notes; mel_L1 sits in the investigate / soft-regression band of the printed guide, but waveform corr is strong.
3. **OV-GPU f32 is real device execution** (`EXECUTION_DEVICES=['GPU.0']`) but:
   - RTF 2.4–2.9 (several times slower than CPU)
   - Longer audio by ~3%
   - mel_L1 ~1.6–1.8 and waveform corr ~0 — not the same utterance
   - No NaNs this time (unlike some earlier dummy-token GPU runs), but still wrong speech
4. **Longer text did not rescue GPU.** RTF improved only modestly (2.94 → 2.44) and stayed far above 1.0. Launch overhead is not the main story; the GPU path is simply slow and incorrect on this UHD.
5. **GPU f16 is not viable** on this patched graph: compiles, then dies on MatMul shape validation at infer. No optimized-kernel win to measure.
6. **Duration drift** (frames column, ~3% longer on GPU) remains a clear diagnostic of the length/rounding bug class seen in phase 4e (54000 vs 61200 on dummy tokens).

## Packaging decision signal

| Goal | Result |
|------|--------|
| Real-text ORT-CPU RTF < 1 | **PASS** (~0.41) |
| OV-CPU usable parity | **Soft pass** (corr~0.97, RTF≈ORT) — listen before shipping |
| OV-GPU correct speech | **FAIL** (corr≈0, mel_L1>1.5) |
| OV-GPU RTF < 1 | **FAIL** (RTF 2.4–2.9) |
| OV-GPU f16 faster/better | **FAIL** (infer crash) |

**Product path:** ORT-CPU (original or patched model).  
**Optional:** listen-test OV-CPU if an OpenVINO-only runtime is desired.  
**iGPU Kokoro path:** still blocked on correctness + speed; not ready for Phase 5 as a GPU backend.

## Artifacts for ears

- `artifacts/harness/fox_f32/{ort_cpu,ov_cpu,ov_gpu}.wav`
- `artifacts/harness/long_f32/{ort_cpu,ov_cpu,ov_gpu}.wav`
- fox_f16 has ort_cpu + ov_cpu only (gpu failed)

## Prereqs applied this session

- `espeak-ng` via apt
- `phonemizer==3.4.0` in project venv (not kokoro-onnx)

## Listen verdict (human gate) — 2026-08-03

Listener report on harness WAVs:

- **All backends:** natural prosody, realistic pacing, **no audio artifacts**
- **fox_f16 ort-cpu vs ov-cpu:** sound **identical**
- **fox_f32 ov-gpu vs ort-cpu:** same speech; GPU **slightly lower volume**, **faintly muffled**
- **long_f32 ov-gpu vs ort-cpu:** same; GPU **slightly lower volume**, **faintly muffled**

### Metric reconciliation

Raw harness `corr≈0` / `mel_L1>1.5` on GPU **overstated** damage. Cause: ~3% longer GPU waveforms → unaligned frame/sample compare. Not garbage audio.

Post-hoc (time-stretch GPU to ORT length, optional lag):

| pair | rms_delta_dB | corr_trunc | corr_stretch+lag | mel_L1_trunc | mel_L1_stretch | mel_L1_stretch_cen |
|------|-------------:|-----------:|-----------------:|-------------:|---------------:|-------------------:|
| fox ov-cpu | -1.05 | 0.972 | 0.972 (lag 0) | 0.27 | 0.27 | 0.25 |
| fox ov-gpu | **-1.95** | -0.055 | 0.15 (lag +18ms) | 1.64 | 1.20 | 0.64 |
| long ov-cpu | -0.95 | 0.977 | 0.977 (lag 0) | 0.27 | 0.27 | 0.27 |
| long ov-gpu | **-1.75** | -0.019 | 0.12 (lag ~0) | 1.78 | 1.21 | 0.77 |

Aligned numbers match ears:

- GPU **~1.8–2.0 dB quieter** → “slightly lower volume”
- Elevated mel after stretch, still >> ov-cpu → “faintly muffled” (spectral soft loss), not wrong text
- Sample corr stays mediocre after stretch (phase / ISTFT / non-uniform timing); **do not use raw waveform corr as speech-identity gate** when durations differ

### Revised decision framing

| Goal | Revised status |
|------|----------------|
| OV-GPU intelligible correct speech | **PASS (ears)** — mild muffling + lower level |
| OV-GPU artifact-free | **PASS (ears)** |
| OV-GPU level/timbre match ORT | **Soft fail** — ~2 dB down, faintly muffled |
| OV-GPU RTF < 1 on this UHD | **FAIL** (2.4–2.9) — still disqualifies as default |
| OV-CPU listen parity | **PASS** — fox_f16 identical; corr~0.97 |
| Product default | **Still ORT-CPU** (speed + fidelity reference) |
| iGPU as optional path | **Technically alive** for quality; **not** for latency win on Alder Lake UHD |

**Bottom line:** Phase-4 quality blocker on GPU is downgraded from “wrong audio” to “usable but quieter/muffled, and much slower.” Packaging Phase 5 should still default to ORT-CPU unless the goal is specifically to expose a GPU backend for offload demos knowing RTF > 1.
