# notes/74 — GenAI repo seed + R1 rehearsal (Fable note_34)

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Status:** **R1 SMOKE PASS** — awaiting Nexus ears + `prototype-complete` tag

---

## 1. Monorepo (§5)

| Action | Result |
|--------|--------|
| B1 `artifacts/prototype/**` | Pushed `031c999` |
| Sibling README line | yes |
| Version strings 1.5.1 | yes |
| Delete `venv-s0-ov263` | done (~5 GB) |
| note_34 committed | yes |

## 2. Seed `bdk38/kokoro-igpu-genai`

| | |
|--|--|
| Commit | `8987f74` |
| Message | seed from kokoro-igpu @ poc-complete |
| Default | **ovgenai-gpu** |
| Version | **2.0.0** |
| Manifest | server, requirements, MODELS, fetch_pack.sh, smoke.sh, PROVENANCE, README |

## 3. R1.2 stranger rehearsal

| Step | Result |
|------|--------|
| Fresh clone | OK |
| venv + requirements | OK |
| fetch_pack hash verify | OK (bin/xml + 54 voices) |
| **ovgenai-cpu** speak | **PASS** — local pack path |
| **ovgenai-gpu** speak | **PASS** — local pack path |
| Novel tax | not a FAIL (expected) |

WAVs for ears:

```text
/tmp/kokoro-igpu-genai-r1/artifacts/smoke/ovgenai_cpu.wav
/tmp/kokoro-igpu-genai-r1/artifacts/smoke/ovgenai_gpu.wav
```

Also copied under monorepo `artifacts/prototype/r1_smoke/` if present.

## 4. Next

1. Nexus ears by filename  
2. Tag **`prototype-complete`** on genai `8987f74` (or tip after any fix)  
3. Fable may polish README (§6) — seed inventory is this note  

## 5. One-line

**note_34 executed: monorepo B1 pushed; genai appliance seeded 2.0.0 default ovgenai-gpu; R1 clone-and-speak PASS cpu+gpu; ears + tag remain.**
