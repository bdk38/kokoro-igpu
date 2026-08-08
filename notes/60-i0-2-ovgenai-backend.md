# notes/60 — I0.2 ovgenai backend integration (smoke)

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator) + Mechanic (Grok Build)  
**Gate:** Fable note_29 §I0.2 · notes/54 G1–G6 · Nexus waiver notes/58 · convergence notes/59  
**Status:** **I0.2 CLOSED — PASS** (smoke + Nexus ears 4/4)  
**Product version:** **1.3.0** (default backend still **ort-cpu**)

---

## 1. What shipped in tree (uncommitted)

| Path | Change |
|------|--------|
| `scripts/kokoro_server.py` | `OvGenAIBackend`, dual synthesize, pack voices, schema_ver **3**, v**1.3.0** |
| `scripts/i0_2_ovgenai_smoke.py` | Ephemeral `:8891` smoke |
| `README.md` | Backend flags only (no default flip / no GenAI RTF claims) |
| `requirements.txt` / `.lock.txt` | openvino **2026.3.0** + genai **2026.3.0.0** |
| `models/kokoro-82M-int8-ov` | symlink → S0 pack |
| `WORKFLOW.md` | post-S0 / I0 board |
| `notes/58`–`59` | waiver + convergence |

---

## 2. Design lock (as implemented)

| Item | Implementation |
|------|----------------|
| Backends | `ovgenai-gpu`, `ovgenai-cpu` |
| Synthesis unit | Server `chunk_text_strings` → one `generate()` per chunk |
| C2 key | `c2txt:` + exact chunk string; **schema_ver=3** |
| Speed | GenAI native `speed=` (no double resample) |
| Voices | Pack `voices/*.bin` (54); single voice only (no blends) |
| Default | **ort-cpu** unchanged |
| model_fp | sha256(`openvino_model.bin`) |

---

## 3. Smoke (`scripts/i0_2_ovgenai_smoke.py`)

| Check | Result |
|-------|--------|
| Health | `backend=ovgenai-gpu`, `genai=true`, pack model dir |
| Pipeline load | ~3.7 s · 54 voices · emb (510,1,256) |
| Fox repeat | **C1 hit** (infer 0.00 s) after warm/cache |
| Multi-sentence | **200** · `c2_misses=2` (multi-chunk c2txt path) · wall ~142 s first cold multi (A1 tax; **not** I0.3 steady) |
| speed=1.2 | WAV written `artifacts/i0_2/speed_1_2.wav` |
| py_compile | clean |

**WAVs for ears:**

| File | Role |
|------|------|
| `artifacts/i0_2/fox1.wav` | short (cache path) |
| `artifacts/i0_2/fox2.wav` | short repeat |
| `artifacts/i0_2/multi.wav` | multi-chunk seams |
| `artifacts/i0_2/speed_1_2.wav` | native speed≠1.0 (G4) |

---

## 4. Post-convergence ort-cpu sanity (I0.4 teaser)

After ship venv → 2026.3: ort-cpu fox×2 **byte-identical** SHA256  
`6c7c7e6d3ee0b6962db29ae3da600dc53f54bcf0173b2bde8c84922dfb83d771`  
Full I0.4 matrix still open (cache P0/P1, WebUI).

Live daily server restored: **ort-cpu + TTS cache** on `:8880` (v1.3.0 code).

---

## 5. Bar status (I0.2)

| Bar piece | Status |
|-----------|--------|
| Serves `/v1/audio/speech` | **PASS** (smoke) |
| C1/C2 wired (c2txt) | **PASS** (hit + multi c2_misses=2) |
| Warm-text path | warmup OK |
| Within-backend P0/P1 byte-eq | **not full matrix yet** — smoke hit path only |
| **Nexus ears** (seams + speed) | **PASS 4/4** (2026-08-08) |
| Default flip | **not done** (correct) |

### Nexus ear table (binding)

| File | Ear | Notes |
|------|-----|-------|
| `fox1.wav` | **PASS** | clear |
| `fox2.wav` | **PASS** | clear |
| `multi.wav` | **PASS** | multi-chunk seams OK |
| `speed_1_2.wav` | **PASS** | needed a couple listens; **words present and complete** (native speed≠1.0 OK) |

**I0.2 bar: PASS** — serves API, c2txt cache path exercised, ears clean including seams + speed.

---

## 6. Residual risks

1. Cold multi-chunk first hit still multi-minute (shape-JIT / A1) — I0.3 owns steady served RTF.  
2. Chunk seams need ears (concat + gap).  
3. schema_ver 3 invalidates old v2 TTS disk entries (intentional).  
4. Blends unsupported on genai.  
5. Checkpoint ≠ v0.19 (product identity already decided at I0.1).

---

## 7. Next

1. ~~Ears~~ **done**  
2. **I0.3** served RTF matrix (steady after warm; fox + multi ≤ 1.0)  
3. **I0.4** full ort-cpu regression  
4. **I0.5** ov-gpu patched disposition  
5. Verdict word only after I0.3–I0.5  

---

## 8. One-line

**I0.2 CLOSED PASS: ovgenai-gpu serves with c2txt cache; Nexus ears 4/4 (multi seams + speed=1.2 words complete); default remains ort-cpu; I0.3 next.**

**Fable fold:** `notes/61` (I0.3/I0.4 amendments F1–F6; pack promoted; pre/post fox already byte-match soak ref).
