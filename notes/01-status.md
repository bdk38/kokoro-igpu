# Intel iGPU TTS — project status

**Date:** 2026-08-03  
**Host:** bdk-server (i3-1215U, UHD 8086:46b3, Xe-LP)  
**Sandbox:** `/data/intel-igpu-tts`

## Goal
Prove whether Kokoro TTS can run with real Intel iGPU offload via OpenVINO, behind an OpenAI-compatible API suitable for Open WebUI. Stop if impossible or too cumbersome to package.

## Phase gates
1. **Hardware recognition** — DRI + OpenCL + Level Zero see iGPU → **PASS**
2. **OpenVINO GPU visibility** — `ov.Core().available_devices` includes `GPU` → **PASS**
3. **OpenVINO GPU smoke** — compile + infer tiny model on GPU → **PASS**
4. **Kokoro ONNX via ORT OpenVINO EP** — session + audio + `intel_gpu_top` busy → **FAIL** (op support)
   - 4b v1.0 FP16/quant variants → **FAIL** same 3D linear Resize (see `notes/03-phase4b-v1-variants.md`)
5. **OpenAI wrapper** — FastAPI `/v1/audio/speech` + voices → not started
6. **Open WebUI wiring** → not started

## Current status (summary)

Infrastructure is good. **Stock Kokoro v0.19 ONNX does not load on OpenVINO EP for GPU** on this host:

- GPU fail: 3D `linear_onnx` Interpolate/Resize unsupported
- OpenVINO CPU/HETERO/AUTO also fail (dynamic-rank STFT / partition issues)
- Plain ORT **CPU** path works (~1.23s / 32 dummy tokens → ~71k audio samples)

Details: `notes/02-phase4-openvino-ep.md`

## How to enter the sandbox
```bash
source /data/intel-igpu-tts/scripts/env.sh
```

## Useful commands
```bash
/data/intel-igpu-tts/scripts/check_hw.sh
python scripts/check_openvino.py
python scripts/smoke_openvino_gpu.py
python scripts/test_kokoro_openvino_ep.py --device GPU --precision FP16
python scripts/test_kokoro_openvino_ep.py --cpu-only
```

## Layout
- `models/` — staged kokoro-v0_19.onnx + voices-v1.0.bin
- `venv/` — OpenVINO + onnxruntime-openvino
- `scripts/` — env, checks, phase4 test
- `logs/` — including phase4 GPU/CPU logs
- `artifacts/` — dummy wav from CPU run
- `notes/` — inventory + phase writeups

## Decision fork (next)
Decision 1 (v1 ONNX A/B) is **done → FAIL**. Pick one:

2. Graph conversion / rewrite research (higher effort)  
3. Pivot to CPU OpenAI wrapper packaging (works, no iGPU)  
4. Pause iGPU path as blocked pending upstream OV op support  

## Constraints (unchanged)
- Alder Lake Xe-LP: no PyTorch XPU  
- oneAPI host install has no OpenVINO component; pip OV in venv is authoritative  
- Provider name alone is never proof — and here GPU EP does not even initialize
