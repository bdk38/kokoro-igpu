# notes/44 — ov-gpu WebUI soak (valid data retained)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Status:** **CLOSED** — switched back to **ort-cpu** for daily WebUI; keep these measurements  
**Runtime:** ship dual-track OV **2026.2.1**, drivers 26.22.38646.7 / IGC 2.36.5  
**Server during soak:** v1.2.0 · `KOKORO_BACKEND=ov-gpu` f32 · patched `gpu4d.stft` · `KOKORO_TTS_CACHE=1` tier=both  
**Logs:** `logs/kokoro_v120_webui_ovgpu.log`, `logs/cpu_gpu_monitor_ovgpu_soak.log`, `logs/gpu_monitor_ovgpu_soak.log`  
**Related:** notes/43 (v1.2.0 ship + wire-up), notes/15 (WebUI split), notes/18–20 (shape-key / RTF honesty)

---

## 1. What is valid (keep)

### A. Product path still works under WebUI
- Open WebUI reaches host Kokoro via `http://host.docker.internal:8880/v1`.
- Container `POST /v1/audio/speech` returns 200; OWUI transcodes WAV→MP3 and can **cache MP3** client-side (refresh + Read Aloud = instant replay without re-hitting Kokoro).
- TTS response cache (C1/C2) works on ov-gpu keys separately from ort-cpu (`backend_id` in key).

### B. ov-gpu offload is real on this host
During the long fresh miss, `intel_gpu_top` showed extended windows of:

- **GPU max / Render-3D (rcs) ≈ 98–100%**
- Host busy often ~30–40% in parallel  
- Sample span of heavy GPU: roughly **22:11:53–22:15:15** local (join log)

So “GPU backend” is not a silent CPU fallback for the patched demo graph.

### C. Honest ov-gpu latency (server path, fresh multi-chunk)
One WebUI-originated request (from `172.22.0.3`):

| Field | Value |
|-------|------:|
| voice | af_bella |
| tokens | **631** |
| chunks (C2) | **2** misses (`c2_hits=0 c2_misses=2`) |
| audio duration | **42.92 s** |
| wall infer | **215.12 s** |
| **RTF** | **5.01** |
| cache | **miss** |
| compile | bucket **512** ~8.5 s; bucket **288** ~7.6 s (before/during) |

**Product implication:** ov-gpu remains **demo / offload proof**, not a Read Aloud default. Novel long text can pin the UI spinner for **minutes** while OWUI waits for the full response (no progressive TTS).

### D. Cache behavior contrast
| Case | Behavior |
|------|----------|
| Exact fox after `KOKORO_WARM_TEXT` | C2/C1 **hit**, wall tens of ms, GPU ~0 |
| Duplicate / OWUI-cached paragraph | Instant play from **OWUI MP3 cache** and/or C1 — may never re-POST Kokoro |
| Fresh long paragraph on ov-gpu | Full miss, RTF ~5, GPU pegged |

### E. Open WebUI side nits (non-blocking)
- `Error fetching voices from custom endpoint: string indices must be integers, not 'str'` — our `/v1/audio/voices` JSON shape ≠ OWUI’s expected schema (voice still usable when set to `af_bella`).
- `GET /v1/audio/models` → 404; OWUI falls back to `/v1/models` OK.
- `split_on=paragraphs` sends large units → worse cold ov-gpu UX than sentence split (but sentence split was previously bad when RTF ≫ 1 for *many* slow requests — notes/15). On **ort-cpu**, punctuation/paragraphs both fine.

---

## 2. What not to over-claim
- Do **not** quote ov-gpu RTF 5.01 as steady-state for short fox after warm (shape-key + cache change the story).
- Do **not** treat OWUI instant replay after refresh as Kokoro C1 proof without a matching `[speech] cache=hit` line.
- GPU monitor required **sudo** `intel_gpu_top` on this host (user assert failure in igt).

---

## 3. Post-soak disposition (Nexus)
- **Monitors stopped.**
- **Server returned to ort-cpu** + TTS cache on `:8880` for daily WebUI.
- ov-gpu remains one env flip away for demos.

---

## 4. One-line
**Valid soak data: WebUI→ov-gpu path works; iGPU really pegs ~100% RCS; fresh ~43 s audio cost ~215 s (RTF≈5); cache/OWUI-MP3 hide cost on repeats; daily driver back to ort-cpu.**
