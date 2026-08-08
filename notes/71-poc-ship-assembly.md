# notes/71 — PoC ship assembly (Fable note_33 execution)

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Architect:** Fable note_33  
**Status:** **ASSEMBLY COMPLETE** — ready for commit + R0 stranger rehearsal + Nexus ears

---

## 1. Identity (Nexus)

Two finished products:

| | **PoC (A)** | **Prototype (B)** |
|--|-------------|-------------------|
| Era | ONNX v0.19 + surgery | GenAI official pack |
| Repo default | **`ort-cpu`** (v1.5.0) | env `KOKORO_BACKEND=ovgenai-gpu` |
| Claim | Hearable proof on budget Intel box | Evolutionary realtime iGPU path |

notes/68 cutover remains **bdk deploy preference**, not repo default.

---

## 2. Branch check — ov-gpu on 2026.3

| Result | Detail |
|--------|--------|
| Compile | **PASS** ~3.1 s · `EXECUTION_DEVICES=['GPU.0']` |
| Infer | **PASS** peak 1.85, audio written |
| **Pin strategy** | **single-venv 2026.3** (Fable prediction held) |

Evidence: `artifacts/poc_ship/ovgpu_2026_3_check.json`, `ovgpu_2026_3_foxish.wav`

---

## 3. Patch regeneration

| Result | Detail |
|--------|--------|
| Script | `patch_kokoro_v2.py --stamp-stft` |
| SHA256 | `effa0895…` **byte-identical** to `models/patched/…stft.onnx` |

Evidence: `artifacts/poc_ship/patch_regen_check.json`

---

## 4. Bow created

| Item | Path |
|------|------|
| MODELS.md | root |
| download_models.sh | SHA verify added |
| reproduce/2026.2.1/ | lock + requirements + README |
| smoke_product.sh | ort-cpu required; GPU legs optional |
| docs/INDEX.md | arc map |
| Code default | **ort-cpu** · version **1.5.0** |

---

## 5. Out of scope (held)

- Filings research hold  
- Full reorg / server/ move  
- Second repo  
- Prototype feature backlog  

---

## 6. Next (Nexus)

1. Commit pack (this assembly)  
2. R0 fresh-clone rehearsal  
3. Ears on `artifacts/poc_ship/smoke/*.wav`  
4. Tag `poc-complete`  

---

## 7. One-line

**PoC assembly done: ov-gpu speaks on 2026.3; surgery regenerates byte-identical; MODELS/smoke/reproduce/INDEX in place; repo default ort-cpu v1.5.0; commit + R0 ears remain.**
