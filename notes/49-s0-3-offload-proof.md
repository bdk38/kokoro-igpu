# notes/49 — S0.3 offload proof (official GenAI Kokoro GPU)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Gate:** `notes/36` §S0.3 · Fable guidance `notes/48`  
**Status:** **S0.3 PASS**  
**Model:** `OpenVINO/kokoro-82M-int8-ov` · GenAI `Text2SpeechPipeline` · device **GPU**  
**Artifacts:** `spike/ov263-genai/out/s0_3_result.json`, `logs/s0_3_offload_proof.log`, `logs/s0_3_intel_gpu_top.json`

---

## 1. Bar (pre-written)

| | |
|--|--|
| **PASS** | Proof heavy graph on **GPU.0** (not provider string alone) |
| **KILL** | Silent CPU fallback / cannot evidence offload |

---

## 2. Evidence (two independent channels)

### A. OpenVINO compiled-model property
Direct compile of official IR on `GPU` with `CACHE_DIR` + `INFERENCE_PRECISION_HINT=f32`:

```text
EXECUTION_DEVICES: ['GPU.0']
DEVICE_ID: 0
INFERENCE_PRECISION_HINT: float32   # compute hint (weights are int8 pack)
```

### B. `intel_gpu_top` during GenAI `generate` (sudo JSON, 500 ms)

| Window | samples | RCS max | RCS mean |
|--------|--------:|--------:|---------:|
| Idle (~3 s) | 3 | **0.0%** | 0.0% |
| During generate | 40 | **100.0%** | **63.5%** |

Matches notes/44 fingerprint class (real work pegs Render/3D). **Not** silent CPU.

### C. Functional
- GenAI load GPU: **4.3 s**  
- Generate fox: wall **15.3 s**, audio **3.25 s**, peak **0.31** (still not steady RTF — S0.5)

---

## 3. Verdict

| Check | Result |
|-------|--------|
| EXECUTION_DEVICES includes GPU.0 | **yes** |
| igt RCS activity vs idle | **yes** (0 → 100 max) |
| Silent CPU class | **no** |

**S0.3 verdict: PASS** (`verdict_reason: execution_devices_gpu`; igt corroborates)

---

## 4. Implications (no bar moves)

- Offload is real → S0-CPU-only path not forced by S0.3.  
- **A2 caveat (Fable notes/50):** f32 here was **requested** via `INFERENCE_PRECISION_HINT` — not GenAI default discovery. S0.5 A2 must query **unforced** GenAI-compiled precision.  
- Cold wall 22.6→15.3 s with CACHE_DIR is an **A1 teaser** only (blob cache vs residual JIT).  
- RCS mean 63.5% vs notes/44 sustained ~100% = weak B1 utilization **hint**, not evidence.  
- Next: **S0.4** ears; **S0.5** decision bar.

---

## 5. One-line

**S0.3 PASS: official int8 Kokoro GenAI on GPU.0 — EXECUTION_DEVICES=['GPU.0'] and intel_gpu_top RCS max 100% (idle 0%) during generate; silent-CPU killed.**
