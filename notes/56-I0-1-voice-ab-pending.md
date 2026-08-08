# notes/56 — I0.1 voice A/B (**CLOSED**)

**Date:** 2026-08-08  
**Status:** **I0.1 PASS** — Nexus ears + voice policy recorded  
**Nexus ack context:** I0 locked, Option A, I0.1 first; lean bella; HF heart rank A  

---

## 1. Ear results (all PASS)

| File class | Nexus |
|------------|--------|
| Ship v0.19 af_bella (fox/keys/multi) | **PASS** |
| Official v1 af_bella (fox/keys/multi) | **PASS** |
| Official v1 af_heart (fox/keys/multi) | **PASS** |

**Qualitative (Nexus, binding product note):**

- Ship **bella** has **more depth**.  
- Official **bella** is **more treble** — “as if missing lower frequencies.”  
- **Both surprisingly good** → not a quality kill on either.  
- No ship heart; official **heart is excellent** as well.

Cross-checkpoint timbre difference confirmed by ear (expected; not a defect bar).

---

## 2. Voice policy decision (I0.1)

**Choice: BOTH first-class**

| Role | Voice |
|------|--------|
| Continuity / familiar | **af_bella** (v1.0 pack on ovgenai; v0.19 remains on ort-cpu/ov-onnx) |
| HF rank-A / alternate excellence | **af_heart** (ovgenai pack) |
| Default on ovgenai backend (until UI says otherwise) | **Recommend `af_bella`** for continuity with ship docs/WebUI, with **af_heart fully selectable** — matches “both” without hiding heart |

Implementation implication for I0.2:

- `/v1/audio/voices` must list official pack voices when backend is `ovgenai-*` (or union list with backend tags — design in I0.2).  
- Default voice env: keep `KOKORO_DEFAULT_VOICE=af_bella` unless Nexus later prefers heart.  
- Document treble/depth difference honestly in README when Validator allows.

---

## 3. Artifacts

`spike/ov263-genai/out/i0_1/` · `artifacts/i0_1/` · `manifest.json`

---

## 4. Board after I0.1

| Item | Status |
|------|--------|
| I0.1 | **PASS / CLOSED** |
| Next block | **Convergence A** (filings submit or Nexus waiver) → ship venv 2026.3+GenAI |
| Then | I0.2 `ovgenai-gpu` in-process |

---

## 5. One-line

**I0.1 PASS: all A/B clean; ship bella deeper, official bella brighter; policy BOTH first-class (default bella + selectable heart); convergence gates I0.2.**
