# notes/66 — I0.5 patched ov-gpu disposition

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Authority:** Nexus **`legacy-marked`** (explicit)  
**Architect rec:** Fable notes/65 — legacy-marked  
**Status:** **I0.5 COMPLETE**

---

## 1. Decision

| Backend | Disposition |
|---------|-------------|
| **`ov-gpu`** (patched `gpu4d.stft` ONNX) | **LEGACY-MARKED** |
| Code / `models/patched/` | **Retained** (honest-log / repro) |
| Maintenance | **None promised** for steady product work |
| Steady iGPU path of record | **`ovgenai-gpu`** (I0.2–I0.4) |

---

## 2. Why

| Evidence | Source |
|----------|--------|
| Patched ov-gpu fresh long RTF ~**5.01** | notes/44 |
| ovgenai-gpu served steady RTF ~**0.73** | notes/62 |
| ~**7×** steady advantage + official pack | S0 + I0 |
| Historical value: first real iGPU speech path | Warm Bucket / patch arc |

---

## 3. Docs touched

- `README.md` — backend table + legacy section; status → v1.3.0 / I0  
- `scripts/kokoro_server.py` — docstring + `make_backend` comment  
- **No** removal of ov-gpu code path  
- **No** default flip  

---

## 4. One-line

**I0.5: ov-gpu legacy-marked (code kept, no steady maintenance); ovgenai-gpu is optional iGPU steady path of record; default still ort-cpu.**
