# FILING DRAFT #2 — for github.com/openvinotoolkit/openvino/issues

**Repo:** openvinotoolkit/openvino · **Component:** GPU plugin (accuracy)
**Prepared:** 2026-08-08 · Fable draft — **reframed per S0 A2 finding** (notes/52 §4)
**[VERIFY] markers = Grok confirms/fills exact evidence before submit. This filing must NOT claim the official pack is affected — it is not.**

---

## Title

`[GPU] f16 inference precision produces corrupted audio output for f32 Kokoro TTS ONNX graph on Xe-LP; f32 hint is a full workaround; official int8 IR pack unaffected (graph-dependent accuracy issue)`

## Body

### Summary

Compiling a community **f32 Kokoro v0.19 ONNX** graph on Intel Xe-LP iGPU with the default GPU inference precision (**f16**) yields numerically corrupted audio output `[VERIFY: exact symptom wording from original repro — garbage/level blowup + which layer class implicated (MatMul)]`. Setting `INFERENCE_PRECISION_HINT=f32` fully restores correct output at significant performance cost (see companion performance issue on `convolution_gpu_ref`).

**Scope honesty:** the official `OpenVINO/kokoro-82M-int8-ov` pack under 2026.3.0 GenAI runs at unforced default **f16** compute with clean output on the same host (verified by property query + listening set). The defect is therefore **graph/export-dependent** — an op pattern in the f32 ONNX export overflows or degrades under f16 — not a blanket Kokoro-on-GPU accuracy failure. We file it because (a) the f32 ONNX export is widely used in the community (kokoro-onnx ecosystem), and (b) a graph-dependent f16 accuracy cliff with no diagnostic is hard for users to attribute.

### Environment

| Item | Value |
|------|-------|
| OpenVINO (repro) | 2026.2.1 `[VERIFY: re-confirm repro on 2026.3.0 f32 ONNX before submit — one session, strengthens or scopes the filing]` |
| Model | community Kokoro v0.19 f32 ONNX (~310 MB) `[VERIFY: exact file/source hash]` |
| Device / driver / OS | Intel UHD Xe-LP 64 EU (i3-1215U) · intel-opencl-icd 26.22.38646.7 · IGC 2.36.5 · kernel 7.0.0-28 · Ubuntu 24.04-class |

### Steps to reproduce

1. Compile the f32 Kokoro ONNX on `GPU` with defaults (f16 execution).
2. Run inference on any short text; write PCM.
3. Recompile with `{"INFERENCE_PRECISION_HINT": "f32"}`; same input.
4. Compare: (2) is corrupted `[VERIFY: attach corrupted vs clean WAV pair + peak/spectrum evidence]`; (4) is correct.

### Expected

Either numerically acceptable f16 execution, or automatic per-layer precision fallback for the offending pattern, or a runtime accuracy diagnostic pointing at the layer class — rather than silent corruption.

### Additional context

- Contrast datum: official int8-weight IR of the same model family executes cleanly at default f16 on identical hardware/driver — useful for narrowing to the specific f32-graph op pattern `[VERIFY: attach unforced-precision property dump from s0_5]`.
- Hardware available for diagnostics on request.

**Attachments:** `[VERIFY: WAV pair, compile logs, repro script, property dumps]`
