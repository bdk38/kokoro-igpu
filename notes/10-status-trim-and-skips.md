# Status checkpoint — pad-tail trim + Open WebUI skips

Date: 2026-08-04  
Server: `scripts/kokoro_server.py` **v1.1.1**  
Backend: `KOKORO_BACKEND=ov-gpu`, model `models/patched/kokoro-v0_19.gpu4d.stft.onnx`, precision `f32`  
Port: `0.0.0.0:8880`

## Team sync

- Fable `note_3`: original pad-tail trim design (v1.1).
- Fable `note_4`: listen test invalidated by sticky Open WebUI voice + cache suspicion.
- Grok merge: production blend/aliases/`extra=ignore` + Fable trim (not a blind replace).
- User confirmed direct A/B WAVs are distinct voices after fixing Admin → Settings → Models sticky blend:
  `bf_isabella(1)+bf_emma(1)+af_heart(3)`.

## Closed: end-of-sentence breath/moan

### Root cause (measured)

OV bucket-padding produces a **secondary voiced burst after a quiet gap**:

```
real speech → short quiet → pad moan/breath → silence
```

ORT-CPU (no pad) ends cleanly.  
Old trim (v1.1) cut after the **last** loud frame → **kept the moan**.

Evidence under `artifacts/trim_probe/`:

| File | Dur | Notes |
|------|-----|-------|
| `ort_cpu.wav` | 3.78 s | clean reference end |
| `ov_no_trim.wav` | 4.73 s | moan present after gap |
| `ov_with_trim.wav` | 4.05 s | old trim; moan retained |
| `v111_fox.wav` | 3.07 s | v1.1.1 server; moan removed |
| `v111_para.wav` | 10.30 s | multi-sentence; moan removed |

### Fix shipped in v1.1.1

`trim_pad_tail()` now prefers the **first sustained quiet** inside the pad search window (gap before secondary burst), with fallback to last-speech-frame behavior.

New knob: `TRIM_QUIET_S = 0.10`.

### Ear acceptance (user)

- Moan **gone** on the probe WAVs.
- **No clipping** of the last word on those files.

## Open: mid-utterance skips in Open WebUI Read Aloud

### Repro text (user)

```
Well, honestly, I think we should wait; however, the choice is yours. Wait, did you remember the keys, the wallet, and the passport? Peter packed a heavy box of bright blue berries. Seven silver swans swam smoothly south across the sea.
```

### Heard skips

1. Stops after `the wallet,` — skips `and the passport?` — resumes at `Peter packed...`
2. Stops after `Seven silver swans` — skips `swam smoothly south across the sea.`

### Server-side evidence for that session

Open WebUI (`172.22.0.3`) did **not** send one full-string request. It sent **multiple** `/v1/audio/speech` POSTs (paragraph/sentence mode), e.g.:

```
[speech] voice=af_bella tokens=71  audio=5.11s ...
[speech] voice=af_bella tokens=63  audio=3.14s ...
[speech] voice=af_bella tokens=111 audio=5.49s ...
[speech] voice=af_bella tokens=113 audio=5.60s ...
```

Earlier in the same process lifetime we also saw:

- `400 Bad Request` (likely empty/invalid voice or empty input during UI churn)
- `500 RuntimeError: Infer Request is busy` when concurrent OV infers shared one request object

### Chunking note (full string on server)

If the **entire** repro text is sent as one `input`, server `chunk_text` yields **one** chunk (~247 tokens). Sentence token counts alone:

- 71 — `Well, honestly... yours.`
- 63 — `Wait, did you remember the keys, the wallet, and the passport?`
- 51 — `Peter packed...`
- 59 — `Seven silver swans...`

So WebUI’s multi-POST pattern is client-side splitting, not our sentence packer merging everything.

### Leading hypothesis for the skips (not yet proven)

**v1.1.1 first-sustained-quiet trim is too eager on natural mid-sentence pauses.**

Comma / list prosody (`keys, the wallet, and the passport`) creates a real quiet gap **inside** speech. If that gap sits inside the pad search window, trim can cut there and drop the rest of the chunk — exactly matching skip (1).

Skip (2) may be the same mechanism, a WebUI playback/concat glitch, or a dropped/failed segment under slow OV RTF (~5–9×).

### Alternate / contributing factors

1. Open WebUI playback while RTF ≫ 1 (segments arrive late; UI may skip or overlap).
2. Concurrent speech requests → `Infer Request is busy` (needs a global OV infer lock or request queue).
3. Residual client cache / partial replay (less likely after new-chat test, but still watch logs).

## What works right now

- OV-GPU path compiles and speaks (patched resize + STFT model).
- Voices and blends resolve; style vectors audibly differ.
- Open WebUI integration path live.
- Pad moan removed on single-chunk / probe material without last-word clip (user ear).

## What does not / not yet

- Production-default speed: OV-GPU f32 RTF still ~4–9 vs ORT-CPU ~0.4 (ref conv kernels; f16 still broken).
- Robust long-form Read Aloud without skips.
- Thread-safe OV infer under concurrent WebUI posts.
- Issue drafts still have placeholders (`issues/openvino-issue-1-f16-matmul.md`, `issues/openvino-issue-2-f32-conv-ref-kernels.md`).

## Next actions (priority)

1. **Prove skip locus with one curl of the full repro text** (single request) vs WebUI multi-request; save WAV and compare to ear.
2. **Harden trim**: only accept a quiet cut if a **secondary burst after the quiet** looks like pad energy (weaker/shorter than main speech). Do not cut on the first quiet alone.
3. **Add OV infer lock** so concurrent posts queue instead of 500 busy.
4. Optional: log per-chunk trim cut seconds + n_real/n_bucket for diagnosis.
5. Fill and file OpenVINO issues when logs are pasted.

## Probe artifacts to keep

- `artifacts/ab_voices/ab_{af_bella,am_michael,bm_george}.wav` — voice distinctness
- `artifacts/trim_probe/ort_cpu.wav`
- `artifacts/trim_probe/ov_no_trim.wav`
- `artifacts/trim_probe/ov_with_trim.wav` (old)
- `artifacts/trim_probe/v111_fox.wav` / `v111_para.wav` (new trim)

## Server process reminder

v1.1.1 was started roughly 2026-08-04 10:52 local with:

```bash
source scripts/env.sh
export KOKORO_BACKEND=ov-gpu
export KOKORO_MODEL=/data/intel-igpu-tts/models/patched/kokoro-v0_19.gpu4d.stft.onnx
export KOKORO_GPU_PRECISION=f32
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

Uncommitted local changes at checkpoint time typically include:

- `scripts/kokoro_server.py` (merge + v1.1.1 trim)
- `Fable/note_3`, `Fable/note_4`
- `issues/*`
- `artifacts/**`
- this note
