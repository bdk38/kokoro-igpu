# OpenVINO compile internals brief (mapped to Kokoro iGPU measurements)

**Date:** 2026-08-05  
**Author:** Grok  
**Host OV:** 2026.2.1-21919 (intel-igpu-tts venv)  
**Devices:** CPU (i3-1215U), GPU (UHD iGPU) — both report `EXPORT_IMPORT`  
**Stash:** `/data/kokoro-openvino/openvino/`  
**Companion:** Kokoro source brief in `../notes/fork-decision-brief.md`; measurements notes/18–20

---

## Why this matters

We measured (notes/18–20):

| Observation | Measurement |
|-------------|-------------|
| `compile_model` with CACHE_DIR hit | ~0.9 s |
| First infer novel **output** shape | ~17–25 s wall ≈ process CPU |
| Same shape, different text | warm transfer (~3 s) |
| Many novel shapes then revisit early | cold again (eviction) |
| CACHE_DIR present | ~10G, thousands of `.cl_cache` + `.blob` |

Official + plugin-internal docs now explain this **without speculation**.

---

## Two different “compiles” (do not conflate)

### 1. `core.compile_model()` — model compile

Pipeline:

1. `read_model` (ONNX → `ov::Model`) if from path  
2. Apply properties (hints, cache_dir, precision)  
3. **Plugin transformations** (always run on GPU even when cache hits — docs state this)  
4. Lower to intel_gpu / cldnn topology; kernel_selector planning  
5. If `ov::cache_dir` + EXPORT_IMPORT: load/store **model blob**  
6. Return `CompiledModel` → `create_infer_request()`

**What CACHE_DIR speeds up:** kernel compilation *that is part of model load* for the **static** compiled topology (our static reshape to bucket e.g. `[1,96]`).

**What it does not finish:** every future **runtime shape** the dynamic internals will see when duration/alignment produces a new `T_out`.

Docs (GPU device page): *“all plugin-specific model transformations are executed on each compile_model() call, regardless of cache_dir… since kernel compilation is a bottleneck… significant load time reduction”* — and for dynamic models: *“.blob` + multiple `.cl_cache`”*.

Our disk cache confirms both file types under `/data/intel-igpu-tts/cache/openvino`.

### 2. First infer / shape change — **runtime impl update**

From plugin `overall_flow.md` (`primitive_inst::execute` when dynamic):

```
update_shape()
  → if shape changed:
       update_impl()     # pick or BUILD kernel for this shape
       update_weights()  # reorder weights if layout changed
       realloc if needed
  → execute impl
