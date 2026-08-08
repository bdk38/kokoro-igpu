<!--
SUBMIT READY — github.com/openvinotoolkit/openvino/issues
Labels (suggested): bug, category: GPU
VERIFY: 2026-08-08 Grok
  - Symptom CORRECTED vs early draft: hard FAIL at first infer (MatMul shape validation),
    NOT silent "corrupted audio". Matches captures/iss1_f16_fail.log and live 2026.3.0 re-repro.
  - Official int8 pack UNAFFECTED (default f16 compute, ears PASS) — do not claim otherwise.
  - Re-repro on ship OpenVINO 2026.3.0: FAIL f16 MatMul_71562; PASS f32 finite speech-like peak.
Attachments: iss1_f16_fail.log, iss1_f32_ok.log, filing2_f16_repro_2026.3.json
File this BEFORE #3 and cross-link.
-->

# Title

```
[GPU] FP16 inference fails with "Incompatible MatMul matrix dimension" on patched f32 Kokoro TTS ONNX (Xe-LP); f32 hint works; official int8 Kokoro IR unaffected
```

# Body (paste below)

### OpenVINO Version

- Originally captured: **2026.2.1** (`2026.2.1-21919-ede283a88e3-releases/2026/2`)
- **Reconfirmed 2026-08-08 on 2026.3.0** (`2026.3.0-22451-8a17657b995-releases/2026/3`) — same failure class

### Operating System

Ubuntu 24.04.4 LTS (x86_64), kernel 7.0.0-28-generic

### Device used for inference

GPU — Intel UHD Graphics, Alder Lake-UP3 GT1, PCI **8086:46b3**, Xe-LP 64 EU  
Driver: intel-opencl-icd **26.22.38646.7**, IGC **2.36.5**

### Framework / model

- ONNX opset 17 export of **Kokoro-82M v0.19** (public community ONNX ~311 MB)  
  SHA256 stock: `dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c`  
- Two small **graph patches** required for GPU compile at all (3D→4D linear Resize + STFT rank-4 annotation). Scripts: https://github.com/bdk38/kokoro-igpu  
  Patched model SHA256: `effa08953b35c413064953850070533afce7c8d6a11f996f87e87fbcad42983f` (`kokoro-v0_19.gpu4d.stft.onnx`)  
- Patches are **not** the subject of this bug: the patched graph runs **correctly end-to-end on GPU at f32**.

### Issue description

Compile on GPU with `INFERENCE_PRECISION_HINT=f16` **succeeds**, but **first inference fails** with MatMul shape validation:

```text
While validating node 'opset1::MatMul MatMul_71562 () -> ()' with friendly_name 'MatMul_71562':
Incompatible MatMul matrix dimension. First input dimension=9 at COL_INDEX_DIM=2
doesn't match the second input dimension=1 at ROW_INDEX_DIM=0
```

(2026.2.1 capture used friendly name `MatMul_66245` — same COL=9 vs ROW=1 class; name is capture-dependent after graph rewrite.)

Identical graph / feeds / device with only `INFERENCE_PRECISION_HINT=f32`:

- compiles and infers successfully  
- finite output, peak ~0.5 on dummy tokens (2026.3.0 re-repro)  
- human-verified speech on real text in earlier captures  
- `EXECUTION_DEVICES=['GPU.0']`

### Scope honesty (important)

The **official** pack `OpenVINO/kokoro-82M-int8-ov` under GenAI 2026.3.0 runs with **unforced default f16** compute (`INFERENCE_PRECISION_HINT` reports float16) and **clean listening results** on this same host. This defect is **graph/export-dependent** (community f32 ONNX + our GPU enablement patches), **not** a blanket “Kokoro on GPU is broken at f16.”

We still file it because:

1. The f32 ONNX + patch path is widely used in the kokoro-onnx / self-hosted ecosystem.  
2. f16 is the intended fast path on Xe-LP; with f16 hard-failing, users are forced onto f32 and hit reference-convolution performance (companion issue).  
3. Silent attribution is hard: compile succeeds; failure is at first infer deep in MatMul shape inference.

### Step-by-step reproduction

```bash
pip install openvino==2026.3.0 numpy onnx
# obtain patched model via repo scripts patch_kokoro_resize.py + patch_kokoro_v2.py
# or use models/patched/kokoro-v0_19.gpu4d.stft.onnx from https://github.com/bdk38/kokoro-igpu

python - <<'PY'
import numpy as np, openvino as ov
core = ov.Core()
model = "kokoro-v0_19.gpu4d.stft.onnx"
tokens = np.zeros((1, 32), np.int64); tokens[0,0]=0; tokens[0,-1]=0
style = np.zeros((1, 256), np.float32)  # or real voice row
speed = np.array([1.0], np.float32)
for prec in ("f16", "f32"):
    cm = core.compile_model(model, "GPU", {
        "PERFORMANCE_HINT": "LATENCY",
        "INFERENCE_PRECISION_HINT": prec,
    })
    feed = {}
    for inp in cm.inputs:
        n = inp.any_name
        feed[n] = tokens if "token" in n.lower() else style if "style" in n.lower() else speed
    try:
        out = cm.create_infer_request().infer(feed)
        a = np.asarray(list(out.values())[0]).reshape(-1)
        print(prec, "OK", a.size, float(np.max(np.abs(a))))
    except Exception as e:
        print(prec, "FAIL", e)
PY
```

**2026.3.0 result on this host:** `f16 FAIL` (MatMul_71562 … dim 9 vs 1); `f32 OK` (36000 samples, peak 0.50, finite).

### Expected behavior

f16 execution either produces correct output, or fails at compile with a clear unsupported-pattern diagnostic — not a first-infer MatMul dimension check after a successful compile.

### Attachments

- `iss1_f16_fail.log` (2026.2.1 original)  
- `iss1_f32_ok.log`  
- `filing2_f16_repro_2026.3.json` (2026.3.0 re-repro)  
- Patch scripts / model build: https://github.com/bdk38/kokoro-igpu  

### Related

Will cross-link companion performance issue on `convolution_gpu_ref__f32` domination for the forced-f32 path.
