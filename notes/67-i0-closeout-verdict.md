# notes/67 — I0 closeout + verdict word

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Gate:** Fable note_29 · notes/54–56 · 58–66  
**Status:** **I0 CLOSED**

---

## 1. Bar rollup

| Bar | Result | Note |
|-----|--------|------|
| I0.1 voice | **PASS** | both bella + heart first-class (56) |
| I0.2 backend | **PASS** | ovgenai + c2txt; ears 4/4 incl speed (60) |
| I0.3 served RTF | **PASS** | fox/multi steady **0.73/0.72** (62) |
| I0.4 regression | **PASS** | pre/post fox SHA; cache; genai byte-eq doctrine (64–65) |
| I0.5 ov-gpu | **DONE** | **legacy-marked** (66) |

**Convergence:** ship venv 2026.3+GenAI (59) under filings waiver (58).  
**Pack:** first-class `models/kokoro-82M-int8-ov` (61 F5).

---

## 2. Verdict word

# **`I0-GO-default-candidate`**

**Meaning (gate vocabulary):** all integration bars PASS → **Nexus default decision is formally open**.  
This verdict **does not** change `KOKORO_BACKEND` default. Default today remains **`ort-cpu`**.

Architect lean (notes/63): same word on evidence.

---

## 3. What shipped technically (v1.3.0)

- Backends: `ovgenai-gpu` / `ovgenai-cpu` selectable  
- Per-chunk GenAI + `c2txt:` C2 (schema_ver 3)  
- Native `speed=`  
- Voices: pack `.bin`; default voice name still `af_bella`  
- TTS cache inherited  
- ov-gpu legacy  

---

## 4. Validation doctrine (preserve)

From notes/65: on **ovgenai-gpu**, byte-equality holds **within a warmth class**; across cold vs warm, use **corr + ears**. C2 may store cold-numerics on first miss — not corruption. **ovgenai-cpu** is not under byte-eq doctrine.

---

## 5. Default decision — opened, not made

| Option | Summary |
|--------|---------|
| **Cut over** | default → `ovgenai-gpu` |
| **Flag** | default stays `ort-cpu`; ovgenai selectable |
| **Split** | ovgenai-gpu default + ort-cpu fallback |

**Counterweights:** first-novel tax (tens of seconds); checkpoint/voice change (I0.1); ort-cpu reliability; founding CPU-offload premise (Fable notes/63).

**Nexus owns the call.** No automatic flip.

### Resolved 2026-08-08

Nexus chose **cut over** → see **`notes/68`**. Product default is now **`ovgenai-gpu`** (v1.4.0). Fallback: `KOKORO_BACKEND=ort-cpu`.

---

## 6. Remaining endgame (outside I0 bars)

1. **Default decision** (above)  
2. **Filings** VERIFY + GitHub submit (`issues/filing-*`) — at end per Nexus  
3. **Commit/push sweep** (S0–I0 notes, v1.3.0 server, pack identity, WORKFLOW, artifacts)  
4. Optional: systemd unit, OWUI voices JSON polish  

---

## 7. One-line

**I0-GO-default-candidate: ovgenai-gpu integrated and measured (steady ~0.73 served); ov-gpu legacy; default still ort-cpu; Nexus default decision + filings + commit remain.**
