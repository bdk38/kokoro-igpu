# kokoro-igpu

**Kokoro-82M speaking on a budget Intel box** (Alder Lake UHD / Xe-LP class).

Two finished products share this repo:

| | **PoC (Product A)** | **Prototype (Product B)** |
|--|---------------------|---------------------------|
| What | Community **v0.19 ONNX** + graph surgery; OpenAI-compatible server | Official **OpenVINO GenAI** int8 pack on iGPU |
| Proof | You can **hear** it — CPU always; iGPU offload leg optional | Served steady RTF ~**0.73** on validation host |
| Default | **`ort-cpu`** (repo default) | `KOKORO_BACKEND=ovgenai-gpu` |

The PoC claim in one line: **CPU offload onto an Xe-LP iGPU that was said couldn’t do it — and you can run the proof.**  
Speed was never the PoC’s claim. Notes are the lab book; **audio from a clean install is the deliverable.**

Validation host: 12th Gen i3-1215U, UHD `8086:46b3`, Ubuntu 24.04, OpenVINO **2026.3** (+ GenAI for Product B).

---

## 1. Run the PoC (Product A)

### Install

```bash
git clone https://github.com/bdk38/kokoro-igpu.git
cd kokoro-igpu
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./scripts/download_models.sh
```

Build the GPU-friendly patched graph (needed only for the ov-gpu leg):

```bash
python scripts/patch_kokoro_v2.py \
  --model models/kokoro-v0_19.onnx \
  --output models/patched/kokoro-v0_19.gpu4d.stft.onnx \
  --stamp-stft
```

Hashes and roles: **[MODELS.md](MODELS.md)**.

### Start (CPU — always works)

```bash
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
# default KOKORO_BACKEND=ort-cpu
```

### Hear it

```bash
curl -sS -X POST http://127.0.0.1:8880/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"The quick brown fox jumps over the lazy dog.","voice":"af_bella","response_format":"wav"}' \
  -o fox.wav
# play fox.wav
```

### iGPU offload leg (optional proof)

```bash
KOKORO_BACKEND=ov-gpu \
KOKORO_MODEL=models/patched/kokoro-v0_19.gpu4d.stft.onnx \
KOKORO_GPU_PRECISION=f32 \
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

Watch `intel_gpu_top` (Render/3D busy). Expect **correct speech**, **not** a latency win on Xe-LP (fresh long RTF can be ~5).  
This path is **legacy for steady product work** vs GenAI, but **retained** as the original iGPU proof.

### One-shot smoke

```bash
./scripts/smoke_product.sh
# WAVs under artifacts/poc_ship/smoke/ — ort_cpu.wav required
```

### Open WebUI

Admin → Settings → Audio → OpenAI-compatible:

- Base URL: `http://<host>:8880/v1`
- Model: `kokoro` · Voice: `af_bella`
- Response splitting: **Punctuation** is fine on ort-cpu; use **Paragraphs/None** on slow GPU legs

---

## 2. Run the Prototype (Product B)

Official pack + GenAI (evolutionary path after S0/I0):

```bash
# fetch OpenVINO/kokoro-82M-int8-ov into models/kokoro-82M-int8-ov (see MODELS.md)
KOKORO_BACKEND=ovgenai-gpu \
KOKORO_GENAI_MODEL=models/kokoro-82M-int8-ov \
KOKORO_TTS_CACHE=1 \
python scripts/kokoro_server.py --host 0.0.0.0 --port 8880
```

| Metric (validation host, served, warm steady) | Value |
|-----------------------------------------------|------:|
| Fox RTF | ~0.73 |
| Multi RTF | ~0.72 |

**Honesty:** first synthesis of a **novel** length can take **tens of seconds** (shape-keyed JIT). Cache + chunk-shaped `KOKORO_WARM_TEXT` mitigate repeats — do **not** quote steady RTF as first-utterance latency.

Voices: 54 in the official pack; default name `af_bella`; `af_heart` first-class. Timbre differs from v0.19 ship bella (deeper vs brighter).

---

## 3. Configuration (env)

| Variable | Default | Notes |
|----------|---------|--------|
| `KOKORO_BACKEND` | `ort-cpu` | `ovgenai-gpu` · `ovgenai-cpu` · `ov-cpu` · `ov-gpu` (legacy proof) |
| `KOKORO_MODEL` | stock ONNX path | patched path for ov-gpu |
| `KOKORO_GENAI_MODEL` | `models/kokoro-82M-int8-ov` | Product B pack dir |
| `KOKORO_VOICES` | `models/voices-v1.0.bin` | NPZ (PoC) |
| `KOKORO_TTS_CACHE` | `0` | set `1` for deploy repeats |
| `KOKORO_TTS_CACHE_DIR` | `cache/tts` | |
| `KOKORO_TTS_CACHE_TIER` | `both` | `response` · `chunk` · `both` |
| `KOKORO_WARM_TEXT` | empty | `\|`-separated phrases; **chunk-shaped** for GenAI |
| `KOKORO_WARM_BUCKETS` | empty | ov ONNX shape warm only |
| `KOKORO_DEFAULT_VOICE` | `af_bella` | |
| `KOKORO_GPU_PRECISION` | `f32` | ov-gpu; f16 hard-fails on this graph |

---

## 4. Performance honesty

| Path | What to expect |
|------|----------------|
| **ort-cpu** | RTF ~0.4 class — daily driver for PoC |
| **ov-gpu** patched | Real GPU offload; fresh long **RTF ~5** on Xe-LP; proof, not speed |
| **ovgenai-gpu** | Warm steady **~0.7 RTF**; novel shape first hit multi-second–tens of seconds |

Measurement rules we live by: name cold vs steady; discard warmup before mean RTF; ears beat vanity metrics on quality.

---

## 5. Architecture (short)

```text
text → sentence/token chunker → per-chunk backend synth → assembly (+ trim on OV pad path)
                              ↘ C1 full-request / C2 per-chunk disk cache (opt-in)
```

Cache unit = synthesis unit. GenAI uses per-chunk `generate()` and `c2txt:` keys.  
Depth: [docs/INDEX.md](docs/INDEX.md), notes/39–43, 65 (warmth-class byte-eq doctrine).

---

## 6. The story

We started with stock Kokoro ONNX that would not compile cleanly on Intel GPU, patched the graph, proved whole-graph offload, shipped a server and WebUI path, then measured an official GenAI pack into an integrated prototype. **The original PoC still runs.** Prove it to yourself with §1.

Lab map: [docs/INDEX.md](docs/INDEX.md) · team process: [WORKFLOW.md](WORKFLOW.md)

---

## 7. Upstream / filings

Draft OpenVINO GPU issues (shape-JIT, f16 MatMul, conv ref) live under `issues/submit/` — **research hold** for duplicate check before filing (notes/69).

Historical 2026.2.1 pins: [reproduce/2026.2.1/](reproduce/2026.2.1/).

---

## 8. Limits

- ov-gpu is not a latency product on this iGPU class  
- GenAI novel-shape tax remains  
- GenAI blends not supported; ort blends OK  
- Single-process server  
- Decoder componentized spike **parked** (notes/34)  
- Model weights downloaded separately (not in git)

---

## 9. Credits & license

- Kokoro model: hexgrad / community ONNX ecosystem (see upstream licenses)  
- OpenVINO / GenAI: Intel  
- This server & measurements: see [LICENSE](LICENSE), [CONTRIBUTORS.md](CONTRIBUTORS.md)

**Server version:** 1.5.0 (PoC face · ort-cpu default).
