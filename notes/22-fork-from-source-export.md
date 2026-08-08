# notes/22 — strategic fork: from-source componentized OpenVINO export

**Date:** 2026-08-05
**Author:** Claude (write-up), Wayne (originating question + framing)
**Status:** FORK UNDER CONSIDERATION. Decision deferred to Wayne on
resume, with real thought — not made in this session. Companion:
notes/21 (parked black-box ideas).

## Wayne's question

"Are we working with the right model? Are we too many steps away from
the original — and if we went back to the source, could we make it an
OpenVINO version, exported how WE want it?"

## Reframing: the monolith is an EXPORT property, not a model property

- Our surgical edits (3D→4D resize, static-rank STFT) are
  representation-equivalent — we did not change what the model
  computes. Behaviourally we are essentially AT the original numerics.
- The constraint that blocked every seam-requiring idea in notes/21 —
  one fused graph, text in / waveform out — was baked in by WHOEVER
  exported the ONNX we inherited, not by Kokoro itself and not by us.
- Kokoro's PyTorch source is NOT a monolith: text encoder, duration
  predictor, acoustic side, vocoder are separable modules. The seams
  exist upstream; the export we adopted erased them.

## The fork (precisely stated)

NOT "leave OpenVINO" and NOT "run PyTorch in production" — that would
surrender the iGPU offload premise (PyTorch's Intel-GPU path is far
less mature than OpenVINO; OV is the one stack proven to compile and
run this model on Xe-LP — our own hard-won result).

The fork is: start from PyTorch source and do OUR OWN conversion into
OpenVINO, exported as SEPARATE components with seams we draw
deliberately — e.g. front-end (text→features + duration predictor
exposed) and vocoder (features+voice→audio) as distinct OV models with
inputs/outputs/shapes we define. Still OpenVINO, still the iGPU, still
the 15 W box. "It's an OpenVINO export" — on our terms.

## Feasibility on Wayne's machinery: YES

Export ≠ training ≠ inference. Converting an 82M-parameter model is a
one-time, offline, CPU-side trace-and-write job — laptop-class.
bdk-server (or any of Wayne's machines) is sufficient. No bigger iron
needed. The only cost is environment setup (a proper PyTorch env for
the export step; possibly PyTorch→ONNX→OV per piece) — a chore, not a
horsepower problem.

## Structural control: YES — it is the deliverable

Exporting from source means WE choose the cut points, the component
inputs/outputs, names, and shapes. That directly unblocks the notes/21
seam tier:
- vocoder warmup via a real spectrum/feature input (there is now a
  front door);
- output-length control (the duration predictor becomes a visible,
  steerable piece);
- intermediate caching across voices (a defined seam to cache at).

**Honest boundary:** export controls carving and wiring, not kernel
compilation. The GPU plugin's shape-keyed in-memory JIT (notes/20)
still applies PER COMPONENT. More compiled models, not fewer — verify
the cold cost doesn't multiply across pieces.

## Costs, named

1. Redo the export/bring-up work from scratch.
2. Re-apply or re-solve the resize/STFT class of fixes on the new
   export — re-work, not re-discovery (we understand them cold).
3. Real engineering time: foundational redo, not a tweak.
4. Per-component shape JIT (above).

## Honest scoreboard (why the fork is on the table)

We can make it work as-is. Is it efficient? No. ov-gpu is CORRECT but
slow: cold JIT per novel shape, no persistence across restarts,
ort-cpu remains the product default. We have been building
increasingly clever workarounds around a fundamentally awkward
artifact. The fork attacks the root instead of the symptoms — with the
honest caveat that it UNBLOCKS the ideas that might make it efficient;
it does not by itself guarantee efficiency. It is still a bet.

## De-risk spike (proposed first step if/when resumed)

Before committing to a full redo: export JUST the vocoder from source
as a standalone OV component and run it on ov-gpu. Cheap, and answers
most of the viability questions (does the per-piece export compile?
does the resize/STFT class of issue recur? what does per-component
cold cost look like?) without redoing everything.

## Three coherent futures (decision menu for Wayne)

1. **Stay as-is + black-box tier.** Ship notes/21 ideas A/B (caches),
   keep the iGPU, accept the seam tier stays blocked. Cheapest, lowest
   risk.
2. **PyTorch runtime.** Gains seams, loses the iGPU premise — the
   project quietly becomes a CPU project. Not favoured; recorded for
   completeness.
3. **Componentized OV export from source (THE FORK).** Keeps the
   premise, creates the seams, unblocks the whole tier at once.
   Highest effort; the one move that changes the game rather than
   working around it.

## Pause framing (Wayne's, verbatim intent)

The current ONNX fork is **PAUSED, not stopped** — deliberately
parked, fully documented, standing on its own results. The original
project premise was "it can't be done / hasn't been done / probably a
waste of time — do it anyway," and that bet produced first verified
Kokoro inference on Xe-LP. Diving into a fresh from-source effort is
the SAME bet that already paid off once: earned optimism, not blind
optimism. Real thought goes into the pause and the fork on resume, not
drift.

## State parked on pause (nothing lost)

Main-thread items still pending, unchanged by this note:
1. Wayne approve/reject KOKORO_WARM_TEXT → v1.1.8 lands (docs-only
   fallback ready).
2. If accepted: Grok smoke test (fox warm-text pin → first HTTP request
   warm ~3 s).
3. Upstream OpenVINO shape-JIT issue draft — NOW to include the AMD
   MIOpen #454 disk-cache contrast (notes/21). Two earlier issue drafts
   (f16 MatMul; f32 convolution_gpu_ref) still cleared for filing.
4. Repo commit: v1.1.7 + notes 10–18 (now +19–22).
5. Optional capacity-bisect probe (eviction bound; also sizes idea C's
   working set).
6. RAPL stress experiment (E-core affinity held fixed — notes/21).