```

`update_impl()` logic (same doc):

1. Look up **in-memory** `ImplementationsCache` by hash(`kernel_impl_param`)  
2. Else if **shape-agnostic** (`dynamic_impl`) exists → use it **now**  
3. Else **build new static_impl synchronously** and insert into cache  
4. If dynamic_impl was selected **and** primitive is “critical” → also **enqueue async** build of optimal static kernel  

**This is the ~17 s cold path** when step 3 runs (or when shape-agnostic path is slow / ref kernels), dominated by **host CPU OpenCL kernel build**, matching wall ≈ process_time.

---

## In-memory kernel cache (notes/20 eviction explained)

From `in_memory_cache.md` (plugin source docs):

- Class: `ImplementationsCache`  
- Base: **LRU, thread-safe**  
- **Default capacity: 300** (“may change in the future”)  
- Lifetime: tied to `cldnn::program` (one compiled network / process)  
- Shared across multi-stream networks  
- Keys: hash of `kernel_impl_param` (shape + primitive type + layouts…)  
- Stores full `primitive_impl` including **compiled CL kernels + reordered weights**  
- Used only on **dynamic** path (`update_impl` / `update_weights`); static shapes use a different `kernels_cache`

**Maps to measurements:**

- Phase-1 ~70 novel shapes with many primitives each → far more than 300 **impl** entries if each shape×op counts → **LRU eviction** → `revisit_first` cold, `revisit_last` warm  
- Phase-2 few shapes → B hits A’s cached impls → warm  
- Process restart → program destroyed → cache gone (CACHE_DIR does not restore ImplementationsCache contents into LRU for free on first novel shape the same way; disk `.cl_cache` can help OpenCL program rebuild but we still paid multi-second colds)

---

## Async compilation (why some colds are “soft”)

From `async_compilation.md`:

- Motivation: avoid stalling infer on every new shape  
- On miss: run **dynamic/shape-agnostic** kernel immediately; compile **optimal static** kernel in **background thread**  
- **Only four op classes** get prioritized async compile:  
  **convolution, fully-connected, GEMM, softmax**  
- Other ops: not in that priority list  

**Implication for Kokoro:**  
Heavy conv/FC/GEMM may show: first hit uses slower shape-agnostic or ref path (~still multi-second on Xe-LP f32), later hits use optimal cached static.  
If an op has **no** shape-agnostic impl, `overall_flow` says static_impl is built **inline** → hard stall (fits some 17–25 s + cpu≈wall samples).  
Historical profiles mentioning `convolution_gpu_ref__f32` are consistent with “not yet on optimal static kernel” or ref fallback.

---

## Shape-agnostic vs static kernels

From `dynamic_impl.md`:

- Shape-agnostic kernels: `EnableDynamicShapesSupport()`, runtime `shape_info[]` buffer, `update_dispatch_data_func` every exec  
- Static kernels: baked shapes, usually faster  
- Dynamic models often start agnostic, then specialize  

**Kokoro linkage:**  
Token bucket is **static** (`PartialShape [1,96]`) at the **model input**.  
**Internal** time dimension after duration/`repeat_interleave` is still **data-dependent** → treated as dynamic shapes inside the GPU graph.  
Hence: input bucket warm ≠ internal frame-count warm (notes/19–20).

---

## Static reshape vs fully dynamic (our server design)

| Approach | What we do | Effect |
|----------|------------|--------|
| Fully dynamic ONNX | not used on OV path | worst compile/infer specialization |
| `model.reshape` to bucket 96/192/… | server OvBackend | static **input** topology; CACHE_DIR blobs per bucket |
| Internal T from duration | unavoidable in mono graph | runtime dynamic shapes → ImplementationsCache |

Reshape helps **load** and input-side kernels. It does **not** freeze vocoder/length-side shapes.

**Fork implication (notes/22 + Kokoro brief):**  
If decoder is a separate model with **static T** input `[1,C,T_bucket]`, those primitives become **static_impl** at `compile_model` time → cold moves to compile/prewarm of a **small set of T buckets**, not per-utterance. That is the structural fix OpenVINO’s own docs recommend (“prefer static or bounded shapes”).

---

## Properties we actually use

| Property | Our setting | Role |
|----------|-------------|------|
| `CACHE_DIR` / `ov::cache_dir` | `/data/intel-igpu-tts/cache/openvino` | model blob + `.cl_cache` on disk |
| `PERFORMANCE_HINT` | `LATENCY` | single-stream low latency |
| `INFERENCE_PRECISION_HINT` | `f32` (f16 broken MatMul) | precision |
| Static reshape | per PAD_BUCKET | input specialization |

GPU capabilities on this host: `FP32, BIN, FP16, INT8, GPU_USM_MEMORY, EXPORT_IMPORT`.

---

## End-to-end timeline (one ov-gpu speech request)

```
[process start]
  compile_model(bucket=96)
    transformations (always)
    load .blob from CACHE_DIR if hit     → ~0.9 s observed
  create_infer_request

[first text, novel internal T]
  infer()
    for each dynamic primitive with new shape:
      cache miss on ImplementationsCache
      → shape-agnostic exec and/or SYNC static build
      → async enqueue optimal conv/FC/GEMM/softmax
    host CPU ~17–25 s                     → notes/20 cold
  audio out

[second text, same T_out / same impl hashes]
  infer()
    ImplementationsCache hit
    wall ~3 s                             → warm / shape-key

[>~300 distinct impl entries later]
  LRU drops old T’s impls
  early shape cold again                  → phase1 revisit_first
