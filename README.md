# kokoro-igpu

Proof-of-concept: run **Kokoro TTS** on Intel integrated GPUs via OpenVINO, with an honest measurement bar and a working OpenAI-compatible server for Open WebUI.

This is not a claim that iGPU is the fastest path on every machine. On the validation host (Alder Lake UHD `8086:46b3`, Xe-LP) the **product default is ORT-CPU**. The OpenVINO GPU path is real, optional, and documented with limits.


## Current status (2026-08-07)

Server **v1.1.8** (ship path): OV pad-tail trim (ear-validated through v1.1.5), Open WebUI wiring notes, optional `KOKORO_WARM_BUCKETS` (near-capacity real text) and **`KOKORO_WARM_TEXT`** (exact phrase pins).

**Warm honesty (notes/19–20):** ov-gpu warm is **shape-keyed** (output sample count), not bucket-wide and not content-transferring. Steady ~**0.9 RTF** is for **repeats of a warmed shape**. Varied Read Aloud still pays multi-second cold on novel shapes. `KOKORO_WARM_BUCKETS` does **not** make arbitrary traffic fast; use `KOKORO_WARM_TEXT` to pin demo sentences. **Product default remains ort-cpu** (RTF ~0.4).

Componentized decoder-export spike is **PARKED** (not GO) — see [notes/34-spike-closeout-summary.md](notes/34-spike-closeout-summary.md).

Field issues closed: pad moan (server), Read Aloud skips (WebUI **Response Splitting** —
use **None/Paragraphs** with ov-gpu; Punctuation is fine on ort-cpu).

- Spike closeout: [notes/34-spike-closeout-summary.md](notes/34-spike-closeout-summary.md)
- Dual spike statuses: [notes/33-spike-status-grok.md](notes/33-spike-status-grok.md), [notes/33-spike-status-fable.md](notes/33-spike-status-fable.md)
- Earlier rollup: [notes/17-repo-status-summary.md](notes/17-repo-status-summary.md)
- Evidence WAVs + sanitized trim logs: `artifacts/v112`–`v115`, `artifacts/logs/` (Git LFS)
- Models: download locally (not in git); see below

## What this repo proves

- Stock Kokoro ONNX fails to compile on OpenVINO GPU because of **3D `linear_onnx` Resize**.
- OpenVINO partitions also fail on **dynamic-rank STFT** boundaries.
- Two small graph edits fix compile:
  1. lift the sine-generator linear Resizes from 3D to 4D
  2. stamp STFT output as static rank-4
- After patching, whole-graph OpenVINO GPU execution is real:
  - `EXECUTION_DEVICES=['GPU.0']`
  - GPU kernels in profiles
  - `intel_gpu_top` RCS busy
  - human-verified intelligible speech
- On Alder Lake UHD, GPU is **correct enough to demo** but **not a latency win** (RTF ~2.4–2.9 vs CPU ~0.40–0.45).
- GPU f16 compiles then hard-fails at infer on a MatMul shape check.
- A commercial “Intel iGPU Kokoro” container was previously shown to be CPU work behind a GPU provider label. This repo refuses that class of claim.

## Validation host

- CPU: 12th Gen Intel Core i3-1215U
- iGPU: UHD Graphics `8086:46b3` (Xe-LP)
- Stack: OpenVINO `2026.2.1`, `onnxruntime-openvino` `1.24.1`, Python 3.12, Ubuntu 24.04

Contributor write-ups:

- [Fable/CONTRIBUTOR-Claude.md](Fable/CONTRIBUTOR-Claude.md) — diagnosis, graph surgery, tooling
- [Grok/CONTRIBUTOR-Grok.md](Grok/CONTRIBUTOR-Grok.md) — hardware validation, metrics, Open WebUI path

Phase notes live under [`notes/`](notes/).

## Results snapshot

| Path | Role | RTF on real text | Notes |
|------|------|------------------|-------|
| **ORT-CPU** | **default product** | ~0.40–0.45 | clean reference audio |
| OV-CPU | optional | ~parity with ORT | strong waveform parity after patch |
| OV-GPU f32 | experimental | ~2.4–2.9 | real iGPU offload; ~2 dB quieter, faintly muffled |
| OV-GPU f16 | broken | n/a | compile OK, infer MatMul failure |

Sample audio (fox sentence / server path) is in [`artifacts/samples/`](artifacts/samples/).

## Quick start

### 1. Clone and Python env

```bash
git clone https://github.com/bdk38/kokoro-igpu.git
cd kokoro-igpu

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# system phonemizer backend
sudo apt-get install -y espeak-ng
```

### 2. Enter project env

```bash
source scripts/env.sh
```

### 3. Download model weights

Weights are **not** in git.

```bash
./scripts/download_models.sh
```

If the default release URLs move, override:

```bash
KOKORO_ONNX_URL=... VOICES_URL=... ./scripts/download_models.sh
```

You need:

- `models/kokoro-v0_19.onnx`
- `models/voices-v1.0.bin`

### 4. Patch for OpenVINO GPU/CPU

```bash
python scripts/patch_kokoro_v2.py \
  --model models/kokoro-v0_19.onnx \
  --output models/patched/kokoro-v0_19.gpu4d.stft.onnx \
  --stamp-stft
```

