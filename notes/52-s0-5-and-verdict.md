# notes/52 — S0.5 RTF / A1 / A2 + **S0 verdict**

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Gate:** `notes/36` §S0.5 + A1/A2 (`notes/36b`) · Fable methodology `notes/48`/`50`  
**Status:** **S0.5 COMPLETE** · overall **`S0-GO-product`**  
**Prior:** S0.1–S0.4 all PASS  
**Artifacts:** `spike/ov263-genai/out/s0_5/` · `s0_5_result.json` · `logs/s0_5_rtf_a1_a2.log`  
**Comparable:** notes/44 patched ov-gpu fresh long **RTF 5.01**

---

## 1. Methodology (named)

| Item | Method |
|------|--------|
| Runtime | side `venv-s0-ov263` · OV **2026.3.0** · GenAI **2026.3.0.0** |
| Model | `OpenVINO/kokoro-82M-int8-ov` · voice **af_heart** · device **GPU** |
| Steady RTF | discard first run of each shape; mean of subsequent runs |
| A1 | after fox+multi warm; novel text first vs second wall |
| A2 | **unforced** direct compile (no `INFERENCE_PRECISION_HINT`) + pack `openvino_config.json` |
| Product speed clause | steady RTF **≤ 1.0** on fox-class **and** multi-sentence |

---

## 2. Cold vs steady RTF

### Fox-class

| run | wall_s | audio_s | RTF |
|-----|-------:|--------:|----:|
| 0 (warm-up / first) | 14.69 | 3.25 | **4.52** |
| 1–4 mean | ~2.27 | 3.25 | **0.699** |

### Multi-sentence (2 sentences)

| run | wall_s | audio_s | RTF |
|-----|-------:|--------:|----:|
| 0 | 63.03 | 14.30 | **4.41** |
| 1–2 mean | ~9.79 | 14.30 | **0.685** |

**Product speed clause:** fox steady **0.699** ≤ 1.0 **and** multi steady **0.685** ≤ 1.0 → **PASS**.

**vs notes/44 RTF 5.01:** both steady figures **beat** the patched-demo fresh long comparable by ~7×.

---

## 3. A1 — novel shape after warm

| Novel | first wall | second wall | Δ wall |
|-------|----------:|------------:|-------:|
| n1 (swans/boxes) | **30.43 s** | 4.21 s | **+26.2 s** |
| n2 (museum/tea) | **27.26 s** | 3.70 s | **+23.6 s** |

**Interpretation:** `shape_jit_penalty_seconds_class`  
Shape-keyed cold **survives into 2026.3 official IR** (Fable A1 prediction holds). Steady path is fast; **novel traffic still pays multi-second first-infer**. Filing #1 (shape-JIT) **strengthened**, not retired.

---

## 4. A2 — unforced precision (Fable notes/50)

Direct compile **without** precision hint:

```text
EXECUTION_DEVICES: ['GPU.0']
INFERENCE_PRECISION_HINT: float16    # DEFAULT — not forced f32
```

Pack `openvino_config.json`: quantization_config present (int8 pack / optimum default quant).

| Finding | Filing implication |
|---------|-------------------|
| Default compute hint **f16** | Not “GenAI forces f32” |
| Ears PASS (S0.4) on this path | f16 (+ int8 weights) is ear-OK here |
| MatMul f16 bug | **Routed around or non-blocking** on this pack — filing #2 should not claim “still broken for official Kokoro” without a separate repro; may reframe as **our f32 ONNX path** issue / pack-dependent |

---

## 5. Utilization (profile hint)

During multi steady generate: igt RCS **max ~100%**, **mean ~69%** (21 samples).  
Consistent with productive GPU work; not used alone for B1/B3 (RTF decides).

---

## 6. Branch + verdict

| Question | Answer |
|----------|--------|
| B1 vs B3 | **B1_fast_product_interest** on **steady** shapes |
| Demo-only? | No — steady RTF ≤ 1 clears product speed clause |
| Cold/novel? | Still demo-slow first hit (A1) — product integration must plan **shape warm / cache / accept first-hit tax** |

### Overall S0 vocabulary (notes/36)

**`S0-GO-product`**

Meaning (gate text): worth **ship-path design** to integrate or replace ov-gpu demo / discuss default policy later — **not** an automatic cutover. Walk-back ladder (Fable note_27 / notes/38) still applies: cache survives; dual-track; Nexus owns product default.

Combined with S0.1–S0.4 PASS + ears PASS + offload PASS.

---

## 7. Product implications (honest)

1. **Steady official GenAI GPU Kokoro is realtime-class on this Xe-LP** (RTF ~0.7) for **repeat shapes**.  
2. **First novel shape still costs ~25–30 s** — same family of pain as shape-JIT; black-box **TTS cache (v1.2.0)** remains high-value for Read Aloud repeats.  
3. Patched ONNX ov-gpu demo (RTF ~5 fresh) is **dominated** by official path for steady work.  
4. Ship default today remains **ort-cpu** until explicit Nexus cutover design (integration gate separate).  
5. Upstream filings: #1 shape-JIT **still live**; #2 f16 MatMul **reframe** against official int8/f16 path; #3 ref-conv less central if B1 holds without ref domination (optional deeper profile later).

---

## 8. One-line

**S0-GO-product: steady fox/multi RTF ~0.70/0.69 on official int8 GenAI GPU; A1 novel still +24–26 s first hit; unforced A2 default f16; beats notes/44 RTF 5.01; integrate via new ship gate, not silent default flip.**
