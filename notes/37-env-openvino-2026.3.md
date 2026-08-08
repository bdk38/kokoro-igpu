# notes/37 — Environment upgrade to OpenVINO 2026.3

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Scope:** Ship-path runtime + S0 readiness (not a product claim change)

**Superseded-in-part by notes/38 (dual-track):** ship venv rolled back to 2026.2.1; GenAI removed from ship. **Driver upgrade portion of this note still stands.**


## What changed

| Component | Before | After |
|-----------|--------|--------|
| Project venv `openvino` | 2026.2.1 | **2026.3.0** |
| `openvino-genai` | (not installed) | **2026.3.0.0** |
| `openvino-tokenizers` | (not installed) | **2026.3.0.0** |
| `onnxruntime-openvino` | 1.24.1 | 1.24.1 (unchanged; latest on PyPI) |
| Intel GPU userspace (apt) | 26.22.38646.6 / IGC 2.36.3 | **26.22.38646.7** / IGC **2.36.5** |
| VTune (apt) | 2026.3.0 | 2026.4.0 |

Also updated: `requirements.txt`, `requirements.lock.txt`, and `/data/kokoro-openvino/venv-peek` to the same OV/GenAI pins.

## Smoke (project venv)

- Devices: `CPU`, `GPU` (UHD iGPU)
- Tiny GPU Add model: **PASS**, `EXECUTION_DEVICES=['GPU.0']`
- Patched Kokoro `models/patched/kokoro-v0_19.gpu4d.stft.onnx` compile GPU f32: **PASS** (~12.1s cold compile), `EXECUTION_DEVICES=['GPU.0']`
- ORT providers still include `OpenVINOExecutionProvider`, `CPUExecutionProvider`

## Cache note

Fresh compile cache used: `cache/openvino-2026.3/`.  
Old `cache/openvino/` blobs from 2026.2 may be invalid under 2026.3 blob-compat checks — prefer the versioned dir or clear old caches if compile behaves oddly.

## Product defaults

Unchanged: **ort-cpu** remains product default. This upgrade is stack currency for demo ov-gpu + future S0 GenAI Kokoro probe.
