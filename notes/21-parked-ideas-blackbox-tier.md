# notes/21 — parked ideas from pause-week voice session (black-box tier)

**Date:** 2026-08-05
**Author:** Claude (write-up), Wayne (originating ideas, voice session)
**Status:** ALL PARKED. No priority assigned yet — Wayne's explicit call.
Main thread (v1.1.8 landing, upstream issues) resumes first; these are
revisited depending on outcomes. Companion strategic note: notes/22.

## External corroboration — AMD MIOpen (Kokoro-FastAPI issue #454)

Independent confirmation of our notes/20 finding on different hardware
and a different stack (ROCm 7.2, Strix Halo gfx1151, PyTorch + MIOpen):

- Per-shape kernel cost: "tensor shapes vary by phoneme count — every
  unique input length produces a different shape"; first request per
  novel length 5–60 s (MIOpen kernel search), repeats 0.3–5 s.
- Their fix: MIOpen **persists its kernel cache to disk**
  (~/.config/miopen, ~2.4 MB for all lengths). `MIOPEN_FIND_MODE=2`
  forces reuse of the disk cache; a one-time warmup sweep of phoneme
  lengths 1–340 (~2 h) populates it permanently.

Contrast with us (notes/20): OpenVINO GPU shape kernels are in-memory,
per process, finite residency, NOT persisted by CACHE_DIR. Their
strategy (sweep once, disk forever) is exactly what OV-GPU denies us.
Also their shape space is cleaner (keyed ~input length); ours is keyed
on data-dependent OUTPUT sample count, so a length sweep wouldn't fully
cover it anyway.

**Action (Wayne: "hang on to that"):** cite #454 in our upstream
OpenVINO shape-JIT issue when we file — frames it as "AMD's stack
solves this class of problem with a persistent kernel disk cache;
intel_gpu lacks an equivalent." Turns "here's a slow thing" into
"here's a capability gap."

## Idea A — whole-request output cache (server-side)

Cache the FINISHED AUDIO keyed on the full determining tuple:
hash(exact text, voice, speed, backend, model version, format).
On hit: stream stored bytes, ZERO compute — no tokenization, no
duration predictor, no vocoder, no JIT. Disk-backed, so it survives
process restarts: the persistence OV denies us at the kernel level,
achieved at the response level instead.

- Server-side beats Open WebUI's client cache: shared across clients,
  survives, we control eviction.
- Implementation is a thin wrapper at the top of /v1/audio/speech:
  check cache dir → hit: return with X-Kokoro-Cache: hit → miss:
  synthesize as normal, write-through before returning.
- Needs: size bound + simple LRU eviction; model version folded into
  the key for invalidation.
- Honest limit: helps EXACT repeats only. Pairs well with the ov-gpu
  cold problem (repeats free; only genuinely novel text pays JIT).
- Store AUDIO (wav or encoded), NOT the spectrum — see rejected ideas.

Backend-agnostic, helps ort-cpu and ov-gpu alike. Of the session's
ideas, highest value-to-effort.

## Idea B — chunk-level cache (sentence granularity)

Finer version of A. The server ALREADY chunks text at sentence
boundaries before synthesis, so key the cache per chunk
(chunk text, voice, speed, ...) instead of per request. A novel
paragraph that reuses a previously seen sentence stitches cached audio
for the repeat and synthesizes only the fresh sentences → partial
reuse on overlapping traffic (boilerplate, intros, notification lines).

Sentence is the sweet spot: small enough to hit on real overlap, large
enough that each cached unit was synthesized as one prosodic whole, so
stitches land at natural sentence boundaries and stay seamless.

## Idea C — output-shape bucketing + pad-trim reuse

(Parked earlier in the session; recorded here in full.)

Mirror the existing TOKEN-side padding on the OUTPUT side: snap real
content up to the nearest PRE-WARMED output sample count (lattice step
600 samples / 25 ms, notes/20), run that one warm shape, then reuse the
v1.1.1–v1.1.7 pad-trim machinery to peel the tail back to true length.
Key realisation (Wayne): the pad-tail cleanup is not just an artifact
fix — it is the enabling half of a warm-shape strategy, already built
and ear-validated, fails safe.

**The one missing piece:** force the compiled graph to emit a CHOSEN
fixed output frame count. Today the duration predictor inside the graph
decides frames from phonemes+speed and overrides us. Candidate levers
(unproven): (1) speed input as fine adjustment to land a text on a
target lattice step; (2) graph edit clamping/overriding the duration
predictor output; (3) an injected target duration if the architecture
exposes one.

Risks: padded output = more vocoder compute (measure, don't assume;
likely still a good trade vs 17–25 s cold); no restart persistence
(in-memory cache, notes/20); working set must fit under the eviction
bound (~70-novel-shape gauntlet evicted the first shape — capacity
bisect probe would size it; eviction looks recency-driven, not random:
phase-1 revisit_first cold, revisit_last warm).

## Rejected sub-ideas (recorded so we don't re-tread)

1. **Constant text PREFIX to stabilise shape.** Fails: warmth is keyed
   on TOTAL output sample count; fixed prefix + variable text still
   sums to a variable total. Pins nothing.
2. **Cache the SPECTRUM instead of audio (for idea A).** Fails for
   exact repeats: on every hit you'd still run the vocoder — which is
   where the shape-keyed JIT lives — paying the cost the cache exists
   to avoid. Storage doesn't rescue it (mel frames ≥ encoded audio).
   Spectrum caching only earns its keep for reusing the pipeline FRONT
   across requests that differ at the BACK (e.g. same text, different
   voice) — which needs a seam the monolithic export doesn't have.
3. **Spectrum-as-fingerprint for sub-sentence fragment reuse.** Fails
   on coarticulation: word audio is not a context-free Lego brick —
   neighbours and sentence prosody colour it, so acoustically matching
   fragments are rare and stitched mismatches sound like concatenative
   TTS seams. Also, identifying content from audio = running ASR on
   our own output to recover text we already have. The tractable form
   of the instinct is Idea B (sentence-chunk keys on INPUT text).

## E-core pinning (Wayne's question, answered)

Would pinning to an E-core help the cold/warm issue? Expectation: cold
JIT is compute-bound host CPU work (mostly single-threaded in the
wall-matched mode; a multi-threaded burst mode exists — phase-1 subset
with cpu ≈ 2× wall). An E-core (lower clocks, narrower core) would
likely STRETCH cold ~17 s → ~20–25 s, not shrink it; iGPU execution is
unaffected. Where E-core pinning could help is the steady WARM path —
freeing P-cores under the shared 15 W RAPL budget. For minimising cold,
prefer the JIT landing on a P-core. Natural held-fixed variable in the
planned RAPL stress experiment; not a v1.1.8 blocker.

## Organising insight of the session

Every blocked idea (vocoder spectrum warmup, output-length control,
intermediate/spectrum caching) died on the SAME wall: the ONNX export
is one fused graph — text in, waveform out, no seams. Every idea that
SURVIVED (ideas A and B) treats the model as a black box and works
around it. Black-box strategies: cheap, unblocked. Seam-requiring
strategies: all wait on one structural decision. That decision is
notes/22.
