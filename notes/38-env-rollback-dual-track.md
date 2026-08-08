# notes/38 — Dual-track env rollback (ship 2026.2.1 / S0 side 2026.3)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Policy:** `Fable/Fable-note_27-dual-track-env-policy.md` (Nexus decision; Fable recorded; Grok §3 executed)  
**Supersedes-in-part:** `notes/37-env-openvino-2026.3.md` (in-place ship-venv 2026.3 pin). **Driver upgrade portion of notes/37 stands.**

---

## 1. Dual-track pins (live)

| Track | Runtime | Env path | GenAI |
|-------|---------|----------|--------|
| **Ship** | OpenVINO **2026.2.1** | `/data/intel-igpu-tts/venv` | **Not installed** |
| **S0 probe** | OpenVINO **2026.3 + GenAI** | side venv (create at S0.1; not yet) | yes |

Drivers (host, both tracks): compute-runtime **26.22.38646.7**, IGC **2.36.5**, kernel **7.0.0-28-generic** — **not** rolled back.

### Stack-identity caveat (verbatim from note_27 §2)

- Original lab measurements (notes/25–32 and earlier): **wheel 2026.2.1 + old driver stack.**  
- Ship env after this rollback: **wheel 2026.2.1 + new driver stack.**  
- These are **not** identical environments. New ship-track numbers carry the new stack identity (WORKFLOW honesty item 7 / S0 A3).

---

## 2. §3 checklist — done

| Step | Result |
|------|--------|
| 1. `openvino==2026.2.1` in ship venv | **OK** `2026.2.1-21919-ede283a88e3-releases/2026/2` |
| 2. Remove `openvino-genai`, `openvino-tokenizers` | **OK** (ImportError on genai) |
| 3. Revert `requirements.txt` / `.lock.txt` | **OK** — ship pins only; comment forbids GenAI in ship reqs |
| 4. Fresh cache dir | **`cache/openvino-2026.2.1-drv2622/`** (not reusing pre-driver-bump blobs) |
| 5. Update `notes/00-host-inventory.txt` | **OK** (dual-track section) |
| 6. This note | **OK** |
| 7. Post-rollback fox smoke | **OK** — see §3 |

---

## 3. Post-rollback smoke (fox)

Text: `The quick brown fox jumps over the lazy dog.`  
Voice: `af_bella`  
Claim scope: **product behaves** on wheel 2026.2.1 + new driver — not a full matrix.

### ort-cpu (product default)

| | |
|--|--|
| Model | `models/kokoro-v0_19.onnx` |
| WAV | `artifacts/rollback_dual_track/ort_cpu.wav` |
| Audio dur | 3.77 s |
| Mean infer (harness runs=2) | 1.640 s |
| **RTF** | **0.434** |
| Log | `logs/rollback_ort_cpu.log` |

### ov-gpu demo (patched ONNX)

| | |
|--|--|
| Model | `models/patched/kokoro-v0_19.gpu4d.stft.onnx` |
| Precision | f32 |
| Offload | `EXECUTION_DEVICES=['GPU.0']` |
| WAV | `artifacts/rollback_dual_track/ov_gpu.wav` |
| Audio dur | 3.90 s |
| Compile (cached after first) | ~0.8–11 s depending on cold/warm cache |
| Per-run infer (honest) | run0 **17.54 s** (cold/shape), run1–3 **~2.53–2.60 s** |
| **Warm steady RTF** (runs 1–3 mean) | **0.660** |
| Harness mean RTF (3 runs, includes cold) | 2.477 — **do not use as steady claim** |
| Log | `logs/rollback_ov_gpu.log` |

**Nexus ears (2026-08-07):** **PASS** both filenames

- `artifacts/rollback_dual_track/ort_cpu.wav` — PASS  
- `artifacts/rollback_dual_track/ov_gpu.wav` — PASS  

§3 post-rollback smoke **closed** on ears + metrics. Ship track unblocked for v1.1.8 / commit queue.

---

## 4. Product implication

- Ship track is back on the **proven wheel** with **current drivers**.  
- S0 remains free to install **2026.3+GenAI** only in a **side venv**.  
- Walk-back ladder (note_27 §4) still applies only after **both** tracks done.  
- Response/chunk cache remains top backend-agnostic product bet.

---

## 5. One-line

**Ship venv rolled back to OpenVINO 2026.2.1 (GenAI removed); drivers stay; fox smoke ort-cpu RTF~0.43 and ov-gpu warm RTF~0.66 on GPU.0; Nexus ears PASS both WAVs; dual-track policy live; §3 closed.**

---

## Cross-ref (Fable note_29)

Direct-harness warm RTF ~**0.66** (this note) vs later **server** pinned-fox RTF ~**0.95** (notes/35 v1.1.8 smoke) are **not** a regression pair — server RTF includes bucket/pad path (honesty item 4). Recorded so commit-set readers do not rediscover it as a bug.

