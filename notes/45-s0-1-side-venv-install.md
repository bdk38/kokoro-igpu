# notes/45 — S0.1 side venv install + GPU visible

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Gate:** `notes/36` §S0.1 + `notes/36b` (A3 stack fields)  
**Status:** **S0.1 PASS**  
**Does not:** reopen parked decoder spike; mutate ship venv; touch `scripts/kokoro_server.py` / `models/patched/`

---

## 1. What was run

```bash
python3 -m venv /data/intel-igpu-tts/venv-s0-ov263
venv-s0-ov263/bin/pip install \
  openvino==2026.3.0 \
  openvino-genai==2026.3.0.0 \
  openvino-tokenizers==2026.3.0.0 \
  numpy
```

Tree: `spike/ov263-genai/` (README, `out/`, `scripts/`, `logs/`, lockfile).

---

## 2. Versions (A3)

| Item | Value |
|------|--------|
| openvino | **2026.3.0-22451-8a17657b995-releases/2026/3** |
| openvino-genai | **2026.3.0.0-3277-bd8d6542e3c** |
| openvino-tokenizers | 2026.3.0.0 |
| python | 3.12.3 |
| kernel | 7.0.0-28-generic |
| intel-opencl-icd | 26.22.38646.7-1~24.04~ppa1 |
| libigc2 | 2.36.5-1~24.04 |
| clinfo Driver Version | 26.22.38646.7 |

Artifact: `spike/ov263-genai/out/versions_s0_1.json`  
Lock: `spike/ov263-genai/requirements-s0.lock.txt`

---

## 3. Devices

```text
available_devices: ['CPU', 'GPU']
CPU: 12th Gen Intel(R) Core(TM) i3-1215U
GPU: Intel(R) UHD Graphics (iGPU)
```

**GPU visible: yes.**

---

## 4. Ship freeze / dual-track check

| Check | Result |
|-------|--------|
| Ship venv `/data/intel-igpu-tts/venv` | still **2026.2.1** (verified after install) |
| Ship server on :8880 | unchanged (ort-cpu product path) |
| S0 packages only in | `venv-s0-ov263` |

---

## 5. Gate bar

| Bar | Result |
|-----|--------|
| Import openvino + openvino_genai | **PASS** |
| `available_devices` includes GPU | **PASS** |
| Versions recorded | **PASS** |

**S0.1 verdict: PASS**

---

## 6. Next (hard sequence)

**S0.2** — Obtain/convert official Kokoro assets + `Text2SpeechPipeline(..., "GPU")` one generate.  
Not started. No bar moves.

---

## 7. One-line

**S0.1 PASS: side venv 2026.3.0 + GenAI 2026.3.0.0; GPU=UHD iGPU visible; ship venv remains 2026.2.1; ready for S0.2 model load.**
