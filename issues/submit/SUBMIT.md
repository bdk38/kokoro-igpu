# Upstream filings — VERIFY done · **RESEARCH HOLD** (Nexus)

**Date:** 2026-08-08  
**VERIFY:** Grok complete (notes/69) — bodies/attachments still valid  
**Status:** **need research** before submit — Nexus checking openvinotoolkit/openvino for existing issues / upstream acknowledgments to avoid duplicates  
**Do not file until research clears each draft (or marks it as duplicate/superset).**  
**Submit target (when clear):** https://github.com/openvinotoolkit/openvino/issues  

---

## Order (important)

1. **#2 f16 MatMul** first → copy URL  
2. **#3 conv-ref** second → paste #2 URL under Related  
3. **#1 shape-JIT** anytime (independent; can be first or last)

Suggested labels: `bug` + `category: GPU` for #1/#2; `performance` + `category: GPU` for #3.

---

## Files to open

| # | Paste body from | Title line inside file |
|---|-----------------|------------------------|
| 2 | [`02-f16-matmul.github.md`](02-f16-matmul.github.md) | FP16 MatMul dimension fail |
| 3 | [`03-conv-ref.github.md`](03-conv-ref.github.md) | convolution_gpu_ref domination |
| 1 | [`01-shape-jit.github.md`](01-shape-jit.github.md) | shape-keyed JIT 17–30 s |

Each file: copy the fenced **Title** string into the GitHub title field; copy everything under **Body (paste below)** into the issue body.

---

## Attachments (upload per issue)

Directory: `issues/submit/attachments/`

| Issue | Attach |
|-------|--------|
| **#2** | `iss1_f16_fail.log`, `iss1_f32_ok.log`, `filing2_f16_repro_2026.3.json`, `stack_versions.json` |
| **#3** | `iss2_profile.log`, `iss2_gputop.log`, `s0_5_result.json` (contrast), `stack_versions.json` |
| **#1** | `s0_5_result.json`, `i0_3_result.json`, `stack_versions.json` |

Optional: link repo https://github.com/bdk38/kokoro-igpu instead of uploading large WAVs (paths cited in bodies).

---

## VERIFY highlights (already folded into bodies)

| Check | Result |
|-------|--------|
| #1 S0.5 novel Δ | +26.2 s / +23.6 s (direct GenAI) |
| #1 I0.3 served novel Δ | +28.8 s |
| #1 steady RTF | fox 0.70 / multi 0.69 direct; served ~0.73 |
| #2 symptom | **MatMul hard-fail at infer**, not silent audio garbage |
| #2 2026.3 re-repro | **FAIL f16** MatMul_71562 dim 9 vs 1; **OK f32** |
| #2 official pack | **unaffected** (default f16 + ears PASS) — stated explicitly |
| #3 ref kernel share | **~96.2%** of profiled ms = `convolution_gpu_ref__f32` |
| #3 RTF 5.01 | notes/44 soak confirmed |
| Stack | OV 2026.3.0 + drivers 26.22.38646.7 / IGC 2.36.5 |

---

## After you file

Paste the three URLs back into chat (or `issues/submit/FILED_URLS.md`) so we can cross-link and close the filings board item.
