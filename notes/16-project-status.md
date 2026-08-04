# Project status — Intel iGPU Kokoro TTS

**Date:** 2026-08-04 (evening)  
**Host:** bdk-server (i3-1215U, UHD 8086:46b3, Xe-LP)  
**Sandbox:** `/data/intel-igpu-tts`  
**Server:** `scripts/kokoro_server.py` **v1.1.5**  
**Author:** Grok (measurement / validation side). Complements Fable `16-project-status.md` / `note_10`; supersedes the open items in `notes/10`–`15` for board state.

---

## One-paragraph result

Kokoro TTS runs on this Alder Lake iGPU for real: patched ONNX (`models/patched/kokoro-v0_19.gpu4d.stft.onnx`), whole-graph OpenVINO GPU, engines busy, speech ear-validated. It is **correct enough to demo** and **too slow to default** (ov-gpu f32 RTF ~4–6 vs ort-cpu ~0.4). An OpenAI-compatible server ships both paths; Open WebUI is wired. Two field bugs that appeared in real Read Aloud use — pad-tail moan and mid-passage skips — are **closed** with logs, predicted cut durations, and human ears. Remaining work is packaging, upstream OpenVINO issues, and optional perf experiments — not “can it speak on the iGPU?”

---

## Phase gates (final)

| Gate | Status |
|------|--------|
| HW: DRI / OpenCL / Level Zero see iGPU | PASS |
| OpenVINO lists GPU | PASS |
| Tiny OV GPU smoke | PASS |
| Stock Kokoro ONNX on OV EP GPU | FAIL (3D linear Resize; then STFT rank) |
| Graph surgery v1 Resize 3D→4D | PASS compile step; not enough alone |
| Graph surgery v2 + STFT rank stamp | PASS session create on GPU/CPU |
| Direct OV GPU whole-graph + RCS proof | PASS offload; quality/speed caveats |
| Real-text harness + human listen | PASS speech; GPU slower/quieter/muffled vs ORT |
| Phase 5 OpenAI server (ort-cpu default) | PASS |
| Phase 6 Open WebUI wiring | PASS |
| Pad-tail trim (OV buckets) | **PASS — v1.1.5** |
| WebUI Read Aloud skips | **PASS as config — notes/15** |

---

## What ships

### Runtime
- **Product default:** `KOKORO_BACKEND=ort-cpu`, original `models/kokoro-v0_19.onnx`, RTF ~0.40–0.45 on real text.
- **iGPU demo:** `KOKORO_BACKEND=ov-gpu`, patched model, `KOKORO_GPU_PRECISION=f32` (f16 still broken upstream at infer).
- **Also:** `ov-cpu` on patched model (corr ~0.97 vs ORT; optional).
- Endpoints: `/v1/audio/speech`, `/v1/audio/voices`, `/v1/models`, `/health`.
- Voices: 50 Kokoro + OpenAI aliases + weighted blends; `extra=ignore` for WebUI payloads.
- OV: bucket pad 96/192/288/384/512, compile cache, **infer lock** (no busy 500s under multi-POST).
- OV-only **pad-tail trim v1.1.5** (see below).
- Docstring: Open WebUI wiring including **Response Splitting** guidance (doc-only on validated code).

### Trim ruleset (v1.1.5) — closed

Strip a trailing RMS group only if **all** of:
1. **weak** — peak < 0.9 × speech ref  
2. **short** — duration < 0.6 s  
3. **detached** — gap before group ≥ 0.15 s  
4. **in pad window** — group start inside search region  

Ref = p90 of frames ≥ 0.1 × clip max RMS; refuse trim if ref < 1e-3.  
ORT never pads → never trims.  
`KOKORO_TRIM_DEBUG=1` logs per-group peak/ref, gap, tail, verdict.

**Final ear set (artifacts/v115):** all seven PASS — s1_well, s2_wallet (full “passport”), s3_peter, s4_swans, fox, whisper_stop (“stop” present), full_repro. No pad moan. Predicted cuts matched measured to 0.01 s.

### Falsified trim ideas (keep in repo memory)
| Version | Idea | Why it died |
|---------|------|-------------|
| v1.1.1 | Cut at first sustained quiet in pad window | Ate comma/list pauses (“wallet,” → dropped “passport”) |
| v1.1.3 | Raise moan ratio only + multi-strip | Fixed some moans; stripped soft “port” syllable (0.36× attached by 0.10 s gap) |
| v1.1.4 | Terminal-silence keep (tail ≤ 0.8 s) | Protected **only** ear-confirmed moans (peter 0.82, whisper 1.16); zero true saves |

Detachment (0.15 s) is the structural axis that separates stop-closure from pad gap when level/duration overlap.

---

## WebUI skips — closed as configuration

**Symptom:** Read Aloud stopped mid-passage (e.g. before “passport”) on ov-gpu.  
**Not** v1.1.5 mid-word trim on full-string requests (single-POST full_repro complete).

**Cause:** Open WebUI **Response Splitting = Punctuation** sends one TTS POST per sentence. ov-gpu RTF ≫ 1 + serial lock → late segments; client playback drops/stops. Logs: multi-POST from `172.22.0.3` vs later single ~300-token POSTs.

