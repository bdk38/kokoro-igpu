# notes/32 — OpenVINO docs + source dive (spike closeout)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Sources:**  
- Knowledge base **OpenVINO docs** (`79949cce-be4b-43f7-8a43-0c20633d8af3`)  
- Clone: `/data/github/openvino` (openvinotoolkit/openvino, sparse: `docs/`, `src/plugins/intel_gpu/`, `src/core/shape_inference/`, `src/frontends/onnx/`)  
- Prior lab: notes/24, 29–31; `spike/out/g3/diagnosis/*`

**Purpose:** Before spike closeout, map **known OpenVINO behavior / limitations** to what we hit — not to reopen gates.

---

## Executive map (our issue → OV reality)

| Our measurement | OV docs/source explanation | Novelty vs “we already knew” |
|-----------------|----------------------------|------------------------------|
| 3D `linear_onnx` Interpolate fail (legacy Kokoro ONNX) | **Exact assert** in GPU plugin | Confirmed **line-level** match |
| ~17–25 s per novel shape (monolith dynamic) | `ImplementationsCache` + async compile only for conv/FC/GEMM/softmax; else sync static build | Confirmed + **async allowlist** |
| CACHE_DIR ≠ all-shapes-warm | Static `kernels_cache` vs dynamic `ImplementationsCache` (process-local, default cap **300**) | Confirmed in-tree docs |
| NCHW rewrite: 98% `convolution_gpu_ref__f32` | Ref kernel is catch-all with priority `DONT_USE_IF_HAVE_SOMETHING_ELSE`; used only when nothing else validates | Explains **why** ref dominated |
| Dynamo full decoder: Conv rank 3 vs 4 on GPU | Core validates `data_rank.compatible(filters_rank)`; GPU has **known “1d can't be handled properly”** pad extension path | Explains **class** of bug; minimal Conv1d still OK |
| e2e RTF ~5 on rewrite | Upstream **open** work on 1D conv perf (PR #37273: osv16 only ~6% peak on some 1D shapes) | Corroborates Xe-class 1D pain |
| O2 one-op repro does not fail | Matches “full graph / ProgramBuilder path,” not single Conv1d | Strengthens full-model filing |

---

## 1. Interpolate / Resize (Contingency A) — **smoking gun in source**

**File:** `src/plugins/intel_gpu/src/plugin/ops/interpolate.cpp`

```cpp
if (interpolateMode == ov::op::v4::Interpolate::InterpolateMode::LINEAR_ONNX) {
    OPENVINO_ASSERT(inputRank == 2 || inputRank == 4 || inputRank == 5,
        "Mode 'linear_onnx' supports only 2D or 4D, 5D tensors");
```

This is **byte-for-byte** the error string from stock Kokoro ONNX / our early phases and from legacy decoder ONNX on GPU.

**Implication:** Not a mysterious Xe-LP quirk. **Documented GPU op restriction.** Our 3D→4D Resize patch and Contingency A are the correct product response. Upstream issue remains valid as a capability gap (1D time interpolate).

Related history: closed PR #12977 optimized **5d** linear_onnx; open #36752 is PTL interpolate test fix — 3D still a second-class citizen.

---

## 2. Dynamic shape JIT / cache (monolith cold) — **first-party docs**

### ImplementationsCache (in-tree GPU docs)

`src/plugins/intel_gpu/docs/dynamic_shape/in_memory_cache.md`:

- Dynamic models rebuild `primitive_impl` + CL kernels per shape → “build the exactly same cl kernel source code multiple times.”
- **`ImplementationsCache`**: LRU, **capacity default 300**, lifecycle = `cldnn::program` (process / compiled network).
- **Only** for dynamic `update_impl` / `update_weights`. Static shapes use **`kernels_cache`** (what CACHE_DIR helps).

### Overall flow

`overall_flow.md` / `async_compilation.md`:

- On shape change: cache lookup → else shape-agnostic dynamic impl if any → else **sync static build**.
- **Async** specialize **only**: convolution, fully-connected, GEMM, softmax. Everything else can hard-stall the infer thread.

**Maps to our lab:**

| Observation | Mechanism |
|-------------|-----------|
| Cold ~17–25 s, wall≈CPU | Sync host JIT on novel internal T |
| Warm transfers only on **same output sample count** | Cache keyed by impl params / shape, not text |
| Eviction after many shapes | LRU capacity 300 (and multi-impls per shape) |
| CACHE_DIR speeds **bucket compile** (~0.9–2.5 s), not novel-T warm forever | Disk static cache ≠ ImplementationsCache |
| Restart loses warm shapes | Process-local impl cache |

KB “OpenVINO docs” contains the same dynamic_shape articles (semantic search hit these heavily).

---

## 3. `convolution_gpu_ref__f32` (G3 NCHW 11 s) — **by design fallback**

**File:** `convolution_kernel_ref.cpp` / `.h`

```cpp
ConvolutionKernel_Ref() : ConvolutionKernelBase("convolution_gpu_ref") {}
// GetSupportedKey: EnableAllInputLayout, EnableAllOutputLayout, all dtypes, dynamic shapes…
KernelsPriority GetKernelsPriority(...) const {
    return DONT_USE_IF_HAVE_SOMETHING_ELSE;  // 1000000.f — last resort
}
```

Preferred weights layout for 4D data: `oiyx` / `goiyx`.

**Meaning:** Ref is the **universal backup**. If layout_optimizer + kernel_selector cannot pick `bfyx_os_iyx_osv16`, `b_fs_yx_fsv16`, etc., every conv falls here.

**Our profile** (`nchw_ov_profile.json`): 62× `convolution_gpu_ref__f32` = **98.2%** of 11.1 s; optimized `convolution_gpu_bfyx_os_iyx_osv16__f32` ≈ **3 ms total**.

**Why NCHW rewrite selected ref:** We forced NC1L / 4D weights via Unsqueeze so ProgramBuilder would accept the graph. That layout is legal enough for **ref** (`EnableAll*Layout`) but fails **Validate()** on fast kernels (or loses the layout_optimizer path that monolith cold-JIT eventually finds).

**Comment in GPU convolution op** (`plugin/ops/convolution.cpp`):

```cpp
// Extend 1d vectors to 2d as 1d can't be handled properly by the graph optimizer for now
if (!op->is_dynamic() && !p.use_new_shape_infer()) {
    strides.resize(std::max<size_t>(2, strides.size()), 1);
    dilations.resize(...);
    pads_begin.resize(...);
    pads_end.resize(...);
}
```

**This is an explicit upstream admission:** 1D conv attributes are a known graph-optimizer weak spot (legacy shape-infer path).

### Upstream 1D perf work (open)

**PR #37273** (open, not merged at fetch time):  
*[GPU] Add implicit GEMM convolution kernel for 1D large-tap small-IC shapes*

- Symptom: 1D conv on selected kernel only **~5.8% of FP32 peak** on PTLH.  
- Root cause: blocked kernels pad IC; osv16 tiles poorly for IC=1 large taps.  
- Fix: specialized 1D GEMM-style kernel (narrow gate).

**Relevance:** Confirms Intel is actively fighting **1D conv efficiency** on GPU — same problem family as our decoder (time-axis convs, often awkward IC/spatial).

---

## 4. Conv rank mismatch (dynamo full decoder) — **core check + GPU path**

**Exact error string** from:

`src/core/shape_inference/include/convolution_shape_inference_util.hpp`:

```cpp
NODE_VALIDATION_CHECK(op,
    data_rank.compatible(filters_rank),
    "Data batch and filters rank do not match (data batch shape: ", data_shape,
    ", filters shape: ", filters_shape, ").");
```

Data ranks **3/4/5** are allowed in principle (`data_shape` check). Failure is **data vs filters rank disagree** (e.g. 3 vs 4).

**Our O2 experiments (note_31):** isolated dynamo Conv1d / weight_norm Conv1d (even 1090→512) **compile on GPU**. Full decoder does not.

**Interpretation after source dive:**

| Layer | Role |
|-------|------|
| Core validation | Enforces equal ranks; error text is generic |
| GPU ProgramBuilder / 1D→2D pad extend | Known fragile for 1D (`1d can't be handled properly…`) |
| Full dynamo graph | Triggers a **GPU-side** promotion/reshape where filters become `[O,I,1,1]` while activations stay `[N,C,L]` |
| Minimal Conv1d | Never hits that bad intermediate |

So O2 remains: **not a one-op exporter bug**, **not “GPU can’t do any 1D”**; filing package = **full dynamo decoder + working minimals as contrast**, primary target **intel_gpu ProgramBuilder / conv lowering**.

Related open issue class: **#36831** — dynamic-shape conv **wrong output** on Gen11 iGPU; static reshape helps. Different symptom, same theme: **GPU conv + non-trivial shapes are a sharp edge**.

---

## 5. CACHE_DIR vs ImplementationsCache (product wording)

| Store | What it holds | Survives process exit? | Our use |
|-------|----------------|------------------------|---------|
| Model / CL disk cache (`CACHE_DIR`) | Static topology compiles, cl blobs | Yes | G3 restart 0.28 s vs 2.5 s cold |
| `ImplementationsCache` | Dynamic per-shape impls | **No** (program lifetime) | Monolith novel-T warm |
| Capacity | Default **300** entries | — | notes/20 eviction story |

Docs are unambiguous: **do not claim CACHE_DIR warms arbitrary Read Aloud**.

---

## 6. f16 MatMul / precision

No strong hit in the small “OpenVINO docs” KB corpus for the exact f16 MatMul shape error. Source tree has extensive f16 conv paths; our f16 MatMul fail remains best filed with the existing one-command repro (issue-1 draft), not newly explained here.

---

## 7. Implications for upstream filings (no spike reopen)

| Draft | How this dive helps |
|-------|---------------------|
| **Shape-JIT / dynamic GPU** | Cite `in_memory_cache.md`, `async_compilation.md` (allowlist conv/FC/GEMM/softmax), capacity 300, static vs dynamic cache split; attach monolith matrices + static-T contrast (no 17–25 s variance at fixed T). |
| **f32 ref conv perf** | Cite `DONT_USE_IF_HAVE_SOMETHING_ELSE`, profile 98% `convolution_gpu_ref__f32`, PR #37273 as “Intel knows 1D conv is weak”; second graph = NCHW decoder. |
| **3D linear_onnx Interpolate** | Cite `interpolate.cpp:37` literally; our Resize rank-lift is the workaround. |
| **Dynamo decoder Conv rank (possible 4th)** | Full `kokoro_decoder_t96_edge_dynamo.onnx` + note_31 minimals contrast; point at GPU ProgramBuilder + 1D pad-extend comment; **do not** claim bare Conv1d is broken. |

---

## 8. Implications for a *future* spike (O1–O4 only if new gate)

1. Prefer exports that stay on layouts optimized kernels accept (**bfyx** planar with spatial dims that match `os_iyx_osv16` / fsv16 gates), not ad-hoc NC1L unsqueeze.  
2. Try `allow_new_shape_infer` / new shape-infer path explicitly when creating GPU programs (avoids legacy “extend 1d to 2d” branch) — **measure**, don’t assume.  
3. Watch PR #37273 and 1D GEMM kernels for Xe-LP.  
4. Full-decoder OV-GPU compile fail is the right repro; keep chasing subgraph isolation only if filing needs a smaller IR.

---

## 9. Closeout statement

Nothing in OpenVINO docs/source **contradicts** the park. Several items **strengthen** it:

- Interpolate-3D and dynamic-shape JIT are **specified behavior**, not lab myths.  
- Ref-conv domination is the **documented last-resort kernel**, matching our 11 s profile.  
- 1D conv is an **acknowledged GPU weak area** (source comment + open perf PR).  
- Dynamo full-model GPU compile failure is real; **minimal Conv1d is not sufficient blame** for exporter-only.

Spike remains **PARKED**. This note is reference fuel for upstream packs and any future gated export attempt.

### Local references

| Path | What |
|------|------|
| `/data/github/openvino` | Sparse clone for citation |
| KB OpenVINO docs | Dynamic shape + GPU plugin articles |
| `notes/24`, `30`, `31` | Prior internals / RCA / O2 |
| `spike/out/g3/diagnosis/` | Profiles + minimal ONNX repros |
