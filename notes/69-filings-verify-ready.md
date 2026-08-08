# notes/69 — Filings VERIFY complete (submission pack ready)

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Status:** **VERIFY done · PARKED** — bodies in `issues/submit/`  
**Nexus (2026-08-08):** park until duplicate/prior-art research can be completed. Pack stays frozen and placeholder-free; **do not submit** while parked (notes/76).

---

## 1. Pack layout

```text
issues/submit/
  SUBMIT.md                 ← how to file (order + attachments)
  01-shape-jit.github.md
  02-f16-matmul.github.md
  03-conv-ref.github.md
  attachments/
    s0_5_result.json
    i0_3_result.json
    iss1_f16_fail.log
    iss1_f32_ok.log
    iss2_profile.log
    iss2_gputop.log
    filing2_f16_repro_2026.3.json
    stack_versions.json
```

Draft sources (pre-VERIFY): `issues/filing-1..3.md` — superseded for paste by `submit/*.github.md`.

---

## 2. VERIFY table

| Marker / claim | Status | Evidence |
|----------------|--------|----------|
| #1 timing table S0.5 | **OK** | `s0_5_result.json` fox steady 0.699, multi 0.685, novel Δ 26.2 / 23.6 s |
| #1 served novel tax | **OK added** | I0.3 +28.8 s (`i0_3_result.json`) |
| #1 stack / drivers | **OK** | inventory + stack_versions.json |
| #2 symptom wording | **CORRECTED** | Hard fail MatMul shape validation — **not** “corrupted WAV” |
| #2 2026.3 re-repro | **PASS (bug still live)** | f16 FAIL MatMul_71562; f32 OK peak 0.50 |
| #2 official pack scope | **OK** | Explicitly unaffected (A2 f16 default + S0.4 ears) |
| #2 model hashes | **OK** | stock + patched SHA256 in body |
| #3 ref % | **OK** | 96.2% of profiled ms = convolution_gpu_ref__f32 |
| #3 RTF 5.01 | **OK** | notes/44 |
| #3 contrast RTF 0.7 | **OK** | s0_5 / i0_3 |
| No empty `[VERIFY]` in submit bodies | **OK** | stripped / filled |

---

## 3. Filing order for Nexus

1. **02 f16 MatMul**  
2. **03 conv-ref** (link #2)  
3. **01 shape-JIT** (independent)

---

## 4. One-line

**Three issues VERIFY-clean in issues/submit/; PARKED until Nexus finishes duplicate/prior-art research (notes/76).**

---

## 5. Research hold → PARKED (2026-08-08 Nexus)

Originally: RESEARCH HOLD while Nexus searches upstream.  
**Now:** explicitly **PARKED** — not on the active board; resume only when Nexus opens research completion + per-draft file/comment/drop.

Search targets when unparked (`openvinotoolkit/openvino` and related):

- existing shape-JIT / first-infer / CACHE_DIR kernel-cache issues on GPU  
- f16 MatMul dimension / precision issues on TTS or similar graphs  
- convolution_gpu_ref / missing optimized f32 conv on Xe-LP  

**Per draft outcomes (fill when research done):**

| Draft | Research result | Action |
|-------|-----------------|--------|
| #1 shape-JIT | _parked / pending research_ | file / comment on existing / drop |
| #2 f16 MatMul | _parked / pending research_ | file / comment on existing / drop |
| #3 conv-ref | _parked / pending research_ | file / comment on existing / drop |

Grok does not submit while this table is pending.