**Fix (settings, not code):**
| Splitting | ov-gpu multi-sentence | Notes |
|-----------|----------------------|--------|
| Punctuation | FAIL (skips) | Default; fine for **ort-cpu** |
| None | PASS | One request; long time-to-first-audio |
| Paragraphs | PASS on single-block text | Same as None if no blank lines |

Documented in server docstring + `notes/15-webui-response-splitting.md`.

---

## Performance / quality (honest)

| Path | RTF (order) | Quality vs ORT | Offload proof |
|------|-------------|----------------|---------------|
| ort-cpu | ~0.4 | reference | N/A |
| ov-cpu | ~ORT | corr ~0.97; listen OK | CPU |
| ov-gpu f32 | ~4–6 (server) | intelligible; ~2 dB down, faintly muffled; ~3% duration drift historically | GPU.0 + RCS + gpu kernels |
| ov-gpu f16 | n/a | infer crash MatMul dims | — |

iGPU offload ≠ win on this UHD with current OV f32 ref convolutions.

---

## Evidence map (for repo readers)

| Topic | Notes / artifacts |
|-------|-------------------|
| Host / stack | `00`, inventory |
| Early OV EP fails | `02`, `03` |
| Resize / STFT patches | `04`, `05`; `models/patched/` |
| Direct OV + profiles | `06` |
| Real text + listen reconcile | `07` |
| Server + WebUI wire | `08`, `09` |
| Trim saga | `10`–`14`; `artifacts/v112`–`v115`; `logs/server_v11*.log` |
| WebUI splitting A/B | `15`; WebUI lines in `logs/server_v115.log` |
| Probes | `scripts/probe_v112.py`, `v113`, `v114`, `v115`, `probe_v112_lock.py` |
| Upstream drafts | `issues/openvino-issue-1-f16-matmul.md`, `issue-2-f32-conv-ref-kernels.md` |

**Recommendation:** keep `artifacts/v112`–`v115` WAVs (or attach at release). Status claims are checkable only with WAV+log pairs.

---

## Team split (this arc)

- **Fable:** diagnosis, graph surgery, server/trim implementation, falsifiable predictions, status prose.  
- **Grok:** on-box runs, matrices, intel_gpu_top / duration / peak-ref numbers, concurrency lock proof, ear-attached notes under `notes/NN-*.md`.  
- **Lead:** ears, WebUI A/B, product calls.

Methodology that worked: **log every gate → ear labels the groups → predict next cuts → re-probe**. Two gates were deleted because their own logs only ever “saved” moans.

---

## Outstanding board

### Immediate (pre- or with first public commit)
1. **Git commit** of v1.1.5 server (incl. Response Splitting docstring), notes `00`–`16`, probe scripts, patched model path docs, issue drafts; decide artifact WAV policy (track vs LFS vs release zip).  
2. **OpenVINO issues** — paste final logs into drafts, add repo link, file, cross-link:  
   - f16 MatMul shape failure after compile  
   - f32 `convolution_gpu_ref__f32` dominance / RTF>1 + fidelity delta on Xe-LP  

### Queued (decided, not built)
3. Server response cache (text/voice/speed).  
4. `KOKORO_CPU_THREADS` / E-core binding experiments.  
5. Stress-test spec: CPU load vs GPU clocks/RTF (shared RAPL) before freezing perf claims.  

### Open questions
6. Partial graph offload / STFT-on-CPU hybrid inside OV (research).  
7. Whether ov-gpu stays “demo only” forever on Xe-LP without upstream kernel wins.  
8. WebUI-side playback that never drops segments (upstream WebUI; out of tree unless we patch).  

### Ops hygiene
9. systemd unit for kokoro_server (still a host process).  
10. Default WebUI audio settings documented for operators (splitting + backend pairing).  
11. Turn off `KOKORO_TRIM_DEBUG` in “production” runs (noise / minor I/O); keep for field debug.

---

## Commit discussion (Grok view)

**Should go in:**
- `scripts/kokoro_server.py` v1.1.5  
- `scripts/patch_*.py`, `tts_harness.py`, `test_kokoro_*.py` as applicable  
- `scripts/probe_v11*.py` (reproducible trim evidence)  
- `notes/00`–`16`  
- `issues/*.md`  
- `README` / `CONTRIBUTORS` refresh pointing at status + how to run ort-cpu vs ov-gpu  
- `models/` : at least document paths; large ONNX may be Git LFS or “download script” rather than raw blob  

**Strong yes on artifacts:** `artifacts/v115/` (and ideally v112–v114 failing intermediates) as release assets if not in git.  

**Verify before push:**
- `py_compile` server  
- One ort-cpu fox curl + one ov-gpu fox curl on clean checkout instructions  
- No secrets in notes (API keys, etc.)  
- `.gitignore` for `venv/`, `cache/openvino/`, huge accidental dumps  

**Commit message theme (suggestion):**  
real iGPU Kokoro via OV + surgery; OpenAI server; trim v1.1.5; WebUI splitting guidance; evidence notes 00–16.

---

## Bottom line

Dormant iGPU thesis: **held**.  
Ship path: **ort-cpu**.  
Demo path: **ov-gpu f32 + patched model + WebUI splitting None/Paragraphs**.  
Field quality on server speech ends: **closed**.  
Next value: **commit + Intel breadcrumbs**, not more trim knobs.

