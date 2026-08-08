# Contributor: Grok (xAI)

**Role:** Hardware validation, measurement, phase reports, Open WebUI integration, and live product path
**Model:** Grok 4.5 (xAI), via Open WebUI + Open Terminal on bdk-server
**Collaboration model:** Human project lead directed the investigation and made all decisions. Claude (Fable) performed diagnosis and authored the graph-surgery tools, harness, and server skeleton. Grok executed every hardware test on the real machine, wrote the phase notes under `notes/`, reconciled metrics against human listening, wired Open WebUI, patched production compatibility issues found in live use, and validated both the ORT-CPU product path and the experimental OV-GPU path end to end. Nothing here is claimed from simulation.

---

## Summary of the problem (as found on this host)

Kokoro TTS could not be proven on Intel Alder Lake UHD (`8086:46b3`, Xe-LP) through OpenVINO:

1. Stock ONNX exports failed to compile/load on OpenVINO GPU with:
   ```
   Mode 'linear_onnx' supports only 2D or 4D, 5D tensors
   ```
2. OpenVINO CPU / HETERO / AUTO paths also failed around dynamic-rank STFT partition boundaries.
3. A commercial Docker image advertised as Intel iGPU-accelerated Kokoro was previously shown on this project to be CPU execution behind a GPU provider label. That set the evidentiary bar for this sandbox: provider names are never offload proof.

The project goal was not "make a demo that claims GPU." It was:

- prove or disprove real iGPU offload with engine counters,
- keep an honest map of quality and speed,
- ship a usable OpenAI-compatible TTS path for Open WebUI if the iGPU path was not the winner.

---

## What I contributed

### Sandbox bring-up and measurement discipline

- Host inventory and device visibility checks (DRI, OpenCL, Level Zero, `intel_gpu_top`, OpenVINO `GPU` device).
- Project layout under `/data/intel-igpu-tts` (venv, models, scripts, logs, artifacts, notes).
- Baseline scripts and gates:
  - `scripts/check_hw.sh`
  - `scripts/check_openvino.py`
  - `scripts/smoke_openvino_gpu.py`
  - `scripts/test_kokoro_openvino_ep.py`
- Locked the rule used throughout: **no offload claim without** one or more of
  - `intel_gpu_top` engine busy,
  - OpenVINO `EXECUTION_DEVICES`,
  - per-op GPU kernel types in profiles.

### Phase execution and reports (all on real silicon)

| Phase | Note | What Grok did |
|-------|------|----------------|
| 0 inventory | `notes/00-host-inventory.txt` | Captured host/GPU/driver/model state |
| status | `notes/01-status.md` | Living gate board |
| 4 stock OV EP | `notes/02-phase4-openvino-ep.md` | Proved stock v0.19 fails OV GPU/CPU/HETERO/AUTO; ORT-CPU works |
| 4b v1 variants | `notes/03-phase4b-v1-variants.md` | Exhausted onnx-community v1.0 FP/quant exports; same 3D linear Resize wall |
| 4c Resize patch | `notes/04-patch-resize-results.md` | Ran Claude's v1 surgery; confirmed Resize wall cleared, STFT wall exposed |
| 4d STFT patch | `notes/05-patch-v2-stft-results.md` | Ran Claude's v2 surgery; sessions create; first quality/offload matrix |
| 4e direct OV | `notes/06-ov-direct-results.md` | Whole-graph `ov.Core` path; first hard proof of GPU kernels + RCS busy |
| 4f real text | `notes/07-harness-realtext.md` | Ran harness fox/long/f16; stretch-aligned metric reconciliation vs ears |
| 5 server | `notes/08-phase5-server.md` | Validated OpenAI-compatible API on ORT-CPU |
| 6 Open WebUI | `notes/09-phase6-openwebui.md` | Wired production Open WebUI to local Kokoro and proved read-aloud |

### Metric work that changed the conclusion

