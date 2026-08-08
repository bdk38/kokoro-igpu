# Componentized-export spike (G0+G1)

Spike path for the Kokoro seam-B parity instrument locked in `Fable/note_17`. Do not touch the ship path (`scripts/kokoro_server.py`, `models/patched/`). Run G0 strict decoder load + G1 forward-hooks ladder with:

```bash
/data/kokoro-openvino/venv-peek/bin/python spike/hook_ladder.py
```

Outputs land in `spike/out/` (`g0_strict_load.json`, `ladder_table.csv`, `ladder_result.json`, optional wavs). G2+ (ONNX / OpenVINO) are intentionally not implemented here.

## Artifacts in git

- **Committed:** Python probes, JSON/CSV result tables, ear WAVs (LFS), tiny Conv1d repro ONNX under `out/g3/diagnosis/minimal_conv1d/`.
- **Not committed (~200MB each):** full decoder ONNX under `out/g2/` — rebuild with `g2_export.py` / hardening scripts. See notes/27–31.
