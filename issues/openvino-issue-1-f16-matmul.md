# [Bug][GPU] FP16 inference fails with "Incompatible MatMul matrix dimension" on Kokoro-82M TTS graph that runs correctly at f32

<!--
DRAFT for github.com/openvinotoolkit/openvino/issues — review before filing.
Fill every [PLACEHOLDER] with fresh output captured on bdk-server.
Suggested labels: bug, category: GPU
-->

### OpenVINO Version

2026.2.1 (pip `openvino==2026.2.1`, build `2026.2.1-21919-ede283a88e3-releases/2026/2`)

### Operating System

Ubuntu 24.04.4 LTS (x86_64)

### Device used for inference

GPU (Intel UHD Graphics, Alder Lake-UP3 GT1, PCI 8086:46b3 rev 0c, Xe-LP, 64 EU)

### Framework

ONNX (opset 17 export of Kokoro-82M v0.19)

### Model used

Kokoro-82M v0.19 ONNX (public: `kokoro-v0_19.onnx`, ~311 MB), with two small
graph patches applied to make it compilable at all on the intel_gpu plugin
(details and patch scripts below — the patches are reproducible from the
public model and are not the subject of this report). The patched model runs
**correctly end-to-end on GPU at f32**; this issue is that the identical
graph fails at f16.

### Issue description

The patched Kokoro graph compiles successfully for GPU with
`INFERENCE_PRECISION_HINT: f16`, but the **first inference** fails with a
MatMul shape-validation error:

```
MatMul_93790: Incompatible MatMul matrix dimension
```

(dimension mismatch reported as 9 vs 1 — full log attached below).

The same graph, same feeds, same device, with only the precision hint
changed to `f32`, compiles and infers correctly: finite output, valid
speech confirmed by listening, `EXECUTION_DEVICES=['GPU.0']`, all-GPU
kernels in per-op profiling, ~95–99% Render/3D engine busy in
`intel_gpu_top` for the full inference window.

Because the graph is precision-agnostic at the ONNX level and executes
correctly at f32, this looks like a bug in the GPU plugin's f16 conversion /
shape handling for this MatMul pattern rather than a model problem.

**Why it matters:** on Xe-LP the optimized convolution kernels are
f16-first. With f16 broken, the graph falls back to
`convolution_gpu_ref__f32` reference kernels and runs at RTF ≈ 2.4–2.9
(slower than realtime) — see companion performance issue [link after
filing]. Fixing f16 is the gate to usable Kokoro TTS performance on
integrated GPUs. Note that Kokoro was explicitly named in the OpenVINO
2025.2 release notes (ISTFT GPU support expansion), so this model appears
to be on the supported-models radar already.

### Step-by-step reproduction

Prereqs: Python 3.12 venv with `openvino==2026.2.1`, `onnx`, `numpy`;
public `kokoro-v0_19.onnx` and `voices-v1.0.bin` (NPZ).

1. Patch the stock model (two rewrites; scripts attached / in repo
   [LINK TO PROJECT REPO]):

   ```bash
   python scripts/patch_kokoro_resize.py \
       --in models/kokoro-v0_19.onnx \
       --out models/patched/kokoro-v0_19.gpu4d.onnx
   python scripts/patch_kokoro_v2.py \
       --in models/patched/kokoro-v0_19.gpu4d.onnx \
       --out models/patched/kokoro-v0_19.gpu4d.stft.onnx
   ```

   Patch 1 rewrites two 3D `linear` Resize nodes in the sine-source
   generator to the equivalent 4D form (Unsqueeze/Resize/Squeeze), because
   the intel_gpu plugin rejects 3D `linear_onnx` Interpolate. Patch 2
   stamps static rank-4 `value_info` on the STFT output. Both patches are
   numerically verified against ORT-CPU (max_abs_diff ~2.4e-7 for the
   resize rewrite on synthetic cases).

2. Working control — f32 (PASSES):

   ```bash
   python scripts/test_kokoro_ov_direct.py \
       --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
       --voices models/voices-v1.0.bin \
       --device GPU --precision f32 --static --runs 2
   ```

3. Failure — f16 (identical except the precision hint):

   ```bash
   python scripts/test_kokoro_ov_direct.py \
       --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
       --voices models/voices-v1.0.bin \
       --device GPU --precision f16 --static --runs 2
   ```

   Compile succeeds; the first `infer_request.infer()` raises the MatMul
   error.

   The test script is a thin wrapper around
   `core.read_model` → `model.reshape` (static `tokens=[1,N]`,
   `style=[1,256]`, `speed=[1]`) → `core.compile_model(model, "GPU",
   {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": <p>})` →
   `create_infer_request().infer(feeds)`.

### Relevant log output

```
[PLACEHOLDER — paste full console output of the f16 run, including the
complete exception text and stack for MatMul_93790]
```

f32 control output for comparison:

```
[PLACEHOLDER — paste f32 run output showing compile OK,
EXECUTION_DEVICES=['GPU.0'], run timings, finite audio stats]
```

### Environment details

- CPU: Intel i3-1215U (Alder Lake, 2P+4E)
- GPU: Intel UHD Graphics 8086:46b3 rev 0c (Xe-LP GT1, 64 EU), kernel driver i915
- intel-opencl-icd 26.22.38646.6 (OpenCL 3.0 NEO), libze-intel-gpu1 26.22.38646.6, IGC 2.36.3
- Kernel: [PLACEHOLDER — `uname -r`]
- Python 3.12, numpy 2.4.6

### Additional context

- The failure is at **inference**, after a successful compile — so the
  validation appears to happen lazily at first execution.
- The reported mismatched dimension (9) is suggestive: Kokoro contains
  small MatMuls with a sequence-derived dimension; a rank/broadcast
  handling difference in the f16 conversion path could plausibly collapse
  or transpose one operand. Happy to run instrumented builds or dump
  intermediate IR if that helps localize it.
- We can share the patched model file directly if that is easier than
  re-running the patch scripts.

### Issue submission checklist

- [x] I'm reporting an issue. It's not a question.
- [x] I checked the problem with the documentation, FAQ, open issues, forum, etc., and have not found a solution.
- [x] There is reproducer code and related data files attached.