Early GPU waveform correlation looked catastrophic (`corr ≈ 0`). Human listening said the speech was the same utterance, only quieter and faintly muffled. I reconciled that:

- GPU audio is ~3% longer (duration/rounding drift),
- unaligned sample/mel compares overstate damage,
- after time-stretch + optional lag:
  - GPU is about **1.8–2.0 dB quieter**,
  - residual spectral softening matches "faintly muffled,"
  - raw waveform correlation is a bad speech-identity metric when durations differ.

That downgraded GPU from "wrong audio" to **"usable but slower and slightly duller"** — important for honest packaging, not marketing.

### Product path: server + Open WebUI

Claude authored `scripts/kokoro_server.py`. I:

1. Installed runtime deps and validated `/health`, `/v1/models`, `/v1/audio/voices`, `/v1/audio/speech`.
2. Confirmed ORT-CPU product numbers on real text:
   - RTF ≈ **0.40–0.45**
   - clean WAV artifacts under `artifacts/server/`
3. Wired Open WebUI v0.11.0:
   - persistent config → OpenAI TTS engine
   - base URL `http://host.docker.internal:8880/v1`
   - model `kokoro`, default voice `af_bella`
4. Made Docker reach the host server:
   - bind `0.0.0.0:8880`
   - UFW allow from `172.16.0.0/12` to port 8880
5. Proved the full proxy path:
   - container → Kokoro direct WAV OK
   - Open WebUI `/api/v1/audio/speech` → MP3 OK

### Live-use fixes after read-aloud broke

Open WebUI read-aloud returned:

```text
External: 400 Bad Request url=http://host.docker.internal:8880/v1/audio/speech
```

Root cause found in request history and model metadata:

- model-level / legacy voices used **Kokoro-FastAPI blend syntax**, e.g.
  `bf_v0isabella(1)+bf_emma(1)+af_heart(3)`
- older aliases like `bf_v0isabella` are not present under that exact name in `voices-v1.0.bin`
- Open WebUI also sends extra fields (`volume_multiplier`, `normalization_options`, …)

I patched `scripts/kokoro_server.py` to:

- parse weighted blends `a(w)+b(w)+...` and style-mix the voice rows,
- alias common `*_v0*` names onto current voice ids,
- ignore unknown request fields,
- keep honest `X-Kokoro-*` headers and RTF logs.

Retest after patch:

- direct blend request → HTTP 200, RTF ~0.41
- Open WebUI proxy with blend voice → HTTP 200 `audio/mpeg`

### Live OV-GPU demo path

For the human `intel_gpu_top` / htop session I flipped the running server from product ORT-CPU to experimental OV-GPU:

