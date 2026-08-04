# [Performance][GPU] Kokoro-82M f32 convolutions fall back to `convolution_gpu_ref__f32` on Xe-LP (RTF > 1); plus reproducible f32 GPU fidelity delta vs CPU

<!--
DRAFT for github.com/openvinotoolkit/openvino/issues — review before filing.
Fill every [PLACEHOLDER] with fresh output captured on bdk-server.
Suggested labels: performance, category: GPU
This is the companion to the f16 MatMul bug report — cross-link both after
filing, since fixing f16 is one valid resolution to this performance issue.
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

Kokoro-82M v0.19 ONNX, patched to be GPU-compilable (3D→4D linear Resize
rewrite + STFT output rank annotation; reproducible patch scripts at
[LINK TO PROJECT REPO], numerically verified against ORT-CPU). To our
knowledge this is the first verified real Kokoro inference on this iGPU
class: `EXECUTION_DEVICES=['GPU.0']`, all-GPU kernels in per-op profiling,
95–99% engine busy in `intel_gpu_top`, human-verified natural speech.

### Issue description

Two related observations on the working f32 GPU path. Both are honest
"it runs, but" findings — the model is correct on GPU, just not usable
in production yet.

**1. Performance: reference conv kernels dominate.** Per-op profiling
(`PERF_COUNT`) shows the decoder/vocoder convolutions executing as
`convolution_gpu_ref__f32` — the generic reference kernels — rather than
any optimized path. Measured results on real phonemized text (identical
tokens across backends):

| Backend | RTF (infer_s / audio_s) |
|---|---|
| ORT CPUExecutionProvider (same host CPU) | ~0.40–0.45 |
| OpenVINO CPU plugin, f32 | ~0.39–0.42 |
| **OpenVINO GPU plugin, f32** | **~2.4–2.9** |

Longer inputs do not close the gap (verified up to several hundred
tokens), so this is kernel throughput, not launch overhead. The graph is
dominated by 1D convolutions (as 4D tensors with a singleton spatial dim
after our resize rewrite, plus the model's own conv stack), dilated convs,
and weight-norm patterns. It appears no optimized f32 path matches these
shapes on Xe-LP; the optimized conv kernels seem to be f16-first, and f16
is currently unusable on this graph due to a MatMul validation bug
([LINK TO COMPANION ISSUE]).

Request: either an optimized f32 1D-conv/NCHW-with-H=1 path for Xe-LP, or
(preferably) the f16 fix that would make the intended fast path reachable.

**2. Fidelity: small but reproducible f32 GPU output delta vs CPU.** On
identical feeds, GPU-f32 output vs CPU reference shows:

- ~2 dB lower output level with mild spectral softening (audibly "quieter
  and faintly muffled"; confirmed both by listening and by time-stretch-
  aligned spectral comparison)
- ~3% output duration drift (integer frame-count differences from the
  duration predictor — f32 rounding boundaries flip on GPU kernels)
- No NaN/Inf; output is fully finite and intelligible

The duration drift is understandable numeric behavior for a
round-to-integer duration model, but the consistent level/spectral delta
at f32 (where results are usually expected to track CPU closely) may
point at accumulation-precision differences in the reference conv kernels
and could be a useful correctness canary alongside the perf work.

### Step-by-step reproduction

Prereqs: Python 3.12 venv with `openvino==2026.2.1`, `onnx`, `numpy`
(`onnxruntime` optional for the CPU comparison); public
`kokoro-v0_19.onnx` and `voices-v1.0.bin`.

1. Produce the patched, GPU-compilable model:

   ```bash
   python scripts/patch_kokoro_resize.py \
       --in models/kokoro-v0_19.onnx \
       --out models/patched/kokoro-v0_19.gpu4d.onnx
   python scripts/patch_kokoro_v2.py \
       --in models/patched/kokoro-v0_19.gpu4d.onnx \
       --out models/patched/kokoro-v0_19.gpu4d.stft.onnx
   ```

2. GPU f32 run with profiling and CPU comparison:

   ```bash
   python scripts/test_kokoro_ov_direct.py \
       --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
       --voices models/voices-v1.0.bin \
       --device GPU --precision f32 --static --profile \
       --compare-ort --runs 3
   ```

   The `--profile` output lists per-op `exec_type`; the conv entries show
   `convolution_gpu_ref__f32`.

3. Real-text RTF comparison across backends on identical tokens:

   ```bash
   python scripts/tts_harness.py \
       --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
       --voices models/voices-v1.0.bin \
       --text "The quick brown fox jumps over the lazy dog." \
       --backends ort-cpu,ov-cpu,ov-gpu --gpu-precision f32
   ```

### Relevant log output

Profiling excerpt (top ops by real time):

```
[PLACEHOLDER — paste --profile output showing convolution_gpu_ref__f32
entries dominating the time]
```

Harness summary table (RTF + mel-L1 per backend):

```
[PLACEHOLDER — paste tts_harness.py SUMMARY block]
```

`intel_gpu_top` during the GPU infer window (offload evidence):

```
[PLACEHOLDER — engine busy % and frequency during the run]
```

### Environment details

- CPU: Intel i3-1215U (Alder Lake, 2P+4E, ~15 W package)
- GPU: Intel UHD Graphics 8086:46b3 rev 0c (Xe-LP GT1, 64 EU), i915;
  observed ~1060–1100 MHz (max clock) at 6–8 W during inference — the
  bottleneck is kernel efficiency, not frequency
- intel-opencl-icd 26.22.38646.6 (OpenCL 3.0 NEO), libze-intel-gpu1 26.22.38646.6, IGC 2.36.3
- Kernel: [PLACEHOLDER — `uname -r`]
- Python 3.12, numpy 2.4.6

### Additional context

- Motivation: Kokoro-class TTS on the idle iGPU of small headless servers
  (NUC-class Alder Lake N/U machines) is a real CPU-offload use case. The
  math currently works out to "correct but 6× slower than the same host's
  CPU," entirely attributable to reference kernels.
- Kokoro was named in the OpenVINO 2025.2 release notes (ISTFT GPU
  support), so the model family appears to be tracked already; this
  report covers the remaining gaps after the ISTFT work.
- We can provide the patched model file, WAV pairs demonstrating the
  fidelity delta, and any additional profiling dumps on request.

### Issue submission checklist

- [x] I'm reporting a performance issue. It's not a question.
- [x] I checked the problem with the documentation, FAQ, open issues, forum, etc., and have not found a solution.
- [x] There is reproducer code and related data files attached.
