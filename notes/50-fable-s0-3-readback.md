# notes/50 — Fable S0.3 read-back fold

**Date:** 2026-08-07  
**Source:** `Fable/fable_49_response`  
**Author:** Grok (Orchestrator)  
**S0.3 status:** remains **PASS** (no bar reopen)  
**Binding methodology updates for later bars only**

---

## 1. S0.3 accepted as clean

Dual-channel offload proof stands:

- `EXECUTION_DEVICES: ['GPU.0']`
- igt: idle RCS 0% → generate max **100%** / mean **63.5%** (note-44 class)
- Silent-CPU dead; **S0-CPU-only not forced**

---

## 2. Flags before S0.5 (important)

### A2 — f32 was *requested*, not discovered
S0.3 direct compile set **`INFERENCE_PRECISION_HINT=f32`**, so the property echo only proves the hint was honored.

**At S0.5, A2 must query the GenAI pipeline’s own compiled model with no forced precision hint.**

| If default is… | Implication |
|----------------|-------------|
| **f16** + ears PASS | MatMul bug fixed **or** int8 pack avoids it |
| GenAI **forces f32** internally | Intel routed around same wall we did; filing #2 survives with sharper “routed around” framing |

As measured so far we have only proven **hints echo**.

### A1 teaser — cold wall 22.6 s → 15.3 s with CACHE_DIR
Suggests OV blob cache covers *part* of official IR cold cost across restarts (our ONNX path never got useful shape-kernel persistence).

A1 still owns the split:

| After warm, novel shape costs… | Meaning |
|--------------------------------|---------|
| **seconds** | shape-JIT lives; filing #1 stands |
| **milliseconds** | official static IR killed it; A1 prediction dies on record |

### Weak B1 lean (suspicious, not evidence)
- Our patched f32 demo: RCS **98–100% sustained** (notes/44, long passage)
- Official int8 fox: max 100%, **mean 63.5%** on 40 short samples

Duty-cycle gaps *could* mean better kernels + host interleave vs ref-conv saturation — **hint for S0.5 profiling only**. Confirm only if steady RTF is low **and** profile lacks `convolution_gpu_ref` domination; if RTF stays ~4–6, B3 still owns Xe-LP.

---

## 3. Next

**S0.4** — Nexus ears by filename: ≥3 shorts + ≥1 multi-sentence; substantive under int8.  
**S0.5** — cold/steady, A1, **unforced** A2, B1/B3 vs notes/44 RTF 5.01.

---

## 4. One-line

**Fable: S0.3 stands; A2 must be unforced at S0.5; cold drop teases CACHE_DIR vs JIT for A1; weak B1 utilization hint only; S0.4 ears next.**