```bash
KOKORO_BACKEND=ov-gpu \
KOKORO_MODEL=/data/intel-igpu-tts/models/patched/kokoro-v0_19.gpu4d.stft.onnx \
KOKORO_GPU_PRECISION=f32 \
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

Health reported `backend=ov-gpu`, warmup compiled a bucket on GPU, and live read-aloud produced visible iGPU movement. That closed the loop from "compile error" to "hear it while watching the engines."

---

## Results measured on bdk-server (i3-1215U / UHD 46b3)

### Compile / load

| Graph | ORT-CPU | OV-CPU | OV-GPU |
|-------|---------|--------|--------|
| stock v0.19 / v1.0 exports | OK | fail (STFT rank / partition) | fail (3D linear Resize) |
| `kokoro-v0_19.gpu4d.onnx` (Resize only) | OK | fail STFT rank | fail STFT rank |
| `kokoro-v0_19.gpu4d.stft.onnx` (Resize + STFT rank) | OK | OK | OK compile; f16 infer fails |

### Real-text harness (patched model, af_bella)

Fox sentence:

- ORT-CPU RTF ≈ 0.41
- OV-CPU RTF ≈ 0.42, strong parity
- OV-GPU f32 RTF ≈ 2.94
- OV-GPU f16: compile OK, infer crash (`MatMul` dim mismatch)

Long passage:

- ORT-CPU RTF ≈ 0.42
- OV-CPU RTF ≈ 0.39
- OV-GPU f32 RTF ≈ 2.44

### Offload proof (OV direct GPU f32)

- `EXECUTION_DEVICES=['GPU.0']`
- profile dominated by `convolution_gpu_ref__f32` (and related GPU ops)
- `intel_gpu_top` RCS ~95–99% during infer windows
- first verified real Kokoro inference on this iGPU class

### Ears + aligned metrics (GPU f32 vs ORT-CPU)

- intelligible, correct speech, no crackle/artifacts
- ~1.8–2.0 dB quieter
- faintly muffled / spectrally softer
- ~3% longer waveform before alignment

### Product integration

- OpenAI-compatible server on `:8880`
- Open WebUI read-aloud works on ORT-CPU and OV-GPU
- blend voices and OpenAI aliases supported

---

## Decisions locked

1. **Default product backend = ORT-CPU**
   - RTF ~0.40–0.45
   - clean reference audio
   - original or patched model both fine; original is the fidelity reference
2. **OV-CPU** is a near-parity alternative if an OpenVINO-only runtime is desired.
3. **OV-GPU** is optional/experimental only:
   - real offload, real speech
   - not a latency win on Alder Lake UHD (RTF 2.4–2.9)
   - mild level/timbre delta
   - f16 path hard-fails at infer
4. Never ship GPU as default on this class of iGPU without a measured RTF < 1 and closer fidelity.

---

## Code / artifacts I own or heavily exercised

Authored or substantially extended in-tree:

- phase notes `notes/00` through `notes/09`
- host inventory and status board
- Open WebUI wiring procedure and validation artifacts
- production compatibility patch in `scripts/kokoro_server.py` (blend voices, aliases, extra-field tolerance)
- live backend flip validation (ORT-CPU ↔ OV-GPU)

Executed and reported from Claude-authored tools:

- `scripts/patch_kokoro_resize.py`
- `scripts/patch_kokoro_v2.py`
- `scripts/test_kokoro_ov_direct.py`
- `scripts/tts_harness.py`
- base `scripts/kokoro_server.py`

Key artifacts:

- `models/patched/kokoro-v0_19.gpu4d.onnx`
- `models/patched/kokoro-v0_19.gpu4d.stft.onnx`
- `artifacts/harness/fox_f32/`, `long_f32/`
- `artifacts/server/` (API + Open WebUI proxy samples)
- logs under `logs/` for every phase gate

---

## Open issues worth upstreaming (OpenVINO)

These are the breadcrumbs for Intel / OpenVINO, not excuses:

1. **FP16 MatMul validation/runtime bug on this patched graph**
   - compiles for GPU f16
   - fails at first infer:
     `MatMul_*: Incompatible MatMul matrix dimension`
   - same graph runs f32
2. **f32 convolutions fall to `convolution_gpu_ref__f32` on Xe-LP**
   - dominates RTF > 1
   - no competitive optimized f32 1D-conv path observed for this model
3. **GPU fidelity delta vs CPU**
   - reproducible ~2 dB level drop + mild muffling
   - finite, no NaNs on real-text f32 path after patches
4. Underlying limitations that forced graph surgery (still true upstream):
   - 3D `linear_onnx` Interpolate unsupported on intel_gpu
   - dynamic-rank Parameters rejected at partition boundaries

Claude diagnosed and fixed (1)/(4) at the model layer where possible; I measured and documented the residual runtime issues on this exact device/stack (OpenVINO 2026.2.1, ORT-OV 1.24.1, UHD 46b3).

---

## Lessons worth keeping

- **Provider labels lie easily.** Require engines, execution devices, or kernel names.
- **Fail loud beats fail silent.** Stock GPU session create failing immediately was healthier than a green "GPU" badge on CPU work.
- **Metrics can invent failures.** Duration drift turned good speech into `corr ≈ 0` until stretch-alignment and ears were applied.
- **Two small graph edits unlocked a wall everyone treated as permanent.** Resize rank lift + STFT rank stamp took Kokoro from "cannot compile" to "whole-graph GPU with busy RCS."
- **Real offload is not automatically a product win.** On this UHD, CPU remains faster and cleaner; GPU is the scientific/demo path.
- **Integration bugs are part of the research.** Blend-voice 400s only appeared after Open WebUI read-aloud hit model-level legacy voice strings.

---

## How to reproduce the validated paths

Enter sandbox:

```bash
source /data/intel-igpu-tts/scripts/env.sh
```

Product server (default):

```bash
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
curl -s http://127.0.0.1:8880/health
```

Experimental iGPU server:

```bash
KOKORO_BACKEND=ov-gpu \
KOKORO_MODEL=/data/intel-igpu-tts/models/patched/kokoro-v0_19.gpu4d.stft.onnx \
KOKORO_GPU_PRECISION=f32 \
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

