# notes/25 — Spike G0/G1: strict load + hook ladder

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator) — Mechanic implemented `spike/hook_ladder.py`; Orchestrator QC + re-run  
**Gate design:** `Fable/note_17` (Nexus-acked)  
**Path:** Spike only (`spike/`). Ship path not touched.

---

## One-line verdict

**G1 PASS (bit-exact).** Seam B recomposition is sound. **G0 is not literally clean** (121 missing keys) but every missing key is structural (AdaIN `InstanceNorm` affine + `CustomSTFT` buffers under `disable_complex=True`) — **not** dropped learned weights. Ladder signature is **not** Branch A damage (no discontinuous jump). Weekend peek maxdiff ~0.075 was almost certainly a bad hand-mirror/load path, not an un-mirrorable seam.

---

## What ran

```bash
/data/kokoro-openvino/venv-peek/bin/python spike/hook_ladder.py
```

| Item | Value |
|------|--------|
| Env | `/data/kokoro-openvino/venv-peek` (torch CPU 2.13, kokoro editable) |
| Weights | `kokoro-v1_0.pth` |
| Voice | `af_bella` |
| Text | `Hello from the spike ladder.` |
| Seed | 0 (required: decoder NSF uses `randn`) |
| `disable_complex` | True |
| Device | CPU f32, `eval()`, `no_grad()` |

Artifacts:

- `spike/hook_ladder.py`, `spike/README.md`
- `spike/out/g0_strict_load.json`
- `spike/out/ladder_table.csv`, `spike/out/ladder_result.json`
- `spike/out/ref.wav`, `standalone_captured.wav`, `standalone_constructed.wav` (24 kHz)
- `spike/out/rerun_console.log` (Orchestrator re-run)

---

## G0 — Strict decoder load

Printed and captured:

```text
missing_keys = 121 keys (see g0_strict_load.json)
unexpected_keys = []
strict_clean = False
n_ckpt_decoder_keys = 375
```

### Missing-key classes (complete partition)

| Class | Count | Interpretation |
|-------|------:|----------------|
| `*.norm.weight` / `*.norm.bias` (AdaIN `InstanceNorm1d`) | 116 | Source sets `affine=True` for old ONNX export (`istftnet.py` comment: *should be False*; extra learnable params). **Not present in v1.0 checkpoint** — defaults remain identity-scale. Same situation on official `KModel` load (`strict=False` fallback). |
| `generator.stft.*` buffers (`window`, `weight_forward_*`, `weight_backward_*`) | 5 | Built by `CustomSTFT` when `disable_complex=True`; not trained weights in the pth. |
| Other learned weights missing | **0** | — |

**Literal note_17 G0 bar** (“zero missing, zero unexpected”): **not met.**  
**note_17 G0 kill trigger:** none — failure routes into the ladder. Ladder run completed.

---

## G1 — Hook ladder

### Rung 0 (seam inputs: constructed frontend vs captured decoder inputs)

| name | shape | maxdiff | mean\|diff\| | cosine | status |
|------|-------|--------:|------------:|-------:|--------|
| seam.asr | [1,512,90] | **0** | 0 | ~1 | OK |
| seam.F0_pred | [1,180] | **0** | 0 | ~1 | OK |
| seam.N_pred | [1,180] | **0** | 0 | ~1 | OK |
| seam.style | [1,128] | **0** | 0 | ~1 | OK |

F0/N length = 2×T (T=90) — matches v1.0 peek lattice note.

### Decoder named-module rungs

- **422** mirrored hooks (426 rows including 4 seam rungs)
- **max maxdiff across all rungs = 0**
- No shape mismatches
- No discontinuous jump (≥3 orders) anywhere

### Waveforms

| pair | maxdiff |
|------|--------:|
| ref vs standalone on **captured** seam inputs | **0** |
| ref vs standalone on **constructed** seam inputs | **0** |
| captured vs constructed standalone | **0** |

Audio length: 54000 samples @ 24 kHz (2.25 s).  
**G1 PASS** vs bar maxdiff ≤ 1e-4 (actual 0).

Cosine values occasionally print as 1.0000x with maxdiff 0 — float reduction noise in the cosine helper; maxdiff is the binding metric and is exact 0 on this run (int16 WAV re-read also maxdiff 0 after quantize).

---

## Branch verdict (note_17 taxonomy)

| Branch | Predicted signature | Observed |
|--------|---------------------|----------|
| **A** dropped weights | G0 non-empty **and** single-rung maxdiff jump O(0.01–0.1) | G0 non-empty **yes**; jump **no** |
| **B** seam construction | G0 clean, rung0 diverges | rung0 maxdiff **0** |
| **C** mode/dtype | gradual growth across rungs | all rungs **0** |
| none | clean rungs, bad final wave | final wave **0** |

**Recorded script verdict: `A`** (because note_17 maps any non-empty G0 missing/unexpected → A).

**Orchestrator refinement (do not silent-rewrite the gate):** this is **formal A without A-damage**. Missing keys are explained structural keys, not missing conv/LSTM/generator weights. Effective scientific conclusion: **seam B is validated; proceed toward G2 after acknowledging G0 allowlist.**

---

## Product / spike implication

1. **Seam B cut is real and mirrorable** at f32 CPU with bit-exact parity when frontend and decoder share the same math and weights.
2. **G2 (decoder-only ONNX @ fixed T) is unblocked on parity grounds**, subject to Nexus/Fable ack that G0 may treat the 121 structural keys as an **allowlist** rather than a hard stop:
   - allow: AdaIN `InstanceNorm1d` affine weight/bias absent from ckpt
   - allow: `CustomSTFT` buffers under `disable_complex=True`
   - still require: **zero missing keys outside that allowlist**, zero unexpected, and G1 ≤ 1e-4
3. Do **not** spend cycles chasing weekend maxdiff ~0.075 on the old hand path; this ladder supersedes it.
4. Ship freeze held: no edits to `scripts/kokoro_server.py` or `models/patched/`.

---

## Expected log signatures (note_17 §5) vs actual

| Expected | Actual |
|----------|--------|
| G0 PASS: `missing_keys=[] unexpected_keys=[]` | `unexpected=[]`, **missing=121 structural** |
| Branch A: single rung jump ≥3 orders | **No jump**; all maxdiff 0 |
| Ladder &lt; ~5 min wall | Met (seconds-class on this host) |

---

## Next gate (not started)

**G2** — decoder-only ONNX at fixed T (token-bucket-96 equivalent), ORT-CPU parity + Nexus ears on ≥3 utterances — only after G0 allowlist ack if we treat literal G0 as amended; scientifically G1 already clears the seam.

---

## Risks

- NSF `randn` inside decoder: seed must stay fixed across paths or false diffs appear.
- G0 literal wording vs structural keys: needs a one-line gate clarification from Fable/Nexus so we do not argue mid-G2.
- Cosine helper can read slightly &gt;1 when maxdiff is 0; ignore cosine for pass/fail.
