# v1.1.7 warm-transfer experiment (Fable note_14)

**Date:** 2026-08-04  
**Server:** `scripts/kokoro_server.py` **v1.1.7**  
**Backend:** ov-gpu f32, patched `kokoro-v0_19.gpu4d.stft.onnx`  
**OpenVINO:** 2026.2.1-21919-ede283a88e3-releases/2026/2  
**Log:** `logs/server_v117.log`  
**Artifacts:** `artifacts/v117/`  
**Probe:** `scripts/probe_v117_warm_transfer.py`  
**Author:** Grok (measurement)

## Question (Fable note_14)

After a v1.1.7 near-capacity real-text pre-warm on bucket 96, do first-ever
requests of s1-s4 (novel content, varied lengths, same bucket) run warm
(~2.9 s / RTF ~0.9) or cold (~18 s)?

- All warm -> warm state transfers across content/length; README can claim
  "ov-gpu ~0.9 RTF for varied text once bucket warmed."
- Any cold -> cold is per-content/per-length; claim shrinks; also explains
  the v114 all-requests-slow anomaly.

## Setup

```bash
source scripts/env.sh
export KOKORO_BACKEND=ov-gpu
export KOKORO_MODEL=models/patched/kokoro-v0_19.gpu4d.stft.onnx
export KOKORO_GPU_PRECISION=f32
export KOKORO_WARM_BUCKETS=96
export KOKORO_TRIM_DEBUG=1
python scripts/kokoro_server.py --host 127.0.0.1 --port 8880
```

Startup log:

- openvino=2026.2.1-...
- compiled bucket=96 in 0.9s (cache hit)
- short "Warm up." path OK (n_real=13 -> bucket 96)
- pre-warmed bucket=96 via synthesize in 28.8s (near-capacity real text,
  n_real=88 -> bucket 96)

Then sequential first-ever POSTs: s1_well, s2_wallet, s3_peter, s4_swans, fox.
Follow-up on same process: repeats of known texts + one brand-new sentence.

## Primary matrix (first-ever content after pre-warm)

- s1_well: tokens=71 audio=5.11s infer=24.54s rtf=4.80 COLD
- s2_wallet: tokens=63 audio=4.39s infer=21.79s rtf=4.96 COLD
- s3_peter: tokens=51 audio=3.19s infer=18.92s rtf=5.93 COLD
- s4_swans: tokens=59 audio=4.13s infer=22.17s rtf=5.37 COLD
- fox: tokens=53 audio=3.21s infer=18.56s rtf=5.78 COLD

**5/5 cold.** Near-capacity bucket-96 pre-warm with different real text does
**not** warm first requests of other content in the same bucket.

This is Fable's FAIL branch: warm does not transfer across content.

## Follow-up on same process (repeats + novel)

- s1_well rep2: tokens=71 audio=5.11s infer=16.14s rtf=3.16 MID/COLD (2nd hit, not yet steady-warm)
- fox rep2: tokens=53 audio=3.21s infer=3.08s rtf=0.96 WARM (same text as fox)
- s3_peter rep2: tokens=51 audio=3.19s infer=3.13s rtf=0.98 WARM (same text as s3)
- novel_cats: tokens=52 audio=3.47s infer=23.68s rtf=6.83 COLD (never-seen text, ~fox length)
- fox rep3: tokens=53 audio=3.21s infer=2.98s rtf=0.93 WARM
- s1_well rep3: tokens=71 audio=5.11s infer=3.90s rtf=0.76 WARM (3rd hit finally ~0.9 class)

novel_cats text: "The quiet white cats sleep under the wooden chair."

## Interpretation

1. **Bucket compile is not request warm.** Cache-hit compile (0.9 s) and a 28.8 s
   near-capacity synthesize pre-warm still left every novel s1-s4/fox cold.
   Whatever lazy GPU setup costs ~15-25 s, it is **not** keyed only on
   compiled bucket shape.

2. **Warm is content-specific (or internal-shape-specific).** Evidence:
   - Pre-warm text (88 real tokens) did not help 51-71 token novel sentences.
   - After fox ran cold once, fox rep2/rep3 were warm (~0.93-0.96).
   - After peter ran cold once, peter rep2 was warm (0.98).
   - Brand-new novel_cats (52 tokens, bucket 96) was cold (6.83) after
     many other bucket-96 infers in the same process, including warm repeats.
   - s1 took until rep3 to reach RTF 0.76 (rep2 still 3.16). Warm-up of a
     given content is not always complete on the second hit.

3. **v114 anomaly is no longer mysterious.** Five sequential bucket-96
   requests at 18-25 s each matches tonight: each was first-seen content.
   Notes/18 "unreproducible all-requests-slow" was the content-keyed cold
   path, observed when every probe sentence was novel to that process.
   Tonight's earlier "fox req2/3 warm after fox req1 cold" still holds — that
   was **same content** repeated, not cross-content transfer.

4. **notes/18 follow-up still correct on its own terms:** real-text synthesize
   of ~fox-length content warms *that* content (and zeros / short "Warm up."
   do not). It does **not** generalize to "bucket is warm for all traffic."

5. **Product claim must shrink.** Cannot say: "set KOKORO_WARM_BUCKETS=96 and
   ov-gpu serves varied text at ~0.9 RTF." Can say: "first request of a given
   text (or internal shape) on a bucket is multi-second cold; repeats of the
   same text approach ~0.9 RTF at bucket 96; pre-warm only helps if it matches
   the traffic you care about (demo sentence, not arbitrary Read Aloud)."

6. **OpenVINO issue 2 breadcrumb:** first-infer / lazy setup appears to track
   **data-dependent internal work** (duration predictor frame count, etc.), not
   merely the static [1,96] compiled model. Characterisation for upstream:
   - all-zero pad infer: does not warm real text (prior)
   - short real text (13 tok): does not warm longer real text (prior)
   - near-capacity different real text (88 tok): does not warm other 51-71 tok texts (this note)
   - same text second/third hit: warms to RTF ~0.9
   - new text after many warms: still cold

## Ops impact

- Demo one canned sentence: pre-warm that exact text (curl once at startup); repeats ~0.9 RTF.
- Open WebUI Read Aloud (varied): every new utterance pays cold ~5x RTF on ov-gpu unless content repeats; ort-cpu remains product default.
- KOKORO_WARM_BUCKETS: still eats compile + one cold path for the pre-warm text only; does **not** make the bucket generally warm. Docs must not overclaim.
- Stress / RAPL tests: must state whether load is repeated text (warm) or novel text (cold each time).

## Trim side note

Trim durations on first-pass s1-s4/fox matched the v1.1.5 closed set
(s1 5.11, s2 4.39, s3 3.19, s4 4.13, fox 3.21). No trim regression observed
while measuring RTF.

## Files

- logs/server_v117.log — full process (openvino version, pre-warm 28.8 s, all speech lines)
- artifacts/v117/warm_transfer_matrix.json — primary s1-s4+fox
- artifacts/v117/warm_transfer_repeat_matrix.json — repeats + novel_cats
- artifacts/v117/*.wav — audio for ears if needed
- scripts/probe_v117_warm_transfer.py — primary probe

## Bottom line

**Warm transfer across content: FAIL.**  
**v114 explained: YES (first-seen content each time).**  
**Steady ~0.9 RTF: still real, but per repeated content, not per bucket.**  
**README / WARM_BUCKETS docs: need a correction pass before commit.**

Server left stopped after the run (port 8880 free). Re-start with v1.1.7 when
needed; do not treat KOKORO_WARM_BUCKETS as a varied-traffic accelerator.
