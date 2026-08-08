# notes/68 — Default cutover: ort-cpu → ovgenai-gpu

**Date:** 2026-08-08  
**Authority:** Nexus explicit **`cut over`** after `I0-GO-default-candidate` (notes/67)  
**Author:** Grok (Orchestrator)  
**Status:** **DONE** — product default is **`ovgenai-gpu`**  
**Version:** **v1.4.0** (default bump; I0 integration was 1.3.0)

---

## 1. Decision

| Item | Value |
|------|--------|
| Previous default | `ort-cpu` (v0.19 ONNX) |
| **New default** | **`ovgenai-gpu`** (official int8 GenAI pack) |
| Fallback | `KOKORO_BACKEND=ort-cpu` |
| Voices default | still `af_bella` (pack + continuity) |
| TTS cache code default | still **off** (`0`); **deploy enables `1`** on :8880 |
| ov-gpu | remains **legacy** (notes/66) |

---

## 2. Why now

- I0.1–I0.5 all closed; verdict opened the question  
- Served steady RTF ~**0.73** (notes/62) clears product speed on warmed shapes  
- Founding premise: free CPU on budget iGPU box (Fable notes/63)  
- Counterweights accepted: novel tax, checkpoint/voice timbre change, cache+warm mitigations  

---

## 3. Honest limits (do not bury)

1. **First novel shape** can cost **tens of seconds** (I0.3 +28.8 s class).  
2. Checkpoint is **v1.0-family int8**, not v0.19 — timbre differs (I0.1).  
3. Enable **`KOKORO_TTS_CACHE=1`** and **chunk-shaped `KOKORO_WARM_TEXT`** in real deploys.  
4. Walk-back: set `KOKORO_BACKEND=ort-cpu` (no reinstall required).  

---

## 4. Code / docs

- `scripts/kokoro_server.py`: default `KOKORO_BACKEND=ovgenai-gpu`, version **1.4.0**  
- `README.md`: status + backend table  
- Live `:8880` restarted on new default + cache on + warm pins  

---

## 5. One-line

**Nexus cut over: product default ovgenai-gpu (v1.4.0); ort-cpu one-flag fallback; novel tax + cache/warm honesty retained.**

---

## 6. Superseded-in-part by PoC product face (notes/71)

Nexus dual-product identity (2026-08-08): **repo code default returns to `ort-cpu`** (PoC).  
This note remains the record of the **deploy cutover experiment**; bdk may still run
`KOKORO_BACKEND=ovgenai-gpu` via env/unit. Product B Run block documents that path.
