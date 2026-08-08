# notes/62 — I0.3 served RTF (ovgenai-gpu through HTTP)

**Date:** 2026-08-08  
**Author:** Grok (Orchestrator)  
**Gate:** Fable note_29 §I0.3 · notes/54 G3 · notes/61 F3/F4 + Fable fox ≤0.85 prediction  
**Status:** **I0.3 PASS**  
**Artifacts:** `artifacts/i0_3/` · `i0_3_result.json` · `logs/i0_3_served_rtf.log`  
**Script:** `scripts/i0_3_served_rtf.py`  
**Daily :8880:** left on **ort-cpu** (probe used **:8893**)

---

## 1. Methodology (named)

| Item | Method |
|------|--------|
| Path | **POST `/v1/audio/speech`** (real server), not direct GenAI |
| Backend | **ovgenai-gpu** · pack `models/kokoro-82M-int8-ov` (first-class copy) |
| Runtime | ship `venv` OV **2026.3.0** + GenAI **2026.3.0.0** |
| TTS cache | **OFF** (measure synth + assembly, not C1 hit) |
| Warm | `KOKORO_WARM_TEXT` = **chunk-shaped** pins (fox + multi piece A + piece B) per F4 |
| Steady | discard first **timed** run per shape; mean of remaining |
| Bar | steady RTF **≤ 1.0** on fox **and** multi |
| Fable pred | served steady fox **≤ 0.85** (on record notes/61) |
| Novel tax | one new text after warm; first vs second wall |
| Chunk overhead | report-only (G3) |

---

## 2. Steady served RTF

### Fox (`af_bella`)

| run | wall_s | audio_s | RTF |
|-----|-------:|--------:|----:|
| 0 (discard) | 3.02 | 3.55 | 0.852 |
| 1–4 mean | **~2.58** | 3.55 | **0.728** |

### Multi (2-chunk passage)

| run | wall_s | audio_s | RTF |
|-----|-------:|--------:|----:|
| 0 (discard / cold chunks) | **97.38** | 21.25 | 4.582 |
| 1–3 mean | **~15.39** | 21.25 | **0.724** |

| Bar | Result |
|-----|--------|
| fox steady ≤ 1.0 | **PASS** (0.728) |
| multi steady ≤ 1.0 | **PASS** (0.724) |
| Fable fox ≤ 0.85 | **PASS** (0.728 ≤ 0.85) |

**vs S0.5 direct** (~0.70 fox / ~0.69 multi): served overhead ~**+0.03 RTF** — well inside prediction.

---

## 3. Novel tax (A1 family, served)

| | wall_s | audio_s | RTF |
|--|-------:|--------:|----:|
| novel first | **33.34** | 6.25 | 5.33 |
| novel second | 4.57 | 6.25 | 0.73 |
| **Δ wall** | **+28.8 s** | | |

Shape-JIT still lives on the **served** path. Steady is product-fast; first novel hit is not. TTS cache + chunk-shaped warm remain the UX mitigations.

Cold multi first **97 s** matches Fable F3: per-chunk path can pay **multiple** novel JITs (here ~2 chunks) vs S0.5 whole-text one-shot (~63 s class).

---

## 4. Chunk overhead (report-only G3)

Both overhead probes were **first-seen shapes** (cold), so RTF ~5.5 is JIT-dominated — **not** a fair fixed-cost compare. Do not use these rows as steady overhead. Formal 1-vs-N steady matrix can revisit in I0.4 if needed after pinning both shapes; not required for I0.3 kill bar.

| tag | wall_s | audio_s | note |
|-----|-------:|--------:|------|
| overhead_punctuated | 27.4 | 5.0 | cold |
| overhead_onechunkish | 30.2 | 5.5 | cold |

---

## 5. Stack (A3)

```text
openvino 2026.3.0
openvino-genai 2026.3.0.0
devices CPU, GPU
pack models/kokoro-82M-int8-ov  bin sha c879cdd8…
voice af_bella
```

---

## 6. Product implication

1. **Served** ovgenai-gpu steady RTF is **realtime-class** (~0.73) on this Xe-LP for warmed shapes — clears I0.3 and Fable’s tighter fox prediction.  
2. Integration overhead vs direct S0.5 is **small**.  
3. Novel/first-chunk tax remains **tens of seconds** — do not market steady RTF as first-utterance latency.  
4. Default still **ort-cpu** until I0 verdict + Nexus cutover decision.  
5. I0.4 next (pre/post soak fox already matched notes/61; full matrix + ovgenai cache byte-eq).

---

## 7. Verdict

**I0.3 PASS**

---

## 8. One-line

**I0.3 PASS: served ovgenai-gpu steady fox/multi RTF 0.73/0.72 (≤1.0; fox ≤0.85 pred holds); novel +28.8 s first hit; cold multi 97 s = multi-chunk JIT; :8880 ort-cpu untouched.**

**Fable fold:** `notes/63` — prediction **held**; filing #1 gets novel row; lean **I0-GO-default-candidate** after I0.4/I0.5; default-question frame only.
