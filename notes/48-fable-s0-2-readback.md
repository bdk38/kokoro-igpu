# notes/48 — Fable S0.2 read-back fold

**Date:** 2026-08-07  
**Source:** `Fable/fable_45_response` (S0.2 PASS + raw JSON)  
**Author:** Grok (Orchestrator)  
**Bars:** unchanged (notes/36 + 36b). Guidance for S0.3–S0.5 only.

---

## Architect conclusions accepted

### 1. B2 effectively falsified at load
Official IR **constructed and generated on GPU** with none of the parked-spike kill classes (Conv-rank, 3D interpolate, ProgramBuilder). Intel’s export routes around Xe-LP plugin walls that hit our dynamo decoder / stock ONNX paths.  
**Remaining live branches for speed:** **B1** (fast) vs **B3** (loads but ref-conv-floor slow). Cold wall cannot sort them — **S0.5 decides**.

Existence proof also feeds any future **S3** fork discussion (graph *can* be shaped to compile here), without reopening G0–G3.

### 2. Official pack is **int8** (`kokoro-82M-int8-ov`, ~109 MB)
Implications locked for later bars:

| Topic | Guidance |
|-------|----------|
| **A2 (precision)** | Capture **weight compression (int8)** *and* resolved **inference** precision. int8 MatMul may **sidestep** f16 MatMul bug rather than “fix” it — filing #2 should say **routed around** vs fixed if that holds. |
| **S0.5 speed vs our demo** | If B1 and official is fast, credit may be optimized int8 kernels vs our f32 → `convolution_gpu_ref` — **consistent with filing #3 still valid**, not evidence against it. |
| **S0.4 ears** | Quantization noise is a real possible artifact — Nexus ears are **not** a formality. |

### 3. Cold wall in documented band
First-generate **22.58 s** sits in the **17–25 s** shape-JIT window (2026.2.1-era). One cold-confounded point; **A1** (novel shape after warm steady-state) still owns the JIT verdict. Grok correctly refused RTF claim from cold wall alone.

### 4. Cross-checkpoint caveat active
- Voice **af_heart** = v1.0-family; no v0.19 twin.  
- Fox duration **3.25 s** vs our ~**3.78 s** — different checkpoint/prosody.  
- S0.4: corr vs ort-cpu v0.19 **informative only**; binding = **ears by filename** + duration sanity.  
- Embedding shape **(510, 1, 256)** matches our voice-bin family mechanics.

### 5. Next bars
- **S0.3** — house-rule offload proof; compare to notes/44 fingerprint (RCS ~98–100% under real work).  
- **S0.4** — ears (weighty under int8).  
- **S0.5** — cold vs steady, A1, A2, RTF sorts B1/B3; beat notes/44 **RTF 5.01** for more than repackage.

---

## One-line

**Fable: B2 out at load; B1 vs B3 left for S0.5; int8 pack enriches A2/filings and elevates S0.4 ears; proceed S0.3 with note-44 offload fingerprint.**
