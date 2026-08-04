# [Performance][GPU] Kokoro-82M f32 convolutions fall back to `convolution_gpu_ref__f32` on Xe-LP (RTF > 1); plus reproducible f32 GPU fidelity delta vs CPU

<!--
DRAFT for github.com/openvinotoolkit/openvino/issues — review before filing.
Filled from bdk-server captures 2026-08-04. Review before filing.
File issue 1 (f16) first, then put its URL in the companion-link line.
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
https://github.com/bdk38/kokoro-igpu, numerically verified against ORT-CPU). To our
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
(companion f16 MatMul issue (file issue 1 first; paste URL here after filing)).

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
[ov] version: 2026.2.1-21919-ede283a88e3-releases/2026/2
[ov] devices: ['CPU', 'GPU']
[feeds] tokens=(1, 32) style=(1, 256) speed=[1.]
[model] read in 0.35s; inputs:
[model] reshaping to static: {'tokens': '[1,32]', 'style': '[1,256]', 'speed': '[1]'}
[compile] device=GPU config={'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f32', 'PERF_COUNT': 'YES'}
[compile] OK in 2.22s
[compile] execution devices: ['GPU.0']
=== INFER WINDOW START (watch intel_gpu_top now) ===
[run 0] 1.464s
[run 1] 1.448s
=== INFER WINDOW END ===
[timing] mean=1.456s over 2 runs
[OV GPU f32] shape=(54000,) nan=0 inf=0 min=-0.4211 max=0.4886 std=0.0518
      224.507 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/noise_res.1/convs1.2/Conv/Without
      213.165 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/noise_res.1/convs2.0/Conv/Without
      209.970 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/noise_res.1/convs1.1/Conv/Without
      206.613 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/noise_res.1/convs1.0/Conv/Without
      158.395 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.2/convs2.0/Conv/Without
      154.957 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.2/convs1.2/Conv/Without
      153.084 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.2/convs1.1/Conv/Without
      137.301 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.2/convs1.0/Conv/Without
      129.720 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.4/convs1.0/Conv/Without
      129.210 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.4/convs1.2/Conv/Without
      126.211 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.4/convs2.0/Conv/Without
      124.436 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.4/convs1.1/Conv/Without
       85.919 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/noise_res.0/convs1.1/Conv/Without
       85.266 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/noise_res.0/convs2.0/Conv/Without
       84.240 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/noise_res.0/convs1.0/Conv/Without
       82.172 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/noise_res.0/convs1.2/Conv/Without
       63.662 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.3/convs2.0/Conv/Without
       61.649 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.3/convs2.2/Conv/Without
       59.149 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.3/convs1.0/Conv/Without
       58.349 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.3/convs1.2/Conv/Without
       57.708 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.3/convs1.1/Conv/Without
       53.869 ms  TensorIterator       undef                    LSTMSequence_43378
       51.487 ms  TensorIterator       undef                    LSTMSequence_43377
       41.755 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.0/convs1.0/Conv/Without
       40.985 ms  Convolution          convolution_gpu_ref__f32 /decoder/decoder/generator/resblocks.0/convs2.0/Conv/Without
```

Harness summary table (RTF + mel-L1 per backend):

```
[tokenizer] using phonemizer/espeak-ng (vendored cleanup)
[tokenizer] phonemes (53 tokens): ðə kwˈɪk bɹˈaʊn fˈɑːks dʒˈʌmps ˌoʊvɚ ðə lˈeɪzi dˈɑːɡ.
[feeds] tokens=(1, 55) voice=af_bella
----- backend: ort-cpu -----
[ort-cpu] samples=90600 dur=3.77s mean_infer=1.525s RTF=0.404 -> artifacts/harness/ort_cpu.wav
----- backend: ov-cpu -----
[ov-cpu] execution devices: ['CPU']
[ov-cpu] samples=90600 dur=3.77s mean_infer=1.595s RTF=0.422 -> artifacts/harness/ov_cpu.wav
----- backend: ov-gpu -----
[ov-gpu] execution devices: ['GPU.0']
[ov-gpu] samples=93600 dur=3.90s mean_infer=9.108s RTF=2.335 -> artifacts/harness/ov_gpu.wav
===== SUMMARY (reference: ort-cpu) =====
text: 'The quick brown fox jumps over the lazy dog.'
backend     infer_s  audio_s    RTF   mel_L1       frames
ort-cpu       1.525     3.77  0.404      ref            -
ov-cpu        1.595     3.77  0.422   0.2604     350vs350
ov-gpu        9.108     3.90  2.335   1.6131     362vs350
mel_L1 guide: <0.05 near-identical | 0.05-0.15 audible-but-same-speech | >0.3 investigate. Rough metric — ears are the gate.
```

`intel_gpu_top` during the GPU infer window (offload evidence):

```
 Freq MHz      IRQ RC6     Power W             RCS             BCS             VCS            VECS 
 req  act       /s   %   gpu   pkg       %  se  wa       %  se  wa       %  se  wa       %  se  wa 
 268   71       19   0  0.03 18.80  100.00   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1099 1057       51   0  5.97 13.34   93.81   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1099 1072        8   0  6.64 13.62   98.45   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1098 1062        8   0  6.55 13.64   99.24   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1099 1060       38   0  6.09 13.32   92.81   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1099 1070        3   0  6.38 13.19   99.76   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1105 1063       30   0  6.07 13.41   97.88   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1098 1061       27   0  6.42 13.63   97.16   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1098 1077        9   0  6.56 13.55   98.80   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1099 1042      117   0  5.78 13.26   96.14   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1104 1080      432   0  6.76 14.11   90.25   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1099 1039      504   0  6.12 14.62   90.40   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
1099  947       53   0  5.90 14.65   79.75   0   0    0.00   0   0    0.00   0   0    0.00   0   0 
...
# During GPU infer window: RCS (Render/3D) ~90-100% busy, freq ~1040-1100 MHz, gpu power ~5.8-6.8 W
```

### Environment details

- CPU: Intel i3-1215U (Alder Lake, 2P+4E, ~15 W package)
- GPU: Intel UHD Graphics 8086:46b3 rev 0c (Xe-LP GT1, 64 EU), i915;
  observed ~1060–1100 MHz (max clock) at 6–8 W during inference — the
  bottleneck is kernel efficiency, not frequency
- intel-opencl-icd 26.22.38646.6 (OpenCL 3.0 NEO), libze-intel-gpu1 26.22.38646.6, IGC 2.36.3
- Kernel: 7.0.0-28-generic
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
