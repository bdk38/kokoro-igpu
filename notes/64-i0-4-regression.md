# notes/64 — I0.4 regression matrix

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Gate:** Fable note_29 §I0.4 · notes/54 · notes/61 F1/F2 · notes/63  
**Status:** **I0.4 PASS**  
**Artifacts:** `artifacts/i0_4/` · `i0_4_result.json` · `logs/i0_4_regression.log`  
**Script:** `scripts/i0_4_regression.py` (+ steady multi follow-up)  
**Daily :8880:** remains **ort-cpu** + cache

---

## 1. Scoreboard

| Piece | Result | Evidence |
|-------|--------|----------|
| **A** ort-cpu pre/post fox vs soak | **PASS** | `fox_miss.wav` sha == post cache-off fox `6c7c7e6d3ee0…` (F1 exact) |
| **B** ort-cpu multi determinism | **PASS** | multi_a == multi_b sha `4f3064e815d0…` (within-post; exact v121 text N/A) |
| **C** ort-cpu cache P0/P1 | **PASS** | P0 equal; P1 miss→hit byte-eq; hit **2 ms** vs miss **1.52 s** |
| **D** ovgenai P0/P1 | **PASS**† | fox P0 byte-eq; multi P0 **steady** byte-eq; P1 cache byte-eq |
| **E** WebUI path | **PASS** | live speech OK; container→`host.docker.internal:8880` health **ort-cpu** |

† See §3 methodology note (cold-vs-warm false FAIL, then corrected).

**I0.4 verdict: PASS**

---

## 2. A — Pre/post fox (F1)

| | SHA256 | bytes |
|--|--------|------:|
| Pre `artifacts/webui_soak/fox_miss.wav` (v1.2.0 / 2026.2.1) | `6c7c7e6d3ee0b6962db29ae3da600dc53f54bcf0173b2bde8c84922dfb83d771` | 181244 |
| Post v1.3.0 / 2026.3 cache-off | **same** | 181244 |

Fable prediction held (notes/61 teaser confirmed in full matrix).

---

## 3. D — ovgenai byte-eq (F2) + RCA

### Pass criteria (final)

| Check | Result |
|-------|--------|
| Fox×2 cache-off | **byte-identical** |
| Multi×2 cache-off after **warm discard** | **byte-identical** (3/3 `gpu_warm_*.wav`) |
| Unique text miss→hit cache on | **byte-identical**; hit 2 ms |

### Initial false FAIL

First script pair mixed **cold multi (66 s)** vs **warm multi (11 s)**:

- same length 355800 samples  
- corr **0.9998**, maxdiff **0.031**  
- **not** equal SHA  

This is cold/first-infer numerical drift, not concat/cache corruption. Same class of honesty bug as averaging cold into steady RTF (note_11).

### Follow-up (binding)

After `KOKORO_WARM_TEXT` included multi chunks:

```text
gpu_warm_0..2: all sha 50dd3c4236d3…  byte-eq True  wall ~10.8 s
```

**Cache P1** never depended on that: miss/hit bodies already matched.

Informational: `ovgenai-cpu` warm multi still showed small nondeterminism (corr ~0.997) — product path under test is **GPU**.

---

## 4. C — Cache still green on 2026.3 ship venv

schema_ver **3** + ort-cpu: P0/P1 PASS. Hit path ~2 ms.

---

## 5. E — WebUI

- Host `:8880` health + speech OK (ort-cpu)  
- Docker open-webui → `host.docker.internal:8880/health` → ort-cpu OK  

---

## 6. Product implication

1. Convergence **did not** break ort-cpu bytes vs pre-upgrade soak fox.  
2. TTS cache remains correct on ship 2026.3.  
3. ovgenai-gpu cache + steady determinism OK; don’t byte-compare cold vs warm for GenAI multi.  
4. Default still ort-cpu; I0.5 disposition next; verdict lean remains **I0-GO-default-candidate** (notes/63).

---

## 7. One-line

**I0.4 PASS: pre/post fox byte-match soak; ort cache P0/P1 green; ovgenai fox+steady-multi+cache P1 byte-eq (cold/warm multi drift explained); WebUI path OK.**

**Fable fold:** `notes/65` — F1 strongest form accepted; **warmth-class byte-eq doctrine** for ovgenai; I0.5 lean **legacy-marked** patched ov-gpu.
