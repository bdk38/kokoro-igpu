# Models — provenance, hashes, roles

Weights are **not** in git. Fetch with `./scripts/download_models.sh`, then
build the patched graph if you need the PoC iGPU leg.

## Product A — PoC (ONNX era)

| File | Role | SHA256 |
|------|------|--------|
| `models/kokoro-v0_19.onnx` | Stock Kokoro v0.19 ONNX (ort-cpu default path) | `dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c` |
| `models/voices-v1.0.bin` | NPZ voice pack | see download note below |
| `models/patched/kokoro-v0_19.gpu4d.stft.onnx` | **LEGACY** GPU-enabled graph (resize 3D→4D + STFT rank stamp) | `effa08953b35c413064953850070533afce7c8d6a11f996f87e87fbcad42983f` |
| `models/patched/kokoro-v0_19.gpu4d.onnx` | Intermediate resize-only patch | `16da5997626ef83780a941b104e5bc2f2311038f9c2e669fca48c6f0e8ae41e6` |

### Fetch (PoC)

```bash
./scripts/download_models.sh
# verifies SHA256 after download when sha256sum is available
```

Default URLs (overridable via env):

- ONNX: `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx`
- Voices (kokoro-onnx **v0.19 companion**, ~11 voices including `af_bella`):
  `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin`
  → saved as `voices-v1.0.bin`
  - SHA256 (current release asset): `157eab2fa1dd1c91b46599ea6f514bf86f66944c0c760250ed324e6cd99af075`
  - Shape family: `(511, 1, 256)` per voice — works with this server
  - Lab book historically used a larger ~50-voice NPZ (`d19762d4…`, ~26 MB). That file is **not** the public kokoro-onnx asset; override `VOICES_URL` if you have it. PoC smoke uses the public 11-voice pack.

### Rebuild patched graph (surgery is executable)

```bash
python scripts/patch_kokoro_v2.py \
  --model models/kokoro-v0_19.onnx \
  --output models/patched/kokoro-v0_19.gpu4d.stft.onnx \
  --stamp-stft
sha256sum models/patched/kokoro-v0_19.gpu4d.stft.onnx
# expect effa08953b35c413064953850070533afce7c8d6a11f996f87e87fbcad42983f
```

Regeneration check (2026-08-08): **byte-identical** to committed reference hash
(`artifacts/poc_ship/patch_regen_check.json`).

### Status

| Path | Status |
|------|--------|
| ort-cpu + stock ONNX | **PoC product default** |
| ov-gpu + patched STFT graph | **PoC iGPU proof leg** — legacy for *steady product work* vs GenAI, but **retained and runnable** (speaks on OV 2026.3) |
| Maintenance on patched graph | No forward feature work; keep for proof + filings |

---

## Product B — Prototype (GenAI era)

| Path | Role | Identity |
|------|------|----------|
| `models/kokoro-82M-int8-ov/` | Official OpenVINO GenAI Kokoro pack | HF `OpenVINO/kokoro-82M-int8-ov` |
| `openvino_model.bin` | IR weights | sha256 `c879cdd88275b9bfa25e51204d969013d701ea8699e15f99fd1957caf75a29ab` |
| `openvino_model.xml` | IR | sha256 `a04d5d91e8d6f8d8c1ade28ad331b65827aa148e65515acb4c6725f876257fa5` |
| `voices/*.bin` | 54 speaker embeddings | e.g. af_bella, af_heart |
| `SHIP_PACK_IDENTITY.txt` | Local promotion record | first-class copy (not spike symlink) |

### Fetch (Prototype)

```bash
# example — huggingface-cli or git-lfs clone into models/kokoro-82M-int8-ov
huggingface-cli download OpenVINO/kokoro-82M-int8-ov --local-dir models/kokoro-82M-int8-ov
# confirm bin hash matches MODELS.md / SHIP_PACK_IDENTITY.txt
```

Set `KOKORO_BACKEND=ovgenai-gpu` and `KOKORO_GENAI_MODEL=models/kokoro-82M-int8-ov`.

---

## Pin strategy (PoC ship)

Single product venv: **OpenVINO 2026.3 + GenAI** (repo-root `requirements.txt`).  
ov-gpu patched **compiles and speaks** on that venv (`artifacts/poc_ship/ovgpu_2026_3_check.json`).  
Historical 2026.2.1 locks: `reproduce/2026.2.1/`.
