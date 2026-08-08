# Fork-decision brief — hexgrad Kokoro technical data

**Date:** 2026-08-05  
**Author:** Grok (research + source read)  
**Stash:** `/data/kokoro-openvino`  
**Question:** Does public technical data support notes/22 (componentized OpenVINO export from source)?

---

## Executive answer

**Yes — the source is modular enough to fork at real seams.**  
Kokoro is not a black-box blob in PyTorch. `KModel.forward_with_tokens` is a readable pipeline with named submodules and an explicit duration→alignment step that is exactly the internal shape driver we measured in notes/20.

**Caveats that matter:**

1. Our shipped path is **v0.19 ONNX**; upstream current is **v1.0 (82M, 8 langs, 54 voices)**. A from-source fork should decide v0.19 parity vs v1.0 upgrade up front.
2. **No public split ONNX exists.** Everyone exports one graph: `input_ids + style + speed → waveform` (and sometimes duration).
3. **Training code is not released** — inference + weights only. Enough for export; not for retrain.
4. License is **Apache-2.0** — commercially and fork friendly.
5. Official export already sets `disable_complex=True` (CustomSTFT) — same class of fix we hit on OV.

---

## What Kokoro is

| Fact | Value | Source |
|------|--------|--------|
| Params | 82M (v1.0) | HF model card |
| Architecture | StyleTTS 2 decoder-only + ISTFTNet | HF + arXiv 2306.07691, 2203.02395 |
| Sample rate | 24 kHz | hardcoded Generator / pipeline |
| Context | Albert max_position_embeddings 512; ~510 phonemes/chunk | config + pipeline |
| Style vector | 256-d: `ref_s[:, :128]` decoder, `ref_s[:, 128:]` predictor | model.py |
| Weights | `kokoro-v1_0.pth` state_dict keys = submodule names | model.py load loop |
| G2P | external `misaki` (+ espeak-ng) — not in the ONNX | HF README |
| Training | ~$1000 / 1000 A100-h; permissive + synthetic data only | HF card |
| Trainer credit | @rzvzn (Discord); arch yl4579 StyleTTS2 | HF card |

v0.19 (what intel-igpu-tts uses): smaller data, 1 lang / 10 voices era; weights under hexgrad/kLegacy. Community ONNX `kokoro-v0_19.onnx` ~311M.

---

## Source module map (the fork gold)

From `/data/kokoro-openvino/github/kokoro/kokoro/model.py`:

```
KModel
  bert            CustomAlbert (PL-BERT, 12-layer, hidden 768)
  bert_encoder    Linear(768 → hidden_dim 512)
  predictor       ProsodyPredictor  (duration + F0/N)
  text_encoder    TextEncoder       (CNN+biLSTM over tokens)
  decoder         Decoder           (Adain stacks + Generator/ISTFTNet)
```

State dict is loaded **per attribute name** (`bert`, `bert_encoder`, `predictor`, `text_encoder`, `decoder`) — weights are already factored for separate modules.

### Forward pipeline (exact order)

```
input_ids, ref_s, speed
  → bert(input_ids) → bert_encoder → d_en
  → predictor.text_encoder(d_en, style_s, ...) → d
  → predictor.lstm → duration_proj → sigmoid → sum/speed
  → pred_dur = round(duration).clamp(min=1)     ##### SHAPE KEY #####
  → alignment via repeat_interleave(pred_dur)   ##### T_out = sum(pred_dur) #####
  → en = d @ alignment
  → F0_pred, N_pred = predictor.F0Ntrain(en, s)
  → t_en = text_encoder(input_ids, ...)
  → asr = t_en @ alignment                      # [hidden, T_out]
  → audio = decoder(asr, F0_pred, N_pred, style_d)
```

**This is the notes/20 mechanism in source form.**  
Output sample count is a deterministic function of `pred_dur` (and decoder upsample/hop). Lattice step 600 samples @ 24 kHz ≈ 2 frames given config:

- `upsample_rates = [10, 6]`, `gen_istft_hop_size = 5`  
- samples/frame ≈ 10×6×5 = **300**  
- gcd 600 = 2 frames — matches phase-1 lattice.

Speed enters only as `duration / speed` before round — explains A@1.05 re-cold.

### Natural component cuts

| Cut | Left (CPU-friendly) | Right (GPU candidate) | Unlocks |
|-----|---------------------|------------------------|---------|
| **A. After duration** | tokens→pred_dur | needs alignment+rest | know T_out before heavy work; can pad T_out to warm lattice |
| **B. After alignment features** | tokens→(asr, F0, N) | decoder(asr,F0,N,s)→wav | **best spike target**: fixed-T feature frames into vocoder |
| **C. After decoder.encode** | …→pre-generator x | Generator/ISTFT only | narrower; still has STFT ops |

**Recommended spike seam = B:** export `Decoder` (or Decoder.generator path) as standalone OV model with inputs:

- `asr`: [1, 512, T]  
- `F0`, `N`: [1, T] (or as produced)  
- `style`: [1, 128]  

and output waveform length = f(T) with **static T buckets** (idea C from notes/21).

Front half (bert→duration→align→asr/F0/N) stays PyTorch or ORT-CPU — dynamic `repeat_interleave` is hostile to GPU shape JIT and cheap on CPU.

---

## Official / community export reality

### hexgrad official (`examples/export.py`)

- Wraps `KModelForONNX` → still **monolithic** forward_with_tokens  
- I/O: `input_ids`, `style`, `speed` → `waveform`, `duration`  
- `disable_complex=True` for ONNX  
- dynamic_axes on token length  
- opset 17  

### adrianlyjak/kokoro-onnx-export (cloned)

- Best documented export + per-node quant trials  
- Notes `conv_post/Conv` must be excluded from aggressive quant (static in audio)  
- Path names like `/decoder/generator/...` confirm decoder is a distinct graph region even in mono export  

### thewh1teagle/kokoro-onnx

- ORT runtime; mentions OpenVINO EP but community reports dynamic-rank failures (same class we hit)  
- No component split  

### Public ONNX I/O (v1.0 community)

- inputs: tokens/input_ids, style[1,256], speed[1]  
- output: audio @ 24 kHz  
- **No published encoder/vocoder split**

---

## Papers (local PDFs)

- `papers/styletts2_2306.07691.pdf` — full StyleTTS2 (prosody predictor, style diffusion in original; Kokoro drops diffusion / is decoder-oriented)  
- `papers/istftnet_2203.02395.pdf` — iSTFT generator (magnitude+phase → inverse STFT)  

Kokoro’s Generator matches ISTFTNet pattern: upsample + NSF harmonic source + `stft.inverse(spec, phase)`.

---

## Implications for notes/22 futures

### Fork is technically justified

- Seams exist in code and in weight keys.  
- Duration is an explicit tensor (`pred_dur`); not buried.  
- Decoder has a clean `forward(asr, F0_curve, N, s)` signature.  
- Apache-2.0.  
- Export recipes and STFT/complex fixes already explored by upstream/community.

### Fork does not auto-win performance

- Shape JIT (notes/20) will still hit **each OV component** that sees novel T.  
- Winning design is almost certainly:  
  **CPU (or ORT-CPU) front-end → fixed-T padded features → OV-GPU decoder buckets → pad-trim**  
  not “five OV models all dynamic.”  
- That is notes/21 idea C enabled by notes/22 seam B.

### Version choice

| Choice | Pros | Cons |
|--------|------|------|
| Stay v0.19 source/weights | Matches current ear baseline & patched ONNX story | Older; less lang/voice; may need to recover v0.19 code/weights from kLegacy |
| Move spike to v1.0 | Current hexgrad source matches weights; better long-term | New parity program vs our v0.19 product path |

**Recommendation:** spike on **v1.0 source + weights** for export mechanics; keep v0.19 intel-igpu-tts as ship path until spike beats it. Do not mix v1.0 decoder with v0.19 front without proof.

### De-risk spike (refined from notes/22)

1. Install hexgrad kokoro + download `kokoro-v1_0.pth` + one voice.  
2. Run `forward_with_tokens` once; dump intermediate `asr, F0, N, pred_dur, audio`.  
3. Call `model.decoder(asr, F0, N, style128)` alone; assert audio match.  
4. `torch.onnx.export` **decoder only** with fixed T (e.g. 100, 150, 200 frames).  
5. OV-GPU compile each T; measure cold/warm wall+cpu (reuse probe_v118 methodology).  
6. Kill if decoder-only cold ≈ full-graph cold with no bucket reuse; go if warm decoder RTF strong and T-buckets transfer across texts with same padded T.

---

## What we did / did not download

**In stash (~360 MB mostly StyleTTS2 clone):** source, cards, config, papers, export tools.  

**Not in stash:** pth weights, ONNX binaries, full voice packs — fetch when spike is approved.

---

## Bottom line for Wayne / Fable

1. **notes/22 fork is not speculative architecture fanfic** — the seams are in `model.py` today.  
2. **The money seam is post-alignment decoder input (asr, F0, N)**, not “re-export the same monolith prettier.”  
3. **Shape control = control pred_dur / T before decoder**, then reuse pad-trim — idea C becomes real.  
4. **Ship path unchanged short-term:** black-box cache A/B + ort-cpu default + documented ov-gpu demo.  
5. **Next technical step if fork greenlit:** decoder-only ONNX→OV spike on v1.0 with fixed-T buckets and notes/20-style cold/warm matrix.

Primary read path: this file + `github/kokoro/kokoro/model.py` + `istftnet.py` Decoder/Generator.


---
Full stash: `/data/kokoro-openvino` (README.md, SOURCES.md).