Harness:

```bash
python scripts/tts_harness.py \
  --model models/patched/kokoro-v0_19.gpu4d.stft.onnx \
  --voices models/voices-v1.0.bin \
  --voice af_bella \
  --text "The quick brown fox jumps over the lazy dog." \
  --backends ort-cpu,ov-cpu,ov-gpu \
  --gpu-precision f32 --cache cache/openvino \
  --outdir artifacts/harness --runs 2
```

Open WebUI:

- TTS engine OpenAI
- base URL `http://host.docker.internal:8880/v1`
- model `kokoro`
- voice `af_bella` or a blend such as `bf_isabella(1)+bf_emma(1)+af_heart(3)`

---


---

## Dual-product era (2026-08 — S0 / I0 / ship)

After the early ONNX/iGPU proof and trim/WebUI arcs, the same collaboration model continued through:

| Arc | Notes (approx) | Orchestrator role |
|-----|----------------|-------------------|
| Warm honesty / shape warm | 19–20, 35 | Measurement discipline; real-path warm vs zeros |
| TTS cache C1+C2 | 39–44 | Probe matrices, ship v1.2.0, WebUI soak |
| Decoder componentized spike | 25–34 | Spike isolation, go/kill write-ups → **PARKED** with RCA |
| S0 official GenAI 2026.3 | 36, 45–53 | Side-env probes, offload proof, ears → **`S0-GO-product`** |
| I0 integration | 54–67 | Backend `ovgenai-*`, served RTF, regression, legacy ov-gpu → **`I0-GO-default-candidate`** |
| Dual-product boundary | 70–76 | PoC face ort-cpu + GenAI appliance; R0/R1 stranger gates; filings VERIFY then **PARKED** |
| Close-out | 77, Fable note_36 | R2 smoke PASS; board empty |

**Products shipped (stranger-reproducible):**

- **PoC** — https://github.com/bdk38/kokoro-igpu tag `poc-complete` (default `ort-cpu`)
- **Prototype appliance** — https://github.com/bdk38/kokoro-igpu-genai tag `prototype-complete` (default `ovgenai-gpu`)

**Standing methods (unchanged):** gates before numbers; cold/steady never mixed in product claims; ears bind quality; park negatives with evidence; clone-and-hear beats prose.


## Acknowledgments

The project lead set the only standard that mattered: hard offload proof over marketing claims, and stop if packaging became dishonest or useless. Claude Fable owned the diagnosis and the graph surgery that made GPU compile possible; the phase notes record where predictions were right and wrong on purpose. My job was to make the machine tell the truth — with logs, counters, ears, and a path you can actually press Read Aloud on.

---

*This document was written by Grok. It covers the sandbox arc from host inventory through dual-product ship (PoC + GenAI appliance) and orchestrator close-out notes/77. Operational cleanup of unrelated host services is intentionally omitted.*
