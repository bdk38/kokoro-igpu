# notes/42 — C2 chunk cache probes (ship as **v1.2.0**)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator) + Mechanic (Grok Build)  
**Status:** **C2 CLOSED** — Validator byte-equality PASS; **Nexus ears PASS** (supplementary).  
**Design lock:** `notes/41` · parent `Fable/Fable-note_28-…`  
**Fable read-back:** `Fable/fable_response_41_42`  
**Runtime:** ship dual-track OV **2026.2.1**, **ort-cpu**  
**Product version:** **`1.2.0`** (C1+C2 single ship — see notes/43). Internal probe labels may still say v121.  
**Code:** `scripts/kokoro_server.py` **1.2.0**, `TTS_CACHE_SCHEMA_VER=2`

---

## 1. What landed

| Item | Detail |
|------|--------|
| C2 | Per-`chunk_text` token-id keys (`c2ids:…`); shared disk store with C1 |
| Composition | C1 full hit first → else C2 partial synth → write C2+C1 |
| Header | `hit` \| `partial` \| `miss` |
| Assembly | **Always** per-chunk int16 roundtrip (cache on or off) for byte-identity |
| schema_ver | **2** (disk format; not the product semver) |
| Default | still `KOKORO_TTS_CACHE=0` until live WebUI soak |

---

## 2. Probe matrix

| Probe | Result | Evidence |
|-------|--------|----------|
| **P0** cache off, multi-chunk | **PASS** | `p0_a.wav` == `p0_b.wav` (3 925 484 B) |
| **P1** C1 hit (tier=both) | **PASS** | fox miss→hit; equal; hit wall **20 ms** vs 1.55 s |
| **P3** partial prefix | **PASS** | header **`partial`**; `c2_hits=4 c2_misses=1`; **byte-equal** to cache-off full |
| **P3b** tier=chunk only | **PASS** | full miss→all-chunk **hit**; equal; hit wall **59 ms** vs 33.5 s |
| **P5** concurrent cold | **PASS** | both 200, bodies equal; follow-up hit |

### P3 detail (amended multi-chunk prefix)

- Prefix: 4× ~40-word sentences → **4** chunks  
- Full: 5 sentences → **5** chunks; shared prefix chunks = **4**  
- Seed prefix: `cache=miss c2_hits=0 c2_misses=4` wall ~26.8 s  
- Full with C2 warm prefix: `cache=partial c2_hits=4 c2_misses=1` wall **6.77 s** (vs fresh off **33.9 s**)  
- `p3_partial_full.wav` **==** `p3_fresh_off.wav`

### P3b (chunk tier, no C1)

| Step | cache | c2 | wall_s |
|------|-------|-----|-------:|
| 1 | miss | 0/5 | 33.47 |
| 2 | hit | 5/0 | 0.059 |

---

## 3. Artifacts / logs

- WAVs: `artifacts/v121_cache/` (`p0_*`, `p1_*`, `p3_*`, `p3b_*`, `p5_*`)  
- Logs: `logs/v121_p0.log`, `v121_p1.log`, `v121_p3.log`, `v121_p3_off.log`, `v121_p3b.log`, `v121_p5.log`  

---

## 4. Validator verdict (formal gate)

- **P0 + P3 byte-equality PASS** → ear gate **waived** for C2 *correctness*.  
- **Branch K1 — clean.**

---

## 5. Nexus ears (supplementary — 2026-08-07)

Per Fable `fable_response_41_42`:

**PASS — all v121 probe artifacts by filename** (p0 / p1 / p3 / p3b / p5): clean and smooth, **no additional utterances**.

Weight: this path is a **new baseline** (always per-chunk int16 roundtrip). C1’s earlier 21/21 ears could not vouch for concat-seam quality after the roundtrip change. Bytes proved cache==fresh; ears proved the baseline is clean (no boundary artifacts).

Precedent unchanged: Validator waiver = formal correctness gate; Nexus ears = quality binding word.

---

## 6. Residual risks

1. Short multi-sentence packs into **one** chunk → no partial until packing splits (by design).  
2. schema v2 cold-start (empty/ignored pre-v2 tts cache trees).  
3. ov-gpu not re-probed.  
4. Live Open WebUI soak is the next honesty check (notes/43).

---

## 7. One-line

**C2 CLOSED under product v1.2.0: partial 4+1 byte-identical; Nexus ears clean on new roundtrip baseline; ship with C1 as one version.**
