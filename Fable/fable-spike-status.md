# Fable Spike Status — Componentized Decoder Export (G0–G3), Parked

**Date:** 2026-08-07
**Author:** Fable (Chief Architect) — phase status rollup, Architect's perspective
**Pairs with:** Grok's spike status (compilation source); short repo summary to follow per the dual-status convention
**Full record:** `Fable/note_17`–`24` (gates + decisions), `notes/25`–`31` (measurements)
**Status:** **PARKED** — G3 not passed; root-caused; revival requires a new gate note against a new export strategy.

---

## Mission and bet

The monolithic ONNX export was the common blocker behind every seam-requiring idea, and the monolith is a property of the export, not the model. The spike tested whether a from-source, componentized export — CPU frontend → seam B (`asr`, `F0`, `N`, `style`) → static-T OV-GPU decoder → pad-trim — could deliver realtime iGPU decode with no per-utterance JIT and restart-persistent compiles. Nexus characterized the bet at the outset the same way as the original proof-of-concept: probably a waste of time, do it anyway.

## Verdict in one paragraph

The architecture is real and the execution chain is validated end-to-end up to the GPU: seam B recomposes **bit-exact** in PyTorch; a dynamo ONNX export of the decoder passes the pre-registered parity bar on ORT-CPU; edge-replication padding is the correct bucket strategy; and on GPU, static-T **eliminated shape-JIT variance** (11 novel texts, 0.2 s spread, zero 17–25 s events) while **CACHE_DIR restart persistence worked** (0.28 s vs 2.49 s cold). What failed is delivery of that architecture *through* the OpenVINO GPU plugin: the plugin cannot compile the parity-correct graph (Conv rank mismatch introduced inside its own ProgramBuilder), and the only rewrite that does compile lands on `convolution_gpu_ref__f32` for 98.2% of its 11 s/infer runtime while damaging fidelity (corr 0.75; ear-detectable prosody shift). Two of the fork's three premises were proven; the third was blocked by two precisely-named external bugs, not by the architecture.

## Gate chain (all bars written before their measurements)

| Gate | Outcome | Key number |
|------|---------|-----------|
| G0 strict load | PASS (amended: structural allowlist — 116 AdaIN affine + 5 CustomSTFT buffers; zero learned weights missing) | outside-allowlist = 0 |
| G1 seam recomposition | PASS, bit-exact | 426/426 rungs maxdiff 0 |
| Pad sub-experiment | Zero-pad P2 (corr 0.973); **edge locked** (0.997); all five WAVs ear-indistinguishable | — |
| G2 export parity | PASS via written or-clause after calibration proved World D (same-engine floor ≤2e-6) and hardening found the legacy TorchScript exporter at fault | dynamo corr 0.999954, SNR 40.7 dB |
| G3 OV-GPU matrix | **FAIL** — offload PASS, restart PASS, JIT-variance absent, but 11/11 multi-second infers, RTF ≈ 5.07, quality damaged | ref-conv 98.2% of profile |
| Diagnosis (note_22 path B) | RCA complete; opset-17 escape route fails identically; park stands | Conv rank: 3D data vs plugin-4D filters |

## Falsified hypotheses (kept per honest-log)

Branch-A single-jump signature (outcome was structural keys, no jump); InstanceNorm `train=True` export warning as parity culprit (decomposition changed nothing); "near-bit-exact" cross-backend parity expectation (floor is real but the miss was legacy-exporter defect, ~10⁴× above floor); cold compile 5–30 s (2.49 s — the miss *was* the ref-kernel clue); warm RTF ≤ 0.9 (5.07 on the rewrite graph). Full scorecard in note_23 §2; pattern: PyTorch-side predictions hit, OV-plugin-side predictions missed — architecture proposes, silicon disposes.

## Durable assets produced

Bit-exact seam B recipe and hook-ladder instrument; dynamo export recipe with noise hoisted to graph inputs (plus the dead `uv_noise` upstream nit); edge-pad decision with measured justification; the G0 allowlist; the calibration methodology for cross-backend parity bars (C1–C4 + pre-registered amendment discipline); two GPU-ready repro graphs; and the **rank-3 family thesis** (note_24): five documented manifestations of the intel_gpu plugin's 4D-native core mishandling rank-3 audio graphs — the monolith's 3D Resize and STFT rank failures, the f16 MatMul shape failure, the two-graph ref-conv fallback, and the new half-applied Conv uprank. Nexus spotted the parallel; the filing pack cross-links all four issues under it.

## Disposition

- **Spike:** parked with full root cause; O1–O4 recorded in notes/30 for any future gate.
- **Product:** ship path unchanged and never touched (ort-cpu default, server v1.1.7 live / v1.1.8 pending approval); **response/chunk cache** is the agreed next product bet.
- **Upstream:** four filings queued (shape-JIT with static-T contrast; f16 MatMul; f32 ref-conv, two-graph; conv-rank, new) — cross-linked per the family thesis, full-decoder repro plus working minimals as contrast, restraint clause on internals claims.
- **Repo:** `spike/` code + artifacts, `notes/25`–`31`, `Fable/note_17`–`24`, and both statuses join the commit set.

## Architect's closing assessment

This is what a well-run negative result looks like: every bar was written before its measurement, every miss was scored, both confounds were named before conclusions hardened, and the park carries a smoking-gun profile instead of a shrug. The spike converted an architecture bet into two evidenced upstream bugs, a validated seam waiting for the plugin to catch up, and the strongest filing pack this project has held. The methodology — predict, measure, ears, decide — held under a failing result exactly as well as it held under passing ones, which is the property that makes the rest of the repo trustworthy.
