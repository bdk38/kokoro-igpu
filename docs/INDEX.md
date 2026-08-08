# Evidence & story index

**Proof is hearing the server run** (see root `README.md`). This file maps the lab book.

## Products

| Product | What | Entry |
|---------|------|--------|
| **A — PoC** | ONNX v0.19 + patches; ort-cpu default; ov-gpu iGPU proof leg | README § Run the PoC |
| **B — Prototype** | Official GenAI int8 pack; `ovgenai-gpu` | README § Run the Prototype |

## Arcs → notes → verdicts

| Arc | Notes (approx) | Verdict / outcome |
|-----|----------------|-------------------|
| OpenVINO EP / graph surgery | 02–07 | Patched GPU compile path |
| Server + WebUI + trim | 08–18 | Ship server; ear-validated trim |
| Warm honesty / shape key | 19–20, 35 | Shape-keyed warm; KOKORO_WARM_TEXT |
| Black-box cache design | 21, 28, 39–43 | C1+C2 TTS cache (v1.2.0) |
| Decoder componentized spike | 25–34 | **PARKED** |
| Dual-track env | 37–38, 59 | Converged ship to 2026.3+GenAI |
| S0 official GenAI probe | 36, 45–53 | **`S0-GO-product`** |
| I0 integration | 54–67 | **`I0-GO-default-candidate`** |
| Default cutover then PoC face | 68, 70–71 | Deploy may use ovgenai; **repo default ort-cpu** (PoC) |
| Filings | 57, 69, `issues/submit/` | VERIFY done · **RESEARCH HOLD** |
| PoC ship assembly | 71, Fable note_33 | MODELS, smoke, reproduce/ |

## Architect notes

Under `Fable/` — especially note_29–33 (I0, reorg, PoC ship).

## Prototype evidence (Product B)

| Path | Contents |
|------|----------|
| `artifacts/prototype/` | S0/I0 ear + matrix WAVs (organized 2026-08-08) |
| `spike/ov263-genai/` | Historical S0 probe scripts |
| `notes/73` | Segregation inventory — **hold for Architect** |
| Sibling repo | https://github.com/bdk38/kokoro-igpu-genai (**empty shell** — not populated) |
| `models/kokoro-82M-int8-ov/` | Official pack (download; see MODELS.md) |

## Host inventory

`notes/00-host-inventory.txt`
