# Spike closeout summary — componentized decoder export

**Date:** 2026-08-07  
**Spike status:** **PARKED** (not GO)  
**Ship path:** unchanged (ort-cpu default; freeze held throughout)

This is the short public rollup. Full parallel statuses (kept, not merged away):

- [notes/33-spike-status-grok.md](33-spike-status-grok.md) — Grok (measurement / validation)  
- [notes/33-spike-status-fable.md](33-spike-status-fable.md) — Fable (architecture / gates)  
- Also: [Fable/fable-spike-status.md](../Fable/fable-spike-status.md)

Gate + decision chain: `Fable/note_17`–`25`.  
Measurements + RCA: `notes/25`–`32`.

---

## Result in one breath

A **from-source decoder-only export** of Kokoro v1.0 is real: seam B recomposes **bit-exact** in PyTorch; **dynamo ONNX** meets the written ORT parity bar; **edge pad** is the correct static bucket strategy; **static T removes shape-JIT variance** and **CACHE_DIR restart persistence works** on this Xe-LP host.

**Realtime OV-GPU product decode was not achieved.** OpenVINO GPU cannot compile the parity-correct dynamo graph (Conv rank mismatch inside ProgramBuilder). The only compiling rewrite runs ~**11 s/infer** (RTF ≈ **5**), spends **~98%** of time in `convolution_gpu_ref__f32`, and damages fidelity (corr ~0.75 vs ORT). Spike **GO is not earned.** Park is root-caused, not shrugged.

**Product default remains ORT-CPU.** Next agreed product bet: **response/chunk cache** (black-box). Upstream filings are stronger for the detour (four packs + rank-3 family framing).

---

## Gate scoreboard

| Gate | Result |
|------|--------|
| G0 strict load (allowlist) | PASS |
| G1 seam ladder | PASS (bit-exact) |
| Pad (edge vs zero) | Edge **locked** |
| G2 ONNX + ORT parity | PASS (dynamo, corr ≥ 0.9999) |
| G3 OV-GPU matrix | **FAIL** (offload + restart PASS; multi-second + RTF FAIL) |
| RCA / O2 / OV dive | Complete — park stands |

---

## Three fork claims (settled)

1. Static T eliminates shape-JIT **variance** — **TRUE** (measured).  
2. CACHE_DIR persists static compiles — **TRUE** (0.28 s vs ~2.5 s cold).  
3. Therefore realtime GPU decode on Xe-LP **as currently reachable** — **FALSE** (plugin/export blockers + ref-kernel path).

---

## What to keep using

| Keep | Do not treat as ship GPU path |
|------|-------------------------------|
| `spike/` recipes (ladder, pad, dynamo export, noise hoist) | NCHW rewrite ONNX as quality reference |
| G2 dynamo ONNX for ORT experiments | Legacy TorchScript decoder ONNX for OV-GPU |
| notes/25–34 + Fable 17–25 as provenance | GO language for this spike |

---

## Queue after close (Nexus-ordered)

1. **v1.1.8 approval** (oldest pending).  
2. **Response/chunk cache** design (Fable on greenlight; ship-path loop).  
3. **Repo commit** — spike tree, notes/25–34, Fable notes/statuses, WORKFLOW.md, research briefs as applicable.  
4. **Upstream filing session** — shape-JIT, f16 MatMul, f32 ref-conv (two-graph), conv-rank (+ family thesis); Architect text green-lit (`note_25`); Grok finalizes drafts; Nexus submits.  
5. **Parked:** componentized fork (O1–O4), RAPL, capacity-bisect, finer-T lattice.

---

## One-line close

**Well-instrumented negative GPU result + validated export architecture; ship stays on ort-cpu; cache next; filings ready; spike parked with full RCA.**
