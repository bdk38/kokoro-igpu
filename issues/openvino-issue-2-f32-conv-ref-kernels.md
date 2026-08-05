# [Performance][GPU] Kokoro-82M f32 path dominated by `convolution_gpu_ref__f32` on Xe-LP; first-infer cold-start multi-second; small f32 fidelity delta vs CPU

<!--
DRAFT for github.com/openvinotoolkit/openvino/issues — review before filing.
Filled from bdk-server captures 2026-08-04; RTF claims corrected after
warmup/steady-state disambiguation (Fable note_11).
Suggested labels: performance, category: GPU
Companion to the f16 MatMul bug — file that first, paste URL below, then file this.
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

Kokoro-82M v0.19 ONNX, patched to be GPU-compilable (3D->4D linear Resize
rewrite + STFT output rank annotation; reproducible patch scripts at
https://github.com/bdk38/kokoro-igpu, numerically verified against ORT-CPU). Whole-graph GPU execution
is real: `EXECUTION_DEVICES=['GPU.0']`, GPU kernels in per-op profiling,
~90–100% RCS busy in `intel_gpu_top`, human-verified natural speech.

### Issue description

Three related observations on the **working f32 GPU path**. The model is
correct on GPU; these are throughput / cold-start / fidelity findings.

**1. Performance: reference conv kernels dominate steady-state time.**
Per-op profiling (`PERF_COUNT`) shows decoder/vocoder convolutions
executing as `convolution_gpu_ref__f32` rather than an optimized path.
That matches the f16-first kernel story: f16 is currently unusable on this
graph due to a MatMul validation bug (companion f16 MatMul issue — paste
URL after filing).

**Steady-state vs cold-start (important methodology note).**
`scripts/test_kokoro_ov_direct.py` discards 1 warmup infer, then averages
timed runs. `scripts/tts_harness.py` averages **all** runs including the
first, so a 2-run harness mean is roughly `(cold + steady) / 2` and can
report RTF > 1 even when steady-state is sub-realtime. Numbers below use
the direct-test protocol unless noted.

| Backend / case | Protocol | RTF |
|---|---|---|
| ORT CPU (fox harness, runs=4 mean) | includes all runs | ~0.45 |
| OV CPU f32 (direct, n=53, warmup discarded) | steady | ~0.39 |
| **OV GPU f32 steady** (direct, n=32/53/250) | warmup discarded | **~0.60–0.62** |
| OV GPU f32 **cold** first infer after compile | warmup only | **~4.2–5.4** |
| OV GPU fox harness runs=2 mean (no warmup discard) | mixed | 2.34 (inflated) |
| OV GPU fox harness runs=4 mean (no warmup discard) | mixed | 1.46 (still inflated) |

So: **steady-state GPU is faster than realtime (~0.60 RTF)** but still
about **1.5x slower than ORT-CPU (~0.40)** on this host. The large
RTF >> 1 numbers in interactive use are dominated by **first-infer
cold-start** (and new shape/bucket compiles), not by steady kernel
throughput alone. Longer shapes do not make steady RTF worse (slightly
better ms/token at n=250). Request: optimized f32 1D-conv / NCHW-H=1 path
on Xe-LP, and/or the f16 fix that unlocks the intended fast kernels;
also any reduction of first-infer setup cost would help TTS servers.

**2. Fidelity: small but reproducible f32 GPU output delta vs CPU.** On
identical feeds, GPU-f32 vs CPU shows:

- ~2 dB lower output level with mild spectral softening (audibly quieter
  and faintly muffled; confirmed by listening)
- ~3% output duration drift (integer frame-count differences from the
  duration predictor — e.g. harness frames 362 vs 350 on fox)
- No NaN/Inf; output is fully finite and intelligible

**mel_L1 caveat:** harness `mel_L1` on fox was **1.61** with
`frames 362vs350`. That metric is **unaligned** (truncated to shorter
length only — see harness docstring). It is **not** a claim of large
spectral error independent of the duration drift. The fidelity claim we
stand behind is the listen result plus ~2 dB / mild softening after
accounting for drift — not the raw unaligned mel_L1 number.

**3. Offload is real.** Profiling and `intel_gpu_top` show the work is on
the iGPU (not a CPU fallback labeled as GPU).

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

2. GPU f32 with profiling (ref-conv evidence) + steady timing:

```bash
python scripts/test_kokoro_ov_direct.py \
    --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
    --voices models/voices-v1.0.bin \
    --device GPU --precision f32 --static --profile \
    --warmup 1 --runs 3
```

3. Steady-state vs length (warmup discarded):

```bash
for N in 32 53 250; do
  python scripts/test_kokoro_ov_direct.py \
    --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
    --voices models/voices-v1.0.bin \
    --device GPU --precision f32 --static --tokens $N \
    --warmup 1 --runs 3
done
```

4. Optional: harness on real text (note: means include cold first run
   unless you discard run 0 externally):

```bash
python scripts/tts_harness.py \
    --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
    --voices models/voices-v1.0.bin \
    --text "The quick brown fox jumps over the lazy dog." \
    --backends ort-cpu,ov-cpu,ov-gpu --gpu-precision f32 --runs 4
```

### Relevant log output

Profiling excerpt (top ops by real time — all `convolution_gpu_ref__f32`):

```
[ov] version: 2026.2.1-21919-ede283a88e3-releases/2026/2
[ov] devices: ['CPU', 'GPU']
[feeds] tokens=(1, 32) style=(1, 256) speed=[1.]
[model] read in 0.35s; inputs:
[model] reshaping to static: {'tokens': '[1,32]', 'style': '[1,256]', 'speed': '[1]'}
[compile] device=GPU config={'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f32', 'PERF_COUNT': 'YES'}
[compile] OK in 2.22s
[compile] execution devices: ['GPU.0']
[warmup 0] 9.264s
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

Steady-state / cold-start RTF table (direct test, 2026-08-04):

```
# Steady-state = mean of timed runs AFTER 1 discarded warmup (test_kokoro_ov_direct.py)
# Cold = that first warmup infer (lazy GPU kernel setup for the shape)
# Random-token feeds; audio length is model-determined (samples/24000).

tokens  cold_s  steady_s  audio_s  RTF_cold  RTF_steady  ms/tok_steady
    32   9.382     1.371     2.25      4.17        0.609         42.8
    53  16.728     1.917     3.08      5.44        0.624         36.2
   250  52.969     7.539    12.58      4.21        0.600         30.2

# OV-CPU control, same script, tokens=53, warmup discarded:
#   steady mean=1.355s  samples=83400 audio=3.48s  RTF_steady=0.390
# (token content is random so audio length differs from GPU row; RTF is the fair metric)

# Same-day fox harness (real text, 55 tok ids) WITHOUT warmup discard — inflates GPU:
#   --runs 2: ov-gpu mean_infer=9.108s RTF=2.335  (approx (cold+steady)/2)
#   --runs 4: ov-gpu mean_infer=5.700s RTF=1.462  (approx (cold+3*steady)/4)
#   ort-cpu runs4 mean RTF=0.445; ov-cpu runs4 mean RTF=0.407
# Conclusion: headline RTF>1 in early notes mixed cold-start into the mean.
# Steady-state GPU is sub-realtime (~0.60) but still ~1.5x slower than ORT-CPU (~0.40).
```

`intel_gpu_top` during a GPU infer window (offload evidence):

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
# RCS (Render/3D) ~90-100% busy during infer, freq ~1040-1100 MHz, gpu power ~5.8-6.8 W
```

### Environment details

- CPU: Intel i3-1215U (Alder Lake, 2P+4E, ~15 W package)
- GPU: Intel UHD Graphics 8086:46b3 rev 0c (Xe-LP GT1, 64 EU), i915;
  observed ~1040–1100 MHz at ~6–8 W GPU power during inference
- intel-opencl-icd 26.22.38646.6 (OpenCL 3.0 NEO), libze-intel-gpu1 26.22.38646.6, IGC 2.36.3
- Kernel: 7.0.0-28-generic
- Python 3.12, numpy 2.4.6
- Project / repro: https://github.com/bdk38/kokoro-igpu
- Raw captures: `https://github.com/bdk38/kokoro-igpu/tree/main/issues/captures`

### Additional context

- Motivation: Kokoro-class TTS on the idle iGPU of small headless
  servers (NUC-class Alder Lake N/U) is a real CPU-offload use case.
  Steady-state already beats realtime; closing the remaining ~1.5x gap
  vs host CPU (and especially first-infer latency) would make the path
  production-interesting.
- Kokoro was named in the OpenVINO 2025.2 release notes (ISTFT GPU
  support); this report covers remaining gaps after that work.
- We can provide the patched model file, WAV pairs for the fidelity
  delta, and additional profiling dumps on request.

### Issue submission checklist

- [x] I'm reporting a performance issue. It's not a question.
- [x] I checked the problem with the documentation, FAQ, open issues, forum, etc., and have not found a solution.
- [x] There is reproducer code and related data files attached.
