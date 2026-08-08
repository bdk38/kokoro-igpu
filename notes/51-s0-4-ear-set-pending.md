# notes/51 — S0.4 ears (CLOSED PASS)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Gate:** `notes/36` §S0.4 · Fable int8 weight (`notes/48`, `notes/50`)  
**Status:** **S0.4 PASS** — Nexus ears **4/4 by filename**  
**Stack:** OV 2026.3.0 + GenAI · `OpenVINO/kokoro-82M-int8-ov` · device **GPU** · voice **af_heart**

---

## 1. Files

| Filename | audio_s | Nexus ear |
|----------|--------:|-----------|
| `s0_4_short1_fox.wav` | 3.25 | **PASS** |
| `s0_4_short2_hello.wav` | 3.25 | **PASS** |
| `s0_4_short3_keys.wav` | 3.73 | **PASS** |
| `s0_4_multi_passage.wav` | 19.88 | **PASS** |

**Directory:** `spike/ov263-genai/out/s0_4/` (+ `artifacts/s0_4/`)  
**Manifest:** `manifest.json`  
**Log:** `spike/ov263-genai/logs/s0_4_ears.log`

---

## 2. Nexus verdict (2026-08-07)

> Nice and clean. I can discern that it’s a different voice than what we had with our ship.

- All four files **PASS** (clear; no pad-moan / garbage called out).  
- **Different voice vs ship** noted and expected: official pack **af_heart** (v1.0-family int8) ≠ ship **af_bella** / v0.19 ort-cpu — cross-checkpoint caveat (notes/48) confirmed by ear, not a defect.

**S0.4 gate:** ≥3 shorts + multi PASS → **PASS**.

---

## 3. Implications

- Quality bar does **not** block S0-GO-* on ears alone.  
- int8 quant did not produce ear-kill artifacts on this set.  
- Next: **S0.5** cold vs steady RTF, A1 novel-shape, **unforced** A2 precision, B1 vs B3 vs notes/44 RTF 5.01.

---

## 4. One-line

**S0.4 PASS: Nexus 4/4 clean ears on official int8 GPU GenAI set; different voice vs ship expected; S0.5 next.**
