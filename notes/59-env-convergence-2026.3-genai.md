# notes/59 — Ship venv convergence: OpenVINO 2026.3 + GenAI

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Basis:** I0 Option A (Fable note_30 / notes/54–55); Nexus filings waiver notes/58  
**Status:** **COMPLETE** (2026-08-08)  
**Supersedes-in-part:** notes/38 dual-track pin (ship stays on 2026.2.1 forever)

---

## 1. Why

I0.2 requires `openvino_genai.Text2SpeechPipeline` **in the ship process**. One process ⇒ one venv ⇒ ship venv must carry **2026.3 + GenAI**.

Dual-track (notes/38) ends for **runtime pins**. S0 side tree remains as **reference/evidence**, not the product interpreter.

---

## 2. Pre-convergence (recorded)

| Item | Value |
|------|--------|
| Ship venv | `/data/intel-igpu-tts/venv` |
| openvino (before) | **2026.2.1** |
| openvino-genai (before) | **not installed** |
| Live server | ort-cpu :8880 (stopped for upgrade) |
| S0 side venv | `venv-s0-ov263` — 2026.3.0 + GenAI 2026.3.0.0 (unchanged reference) |
| Drivers | 26.22.38646.7 / IGC 2.36.5 (host inventory) |

---

## 3. Target pins

| Package | Pin |
|---------|-----|
| openvino | **2026.3.0** |
| openvino-genai | **2026.3.0.0** |
| openvino-tokenizers | matching 2026.3 line |
| onnxruntime-openvino | keep compatible / reinstall as needed |
| Default backend | still **ort-cpu** |

`requirements.txt` and `requirements.lock.txt` updated to match.

---

## 4. Post-convergence checklist

- [x] openvino **2026.3.0** + genai **2026.3.0.0** in ship `venv`  
- [x] devices `['CPU', 'GPU']`  
- [x] ort-cpu starts; fox×2 byte-identical post-upgrade (notes/60 teaser)  
- [x] GenAI pipeline loads pack on GPU (I0.2 smoke notes/60)  
- [x] `requirements.txt` / `requirements.lock.txt` updated

---

## 5. Walk-back

If ship path breaks hard: restore 2026.2.1 from lock snapshot / reinstall; keep GenAI optional until fixed. Ladder (Fable note_27) still applies for product default — this note only moves the **wheel pin**.

---

## 6. One-line

**Ship venv converges to OV 2026.3 + GenAI under Nexus waiver so I0.2 can run in-process; default remains ort-cpu; dual-track runtime pin ends.**
