# Contributor: Claude (Anthropic)

**Role:** Analysis, diagnosis, graph surgery, and tooling
**Model:** Claude Fable 5 (Anthropic), via claude.ai
**Collaboration model:** Human project lead directed the investigation and made
all decisions; Claude performed diagnosis and wrote the code; Grok 4.5 (xAI,
via Open WebUI) executed tests on the target hardware and authored the phase
reports. All results were verified on the actual machine — nothing here is
claimed from simulation.

---

## Summary of the problem

Kokoro TTS (v0.19 and v1.0 ONNX exports) could not run on Intel integrated
GPUs through OpenVINO. Every stock export failed at `InferenceSession` /
`compile_model` time on the same error, on OpenVINO 2026.2.1 + intel_gpu
plugin, Alder Lake UHD (8086:46b3, Xe-LP):

```
Mode 'linear_onnx' supports only 2D or 4D, 5D tensors
```

A secondary blocker appeared once partitioning was involved: the STFT output
tensor carried **dynamic rank**, which every OpenVINO plugin (GPU and CPU)
rejects at subgraph/Parameter boundaries. A commercial Docker image claiming
"Intel iGPU accelerated" Kokoro was tested by this project and shown to be
CPU execution behind a GPU provider label.

## What I contributed

### Diagnosis

- Identified the two architectural blockers as separable: (1) two 3D
  `linear`-mode Resize nodes in the sine-source generator
  (`m_source/l_sin_gen`), and (2) missing rank annotation on the STFT output
  creating dynamic-rank partition Parameters.
- Established that the Resize blocker is *rank-representational*, not
  mathematical: a 4D linear resize with an inserted singleton H axis is
  numerically equivalent to the original 1D interpolation.
- Established that the STFT blocker is *annotational*, not architectural:
  ONNX STFT output rank is statically known (4: `[batch, frames, bins, 2]`)
  even when its dims are dynamic; OpenVINO rejects dynamic rank, not dynamic
  dims.
- Correctly predicted the "whack-a-mole" failure sequence (Resize fix →
  STFT wall) and the FP16-overflow risk class; incorrectly predicted the
  v1 parity delta was stochastic (the determinism probe I wrote disproved
  my own hypothesis — the delta is real, small, and traced to coordinate
  handling in the 300:1 resample).
- Diagnosed the "corr ≈ 0" GPU quality scare as metric failure
  (duration-rounding drift → time misalignment), later confirmed by human
  listening and by Grok's stretch-aligned reconciliation.

### Code (all verified by smoke test before delivery, then validated on
target hardware by Grok)

| Script | Purpose |
|---|---|
| `scripts/patch_kokoro_resize.py` | v1 surgery: symbolic shape inference + 3D→4D linear Resize rewrite (Unsqueeze/Resize/Squeeze, constant & dynamic scales/sizes), CPU parity check |
| `scripts/patch_kokoro_v2.py` | v2 surgery: adds STFT rank-4 value_info stamping with clobber guard, determinism probe |
| `scripts/test_kokoro_ov_direct.py` | Direct `ov.Core` whole-graph compile/run (bypasses ORT EP partitioning), static reshape, per-op profiling, ORT comparison |
| `scripts/tts_harness.py` | Real-text A/B harness: espeak-ng phonemization with vendored v0.19 tokenizer, multi-backend runs on identical tokens, RTF + mel-L1 reporting |
| `scripts/kokoro_server.py` | Phase 5 product: OpenAI-compatible `/v1/audio/speech` FastAPI server, ORT-CPU default, OV-CPU/OV-GPU backend flags, sentence chunking, voice aliases, per-request RTF headers |

## Results (as measured on bdk-server, i3-1215U / UHD 46b3)

- **Compile blockers removed.** The patched model
  (`kokoro-v0_19.gpu4d.stft.onnx`) creates sessions on OpenVINO GPU, CPU,
  HETERO, and AUTO — previously impossible on any stock export.
- **First verified real Kokoro inference on this iGPU class.**
  `EXECUTION_DEVICES=['GPU.0']`, all-GPU kernels in per-op profiling, RCS
  95–99% for the full inference window, and human-verified natural,
  artifact-free speech.
- **Product path shipped.** ORT-CPU at RTF ≈ 0.40–0.45 on real text behind
  an OpenAI-compatible API, wired for Open WebUI.
- **Honest limits documented.** GPU path is correct but not competitive:
  RTF 2.4–2.9 (ref-quality f32 conv kernels), output ~2 dB quieter and
  faintly muffled vs CPU reference, ~3% duration drift from rounding, and
  FP16 — where the optimized kernels live — fails at infer with a MatMul
  shape-validation error.

## Open issues (upstream candidates, OpenVINO repo)

1. **FP16 MatMul compile/validation bug** — patched graph compiles for GPU
   at f16 then fails at first infer:
   `MatMul_93790: Incompatible MatMul matrix dimension` (dim 9 vs 1). Same
   graph runs at f32. One-command repro exists.
2. **f32 convolution falls to `convolution_gpu_ref__f32`** on Xe-LP for
   this graph — no optimized f32 1D-conv path; dominates the RTF > 1 result.
3. **GPU fidelity delta** — ~2 dB level drop + spectral softening vs CPU on
   identical inputs; finite (no NaN), reproducible.
4. (Fixed by this project's surgery, but the underlying limitations remain
   upstream: 3D `linear_onnx` Interpolate unsupported on intel_gpu;
   dynamic-rank Parameters rejected at partition boundaries.)

## Lessons worth keeping

- **Provider names are never offload proof.** Require engine counters
  (`intel_gpu_top`), `EXECUTION_DEVICES`, or per-op kernel types.
- **Raw waveform correlation is not a speech-identity metric** when
  durations can differ; duration-rounding drift drives corr to ~0 on
  audio human ears judge as the same speech. Align first, or use
  spectral metrics, and keep ears as the gate.
- **"Unsupported op" walls are often narrower than they look.** Two small,
  principled graph edits (a rank lift and a rank annotation) took this
  model from "cannot compile anywhere" to "runs whole-graph on GPU."
- **Test the metric before trusting the failure.** Twice in this project a
  "quality FAIL" was a measurement artifact.

## Acknowledgments

The project lead's insistence on hard offload proof (engine counters over
provider labels) — established before I joined the effort — set the
evidentiary standard that kept every result in this repo honest. Grok 4.5
ran all hardware validation and wrote the phase reports; the stretch-aligned
metric reconciliation in Phase 4f is Grok's work.

---

*This document was written by Claude. Errors in prediction noted above are
left in deliberately: the record of what was guessed wrong is part of an
honest research log.*
