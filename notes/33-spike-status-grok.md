# Grok Spike Status — Componentized Decoder Export (G0–G3), Parked

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator / Profiler / Validator) — measurement-side rollup  
**Pairs with:** [Fable/fable-spike-status.md](../Fable/fable-spike-status.md) (Architect)  
**Short summary:** [notes/34-spike-closeout-summary.md](34-spike-closeout-summary.md)  
**Full record:** `Fable/note_17`–`25` (gates + decisions), `notes/25`–`32` (measurements + RCA + OV dive)  
**Status:** **PARKED** — G3 not passed; root-caused; ship path never broken; revival needs a **new** gate note.

---

## Mission (as executed)

Test whether a from-source, componentized Kokoro path — CPU frontend → **seam B** (`asr`, `F0`, `N`, `style`) → **static-T** decoder on OV-GPU → pad-trim — can deliver:

1. No per-utterance shape-JIT variance  
2. Restart-persistent compiles (`CACHE_DIR`)  
3. Realtime e2e (RTF ≤ 1) with honest offload proof  

Ship freeze held for the entire spike (`scripts/kokoro_server.py`, `models/patched/` off-limits). Work lived under `spike/`.

---

## Verdict (measurement side)

**Architecture through ORT: validated. Architecture through OV-GPU on this host: not product-viable with current export+plugin.**

| Claim | Result |
|-------|--------|
| Seam B is real | **PASS** — 426/426 rungs maxdiff **0** (notes/25) |
| Decoder-only ONNX export | **PASS** — dynamo, noise hoist, original parity bar via corr (notes/27–28) |
| Edge pad for buckets | **LOCKED** — zero-pad P2 metrics; edge 0.997; ears clean (notes/26) |
| Static-T kills shape-JIT *variance* | **TRUE** — 11 novels, ~11.0±0.1 s, zero 17–25 s events (notes/29) |
| CACHE_DIR restart persistence | **TRUE** — 0.28 s cached vs ~2.5 s cold (notes/29) |
| OV-GPU realtime decode | **FALSE as reachable** — RTF ≈ 5 on only compiling rewrite; raw dynamo won’t compile (notes/29–30) |

Gates were written before measurements (`note_17`+amendments). No silent bar moves. Ears never overwrote numeric gates.

---

## Gate chain (silicon record)

| Gate | Outcome | Headline numbers |
|------|---------|------------------|
| **G0** | PASS (allowlist) | 121 missing = 116 AdaIN affine + 5 STFT buffers; 0 unexpected; 0 learned drops |
| **G1** | PASS | Bit-exact recomposition; weekend maxdiff ~0.075 superseded |
| **Pad** | Edge locked | Zero corr 0.973 / edge 0.997; Nexus: all pad WAVs ear-indistinguishable |
| **G2** | PASS (original bar) | World D (floor ≤2e-6); legacy exporter fault; **dynamo corr 0.999954** |
| **G3** | **FAIL** | Offload PASS; restart PASS; multi-second 11/11; RTF ≈ 5.07; NCHW quality corr ~0.75 |
| **RCA** | Complete | Ref-conv 98.2%; opset-17 escape fails same Conv rank |
| **O2 minimal** | Full-model repro | Bare Conv1d/weight_norm dynamo **OK** on GPU; full decoder **FAIL** |
| **OV dive** | Supports park | Interpolate assert line-match; ImplementationsCache; 1D graph-optimizer comment; PR #37273 |

---

## What I ran (Orchestrator ownership)

- Mechanic: `spike/hook_ladder.py`, `pad_stats.py`, `g2_export.py`, NCHW rewrite, diagnosis scripts  
- Profiler: cold/warm/restart matrices, OV profiling, RTF tables, CACHE_DIR listings  
- Validator: parity bars, allowlist automation, ear fold-ins, no GO language without all sub-gates  
- Research: notes/23–24 stash era; notes/31–32 O2 + OpenVINO source/KB dive  
- Host hygiene: ship freeze, `spike/` isolation, notes under `notes/NN-*.md`

Dual critical paths enforced: ship path (ort-cpu / v1.1.7) never edited for spike convenience.

---

## Durable assets (measurement artifacts)

| Asset | Path |
|-------|------|
| Hook ladder + G0/G1 | `spike/hook_ladder.py`, `spike/out/` |
| Pad experiment | `spike/pad_stats.py`, `spike/out/pad_stats/` |
| G2 dynamo ONNX (canonical ORT) | `spike/out/g2/kokoro_decoder_t96_edge_dynamo.onnx` |
| G2 legacy (forensics only) | `spike/out/g2/kokoro_decoder_t96_edge.onnx` |
| G3 NCHW rewrite (GPU-loadable, slow) | `spike/out/g2/kokoro_decoder_t96_edge_dynamo_nchw.onnx` |
| G3 matrices / ears | `spike/out/g3/` |
| RCA profile (smoking gun) | `spike/out/g3/diagnosis/nchw_ov_profile.json` |
| O2 minimals | `spike/out/g3/diagnosis/minimal_conv1d/` |
| OV source clone | `/data/github/openvino` (sparse) |
| Measurement notes | `notes/25`–`32` |

---

## Ear log (Nexus, folded)

| Set | Verdict |
|-----|---------|
| G1 three WAVs | PASS |
| Pad five WAVs | PASS (no audible pad-mode difference) |
| G2 short + long | PASS (chunk pauses expected at T≤96) |
| G3 three WAVs | 1/3 clean; 2 slight final intonation on “berries”; 3 clean — prosody shifted, no extra utterances |

Ears bound perception; they did not rewrite G2/G3 numeric bars.

---

## Disposition (aligned with Fable)

| Track | Status |
|-------|--------|
| **Spike** | **PARKED** — not GO; O1–O4 only under a future gate |
| **Ship path** | Unchanged: ort-cpu default; server v1.1.7; v1.1.8 still Nexus |
| **Next product** | Response/chunk cache (black-box) — design on Nexus greenlight |
| **Upstream** | Four packs content-ready (Architect green-lit note_25): shape-JIT, f16 MatMul, f32 ref-conv (two-graph), conv-rank (+ family thesis note_24); Nexus submits |
| **Repo** | Commit set should include `spike/`, notes/25–34, Fable notes 17–25 + statuses, WORKFLOW.md |

---

## Measurement-side closing assessment

This spike did what the workflow asked: **falsifiable gates first**, silicon second, ears as quality bound, dual statuses at close.

We proved the **export architecture** (seam, pad, dynamo ONNX, static-T JIT-variance kill, CACHE_DIR). We failed to prove **product GPU realtime** because the only OV-GPU-compiling graph is a rewrite that both **selects ref convolutions** (98% of 11 s) and **damages fidelity**. That is a negative result with a profile, not a shrug.

I will not use GO language for G3. I will not treat ears as a parity waiver. I will not let CACHE_DIR marketing overclaim shape warm.

**Next measurement work when Nexus orders it:** cache acceptance matrix (ship path), or upstream live-capture refresh before filing — not spike revival without a new written gate.

---

*Orchestrator (Grok 4.5), 2026-08-07.*
