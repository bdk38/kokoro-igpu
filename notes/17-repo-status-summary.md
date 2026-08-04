# Repo status summary

**Date:** 2026-08-04  
**Server:** `scripts/kokoro_server.py` **v1.1.5**  
**Host class:** Intel Alder Lake UHD (Xe-LP), validated on i3-1215U / `8086:46b3`

This is the short public rollup. Full parallel write-ups (kept, not merged away):

- [notes/16-project-status.md](16-project-status.md) — Grok (measurement / validation)
- [notes/16-project-status-fable.md](16-project-status-fable.md) — Claude Fable (implementation / diagnosis)
- Contributor narratives: [Fable/CONTRIBUTOR-Claude.md](../Fable/CONTRIBUTOR-Claude.md), [Grok/CONTRIBUTOR-Grok.md](../Grok/CONTRIBUTOR-Grok.md)

---

## Result in one breath

Kokoro TTS runs with **real Intel iGPU offload** via OpenVINO after two graph edits (3D→4D linear Resize, STFT rank-4 stamp). Offload is proven (`GPU.0`, GPU kernels, RCS busy) and speech is ear-validated. On this UHD class, GPU is a **demo/offload path** (f32 RTF ~4–6), not the latency winner. **Product default remains ORT-CPU** (RTF ~0.4). An OpenAI-compatible server and Open WebUI wiring ship both backends.

Two field issues found in real Read Aloud use are closed:

1. **OV pad-tail breath/moan** — fixed in server trim **v1.1.5** (instrumented, predicted cuts, seven-clip ear PASS).
2. **Mid-passage Read Aloud skips** — not a trim bug after v1.1.2; Open WebUI **Response Splitting = Punctuation** × slow ov-gpu multi-POST. **None** or **Paragraphs** (single-block text) complete cleanly (`notes/15`).

---

## What to run

```bash
source scripts/env.sh

# Product default
export KOKORO_BACKEND=ort-cpu
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880

# iGPU demo (patched model required)
export KOKORO_BACKEND=ov-gpu
export KOKORO_MODEL=models/patched/kokoro-v0_19.gpu4d.stft.onnx
export KOKORO_GPU_PRECISION=f32
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

Open WebUI: TTS Engine OpenAI → `http://<host>:8880/v1`, voice e.g. `af_bella`.

| Backend | Response Splitting |
|---------|-------------------|
| ort-cpu | Punctuation OK (fast segments) |
| ov-gpu  | **None** or **Paragraphs** (avoid Punctuation skips under RTF ≫ 1) |

---

## Trim (v1.1.5) — closed

OV bucket padding only. Strip a trailing RMS group only if **weak** (peak < 0.9× ref) **and** **short** (< 0.6 s) **and** **detached** (pre-gap ≥ 0.15 s) **and** inside the pad window. Ref = p90 of loud frames; refuse trim if ref < 1e-3. ORT never pads → never trims.

Falsified and removed (documented on purpose): first-quiet cut (v1.1.1); terminal-silence keep (v1.1.4). Evidence: `notes/10`–`14`, `artifacts/v112`–`v115`, `scripts/probe_v11*.py`.

---

## Performance honesty

| Path | Role | RTF order | Notes |
|------|------|-----------|--------|
| ort-cpu | **default** | ~0.4 | fidelity reference |
| ov-cpu | optional | ~ORT | corr ~0.97 |
| ov-gpu f32 | demo | ~4–6 | real iGPU; quieter/muffled vs ORT |
| ov-gpu f16 | broken | — | MatMul infer failure (upstream candidate) |

Provider names are never offload proof; this repo requires devices, kernels, or `intel_gpu_top`.

---

## Phase gates (compact)

PASS: host iGPU stack, OV GPU smoke, patched compile, direct GPU offload proof, real-text listen, OpenAI server, WebUI wire, trim v1.1.5, skip-as-config.  
FAIL / limited: stock ONNX on OV GPU; f16 GPU; GPU latency win on Xe-LP.

---

## Repo layout (evidence)

| Path | Content |
|------|---------|
| `scripts/kokoro_server.py` | v1.1.5 server |
| `scripts/patch_*.py`, harness/tests | surgery + measurement tools |
| `scripts/probe_v11*.py` | trim regression probes |
| `notes/00`–`17` | full lab log + both status docs + this summary |
| `issues/` | OpenVINO issue drafts |
| `artifacts/v112`–`v115` | ear-evidence WAVs (Git LFS) |
| `models/` | weights via LFS or local download (see README) |

---

## Still open

1. File OpenVINO issues (f16 MatMul; f32 ref-conv / RTF>1 + fidelity).  
2. Optional: response cache, CPU pin env, power/RTF stress before freezing perf claims.  
3. Ops: systemd unit; production without `KOKORO_TRIM_DEBUG`.  
4. Research: partial offload / upstream kernel wins for Xe-LP.

---

## Credits

Human lead **bdk38**. Implementation/diagnosis **Claude Fable** (Anthropic). On-box validation/measurement/integration **Grok** (xAI). Details in `CONTRIBUTORS.md` and the two `notes/16-*` statuses.
