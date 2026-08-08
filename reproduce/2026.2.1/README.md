# PoC provenance pin — OpenVINO 2026.2.1

Paper-grade / historical lock for the **ONNX-era PoC** measurements
(notes through dual-track era, Warm Bucket Fix, patched ov-gpu demos).

**Product install for strangers:** use the repo-root `requirements.txt`
(OpenVINO **2026.3** + GenAI). The ov-gpu patched path was verified to
**compile and speak on 2026.3** (`artifacts/poc_ship/ovgpu_2026_3_check.json`).

Use this directory only if you need bit-aligned archaeology with the
2026.2.1 lab book, or if a future regression appears on a newer wheel.

```bash
python3 -m venv venv-poc-2026.2.1
source venv-poc-2026.2.1/bin/activate
pip install -r reproduce/2026.2.1/requirements.txt
# optional: pip install -r reproduce/2026.2.1/requirements.lock.txt
```

Captured from git `9f78e5f` / `cff7974` (2026-08-07 dual-track rollback).