### 5. Hardware / OpenVINO sanity

```bash
./scripts/check_hw.sh
python scripts/check_openvino.py
python scripts/smoke_openvino_gpu.py
```

### 6. Product server (ORT-CPU default)

```bash
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

```bash
curl -s http://127.0.0.1:8880/health
curl -s http://127.0.0.1:8880/v1/audio/voices | head
curl -s -X POST http://127.0.0.1:8880/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"kokoro","input":"Hello from Kokoro.","voice":"af_bella","response_format":"wav"}' \
  --output out.wav
```

#### Optional TTS response/chunk cache (env)

Opt-in disk cache for TTS audio (`KOKORO_TTS_*`). Off by default. Distinct from `KOKORO_CACHE`, which remains the OpenVINO compile-cache directory. Schema version 2 (invalidates v1 entries): each synthesis chunk is quantized to int16 PCM and dequantized before concat so cached and uncached assembly share one path.

| Variable | Default | Meaning |
|----------|---------|---------|
| `KOKORO_TTS_CACHE` | `0` | `0` off, `1` on |
| `KOKORO_TTS_CACHE_DIR` | `/data/intel-igpu-tts/cache/tts` | response/chunk store root |
| `KOKORO_TTS_CACHE_MAX_MB` | `500` | lazy size cap (oldest mtime first) |
| `KOKORO_TTS_CACHE_TIER` | `both` | `response` (C1 full request) \| `chunk` (C2 per chunk_text token-id list) \| `both` |

When enabled, responses may include `X-Kokoro-Cache: hit`, `partial` (some chunks reused), or `miss`.

### 7. Experimental iGPU server

```bash
KOKORO_BACKEND=ov-gpu \
KOKORO_MODEL=models/patched/kokoro-v0_19.gpu4d.stft.onnx \
KOKORO_GPU_PRECISION=f32 \
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

Watch `intel_gpu_top` while requesting speech. Expect higher RTF than CPU.

## Real-text A/B harness

```bash
python scripts/tts_harness.py \
  --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
  --voices models/voices-v1.0.bin \
  --voice af_bella \
  --text "The quick brown fox jumps over the lazy dog." \
  --backends ort-cpu,ov-cpu,ov-gpu \
  --gpu-precision f32 \
  --cache cache/openvino \
  --outdir artifacts/harness/fox_f32 \
  --runs 2
```

## Open WebUI

1. Run the server on the host (`0.0.0.0:8880`).
2. In Open WebUI Admin → Settings → Audio:
   - TTS Engine: **OpenAI**
   - API Base URL: `http://host.docker.internal:8880/v1` (Docker on same host)
   - API Key: any non-empty string
   - Model: `kokoro`
   - Voice: `af_bella` (or another voice / blend)
3. If the container cannot reach the host, allow Docker bridge traffic to port 8880.

The server accepts:

- plain Kokoro voices (`af_bella`, `af_nova`, …)
- OpenAI aliases (`alloy`, `nova`, …)
- weighted blends: `bf_isabella(1)+bf_emma(1)+af_heart(3)`

Response headers stay honest, e.g. `X-Kokoro-Backend`, `X-Kokoro-RTF`.

## Repository layout

```text
scripts/                 tools, patches, harness, server
notes/                   phase reports from the sandbox
Fable/                   Claude contributor write-up
Grok/                    Grok contributor write-up
artifacts/samples/       small curated audio samples
models/                  download targets (weights gitignored)
requirements.txt         runtime deps
```

## Important constraints

- **Provider name is never offload proof.** Require `intel_gpu_top`, `EXECUTION_DEVICES`, or GPU kernel names in profiles.
- **Alder Lake Xe-LP is not a PyTorch XPU target.** This PoC is OpenVINO/ONNX-oriented.
- **Do not default to OV-GPU on this iGPU class** unless your measured RTF and listening tests say otherwise.
- Raw waveform correlation can look catastrophic when GPU audio is only a few percent longer. Align first; trust ears + spectral metrics.

## Upstream issues worth reporting

1. GPU f16 MatMul shape-validation failure on the patched graph after successful compile.
2. f32 convolutions falling back to `convolution_gpu_ref__f32` on Xe-LP for this model (dominates RTF > 1).
3. Residual GPU fidelity delta vs CPU (~2 dB down, mild muffling).
4. Broader intel_gpu gaps that forced surgery: 3D `linear_onnx` Interpolate, dynamic-rank partition Parameters.


## Contributors

Human project lead: **[@bdk38](https://github.com/bdk38)**

AI contributors (full write-ups in-repo):

- **Claude / Fable (Anthropic)** — diagnosis, graph surgery, tooling  
  See [Fable/CONTRIBUTOR-Claude.md](Fable/CONTRIBUTOR-Claude.md)
- **Grok (xAI)** — hardware validation, metrics, Open WebUI path  
  See [Grok/CONTRIBUTOR-Grok.md](Grok/CONTRIBUTOR-Grok.md)

Also see [CONTRIBUTORS.md](CONTRIBUTORS.md) for how credit is represented (including why GitHub’s automatic Contributors graph is incomplete for AI collaborators).

## License

MIT — see [LICENSE](LICENSE).

Kokoro model weights are third-party assets. Download and use them under their own upstream terms.