```

---

## What disk cache is and isn’t

**Is:**

- `.blob` — compiled model export for device+topology+config  
- `.cl_cache` — OpenCL program binaries (GPU dynamic caching path)  
- Large on our box (~10G after heavy probing)

**Isn’t:**

- A full persistent replacement for the 300-entry **ImplementationsCache** semantics across arbitrary novel shapes in one process without re-paying something  
- A guarantee that first infer of a never-seen internal shape is free  
- Something MIOpen-style “sweep lengths 1–340 once, forever warm” without our own shape control (notes/21 #454 contrast still valid as **product gap framing**)

---

## Debugging tools (for next probes)

From `gpu_debug_utils.md` + public docs:

- `ov::enable_profiling(true)` → `get_profiling_info()` / `execType` kernel names (`convolution_gpu_ref`, etc.)  
- `benchmark_app -pc`  
- Env: `OV_PROFILE_PASS_ENABLE=1`, `OV_ENABLE_VISUALIZE_TRACING=1` (transformation tracing)  
- Intel compute-runtime OpenCL `cl_cache` FAQ (driver-level, separate from OV cache_dir)

Suggested follow-up measurement (optional):

1. Enable profiling on cold vs warm same-shape infer; list top `execType` by real_time.  
2. Log ImplementationsCache behavior indirectly: time-to-warm for N distinct T, find knee near ~300 **impls** (not 300 utterances).  
3. After cold shape, wait N seconds without infer, re-run — see if async optimal kernel landed (second hit faster than first without being “full warm” yet).

---

## Implications for project decisions

### Ship path (black-box)

- Response cache (notes/21 A/B) bypasses compile/infer entirely on hit — still best ROI.  
- `KOKORO_WARM_*` only pins shapes you actually pre-infer; docs now justify that wording.  
- Do not promise CACHE_DIR alone fixes Read Aloud.

### Fork path (componentized OV)

OpenVINO’s own guidance: **static or bounded shapes**.  
Decoder-only model with fixed `T ∈ {T1,T2,…Tk}`:

- `compile_model` + CACHE_DIR prewarm **per T** once  
- ImplementationsCache pressure collapses (few shapes)  
- Aligns with idea C (pad features to T_bucket, trim audio)

Front-end (duration, align) on CPU avoids putting `repeat_interleave`-driven dynamism on GPU.

### Upstream issue framing (stronger now)

Cite:

1. Model cache ≠ runtime ImplementationsCache (capacity 300, process-local)  
2. Async specialize only conv/FC/GEMM/softmax; other ops may sync-build  
3. Internal dynamic dims behind static inputs still pay per-shape costs  
4. Contrast AMD MIOpen persistent kernel disk cache (#454)  
5. Attach notes/20 matrices + this host OV 2026.2.1  

---

## Primary local files to read

1. `source-refs/dynamic_shape/overall_flow.md`  
2. `source-refs/dynamic_shape/in_memory_cache.md`  ← **capacity 300**  
3. `source-refs/dynamic_shape/async_compilation.md`  
4. `source-refs/dynamic_shape/dynamic_impl.md`  
5. `docs/2025_..._gpu-device.html` (public GPU page)  
6. `docs/2025_..._model-caching-overview.html`

## Key upstream URLs

- https://docs.openvino.ai/2025/openvino-workflow/running-inference/inference-devices-and-modes/gpu-device.html  
- https://docs.openvino.ai/2025/openvino-workflow/running-inference/optimize-inference/optimizing-latency/model-caching-overview.html  
- https://github.com/openvinotoolkit/openvino/tree/master/src/plugins/intel_gpu/docs/dynamic_shape  
- https://github.com/openvinotoolkit/openvino/blob/master/src/plugins/intel_gpu/src/graph/primitive_inst.cpp (update_impl)

---

## Bottom line

OpenVINO GPU does **two-stage** specialization:

1. **Model compile** (helped by CACHE_DIR, static input reshape)  
2. **Per-shape primitive impl cache** (LRU 300, process-local, async optimal for a few op types, sync build otherwise)

Our Kokoro cold/warm/shape-key/eviction story is **textbook intel_gpu dynamic-shape behavior**, not a mysterious Xe-LP bug.  
The durable fixes are: fewer distinct internal shapes (fork + T buckets), or skip compute (audio cache)—not more CACHE_DIR faith.


---
Full stash: `/data/kokoro-openvino/openvino/`
