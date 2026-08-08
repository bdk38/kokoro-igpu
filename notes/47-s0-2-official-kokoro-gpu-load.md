# notes/47 — S0.2 official Kokoro load + one GPU generate

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Gate:** `notes/36` §S0.2  
**Fable pre-run lean:** B1 or B3 (`notes/46`)  
**Status:** **S0.2 PASS**  
**Ship freeze:** held (side venv + `spike/ov263-genai/` only)

---

## 1. Assets

| Item | Value |
|------|--------|
| Repo | **OpenVINO/kokoro-82M-int8-ov** (HF official OV pack) |
| Local | `spike/ov263-genai/out/kokoro-82M-int8-ov/` |
| IR | `openvino_model.xml` + `.bin` (~109 MB bin) |
| Voice | `voices/af_heart.bin` → embedding shape **(510, 1, 256)** |
| Runtime | `venv-s0-ov263` · OV **2026.3.0** · GenAI **2026.3.0.0** |

API (official sample):  
`Text2SpeechPipeline(model_dir, "GPU")` then  
`generate(text, speaker_embedding: ov.Tensor, language="en-us")`.

---

## 2. Results

| Step | Result |
|------|--------|
| Construct pipeline on **GPU** | **PASS** — load **3.33 s** (warm IR cache after first attempt) |
| One `generate` fox-class | **PASS** — wall **22.58 s**, audio **3.25 s**, peak **0.305**, non-silent |
| WAV | `spike/ov263-genai/out/s0_2_gpu_fox.wav` |
| JSON | `spike/ov263-genai/out/s0_2_result.json` |
| Log | `spike/ov263-genai/logs/s0_2_load_generate.log` |

**First generate wall includes cold compile / first-infer cost — not a steady RTF claim** (S0.5 owns that). Informative first-pass RTF ≈ 22.58/3.25 ≈ **6.9** (cold).

---

## 3. Gate bar

| Bar | Result |
|-----|--------|
| Load official Kokoro on GPU without exception | **PASS** |
| One generate completes | **PASS** |
| Known plugin-wall KILL classes | **not observed** at S0.2 |

**S0.2 verdict: PASS**  
**Branch hint:** `B1_or_B3_load_generate_ok` — Fable’s pre-run lean not falsified; S0.3–S0.5 decide offload proof + whether ref-conv floor still owns runtime.

**Fable read-back (notes/48 / `Fable/fable_45_response`):** B2 **falsified at load** (no plugin-wall kill classes). Live speed branches = B1 vs B3 only (S0.5). Pack is **int8** → A2 must record weight + compute precision; S0.4 ears carry quant-noise weight; cross-checkpoint (af_heart / 3.25s vs v0.19 ~3.78s) keeps corr informative-only.

---

## 4. Notes / gotchas

1. Kokoro GenAI requires **explicit** `ov.Tensor` speaker embedding (not voice name string).  
2. First attempt failed only on missing embedding API usage — not a plugin wall; fixed per sample `text2speech.py`.  
3. Ship venv remains 2026.2.1; product server untouched.

---

## 5. Next

**S0.3** — offload proof (`EXECUTION_DEVICES` / kernels / `intel_gpu_top`), not provider name alone.  
Then S0.4 ears, S0.5 cold vs steady RTF (+ A1 novel shape, A2 precision).

---

## 6. One-line

**S0.2 PASS: OpenVINO/kokoro-82M-int8-ov loads on GPU via GenAI Text2SpeechPipeline; fox generate OK (3.25s audio, first-pass wall 22.6s); no Conv-rank kill at load; S0.3 next.**
