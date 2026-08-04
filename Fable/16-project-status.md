# Project Status — Kokoro TTS on Intel iGPU via OpenVINO

*Status as of 2026-08-04 (evening). Supersedes `09-project-status.md`;
written by Claude, for the project lead and Grok. Companion to numbered
notes 10–15.*

## Where we are

The core result is unchanged and now better productized: the Alder Lake
UHD iGPU runs Kokoro whole-graph via the patched model
(`kokoro-v0_19.gpu4d.stft.onnx`), with hard offload proof, at f32-ref-
kernel speed (RTF ~4–6 on this host under the current server; upstream
OpenVINO limits unchanged). The shipped server is
`scripts/kokoro_server.py` **v1.1.5**, live-validated end to end on
ov-gpu, including through Open WebUI.

Since the last status, two field-quality threads opened and both are now
**closed**:

**1. The pad-tail breath/moan — closed at v1.1.5.** OV bucket-padding
makes the vocoder render trailing pad tokens as a weak voiced burst
after a quiet gap. Five versions of an energy-gated trim were tested
against a fixed probe set with per-chunk debug logging and human ear
verdicts. The surviving ruleset strips a trailing RMS group only if it
is simultaneously **weak** (peak < 0.9× speech reference), **short**
(< 0.6 s), **detached** (pre-gap ≥ 0.15 s), and inside the pad search
window; the speech reference is the p90 of the clip's loud frames with a
hard silence floor below which trimming is refused. Every threshold
traces to a measured, ear-confirmed number (moans 0.23–0.77× / 0.12–
0.40 s / gaps 0.40–0.78 s; real speech ≥ 1.05× or > 0.6 s or attached
within ~0.10 s — a plosive closure). Final validation: all seven probe
clips PASS by ear, and all seven predicted cut durations matched
measured to the hundredth of a second.

Two intermediate hypotheses were shipped, falsified by measurement, and
removed — recorded here because the negative results are part of the
repo's evidence: cutting at the *first sustained quiet* (v1.1.1) fired
on natural comma pauses and skipped mid-sentence; a *terminal-silence
keep gate* (v1.1.4) protected only ear-confirmed moans and never real
speech, because Kokoro renders final words attached to preceding speech
while pad bursts are pushed 0.4+ s away. The known residual envelope — a
real word that is weak AND short AND detached — has never appeared in
any probe, including one engineered to produce it; `tail=` telemetry
stays in the debug log as evidence collection should it ever occur, in
which case the next discriminator is spectral, not another threshold.

**2. Open WebUI Read Aloud skips — closed as configuration, note 15.**
The mid-passage skips were never server-side after v1.1.2: an A/B on an
identical server build showed Open WebUI's **Response Splitting =
Punctuation** (the default) fires one slow request per sentence, and
under ov-gpu RTF ≫ 1 the client drops late segments. **None** or
**Paragraphs** deliver the same text complete and clean. Guidance is now
baked into the server's wiring docstring: Punctuation is right for
ort-cpu (fast first-audio); None/Paragraphs for ov-gpu. The OV infer
lock (v1.1.2) remains necessary — it converted `Infer Request is busy`
500s into clean queueing — but queueing cannot fix a client that won't
wait; the settings change does.

Also landed along the way: voice aliases and Kokoro-FastAPI-style
weighted blends (Grok), tolerant request parsing for Open WebUI's extra
fields, per-group trim debug logging (`KOKORO_TRIM_DEBUG=1`), and the
loud-frame reference fix that also killed nonsense warmup ratios.

## What we learned (additions)

**Instrument first, then let ears falsify.** The trim converged in one
day because every version logged per-group evidence (peak/ref, gap,
tail, verdict) and every listen test came back attached to those
numbers. Twice a plausible gate was killed not by argument but by its
own log: every group it acted on was ear-identified as the opposite of
its assumption.

**Predict before you probe.** From v1.1.5 onward the loop stated
expected cut durations in advance; seven-for-seven matches is what
"understood mechanism" looks like, and a miss would have localized the
error immediately.

**Structure separates what thresholds cannot.** "port" at 0.36× and a
moan at 0.70× are inseparable by level or duration; the 0.10 s stop-
closure vs 0.46 s pad gap separates them perfectly. When two classes
overlap on one axis, find the structural axis instead of tuning the
overlapping one.

**The client is part of the system.** The longest-lived "bug" in the
project was a settings dropdown in someone else's UI. Provider names
aren't offload proof, and server 200s aren't playback proof.

## Outstanding items

Immediate: commit to the repo — server v1.1.5 (with the doc-only
Response Splitting amendment), notes 10–16, probe scripts
(`probe_v112/113/115.py`), and the artifact WAV sets that back the trim
evidence chain. Then paste logs into the two OpenVINO issue drafts (f16
MatMul failure; f32 ref-conv performance with fidelity delta), add the
repo link, file, and cross-link.

Queued, decided but not built (unchanged from 09): server response
cache (LRU on hashed text/voice/speed); `KOKORO_CPU_THREADS` /
`KOKORO_CORE_TYPE` env vars (ECORE_ONLY scheduling); the
concurrency/power stress-test spec (`stress-ng` CPU load vs GPU clocks
and RTF — the shared-RAPL experiment, worth running before the repo
ships its conclusions).

Open questions, experiment-or-document (unchanged): partial-offload
graph split (`split_kokoro.py`); optional `probe_tts_ov.py`
generalization.

The honest close still holds, with one addendum: the dormant-silicon
thesis proved out, the product ships on the proven path, and the field
issues that surfaced in real use were run to ground with the same
standard of proof as the offload itself — measured, predicted,
ear-confirmed, and documented, including the hypotheses that died.
