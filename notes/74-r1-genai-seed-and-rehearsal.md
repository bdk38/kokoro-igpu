# notes/74 — GenAI repo seed + R1 rehearsal (Fable note_34)

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Status:** **R1 CLOSED PASS** — Nexus ears 2/2; tag **`prototype-complete`** on genai `8987f74`

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

### Nexus ears (binding)

| File | Ear |
|------|-----|
| `ovgenai_cpu.wav` | **PASS** |
| `ovgenai_gpu.wav` | **PASS** |

## 4. Next

1. ~~Ears~~ **PASS 2/2**  
2. ~~Tag~~ **`prototype-complete`** @ `8987f74`  
3. Fable may still polish README (§6) optionally  

## 5. One-line

**note_34 done: genai appliance shipped; R1 PASS; Nexus ears PASS 2/2; tag prototype-complete @ 8987f74.**
