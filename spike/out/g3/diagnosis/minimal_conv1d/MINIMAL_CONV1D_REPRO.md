# O2 minimal repro + escalation (note_23 §4)

## Headline

| Case | OV-GPU |
|------|--------|
| plain Conv1d dynamo | **ok** |
| legacy Conv1d | **ok** |
| weight_norm Conv1d (small / wide / 1090→512) | **ok** |
| Unsqueeze→weight_norm Conv1d | **ok** |
| Cat→weight_norm Conv1d 1090 | **ok** |
| **Full Kokoro dynamo decoder** | **FAIL** Conv rank |

## Blame for upstream

**not_minimal_conv1d_requires_full_decoder_repro**

Isolated dynamo exports of plain Conv1d, weight_norm Conv1d (including 1090→512 k=1), Unsqueeze-then-Conv, and Cat-then-weight_norm all compile and run on OV-GPU 2026.2.1. Therefore the Kokoro decoder Conv-rank failure is NOT explained by Conv1d or weight_norm alone. Filing should use the full `kokoro_decoder_t96_edge_dynamo.onnx` as the reproducer against OpenVINO GPU; optionally attach the working minimal Conv1d ONNX as a contrast ("simple Conv1d OK, full decoder fails"). Split export-vs-plugin remains open at the subgraph level (O2 undetermined for a one-op minimal case); the actionable upstream packet is OV-GPU + full dynamo decoder ONNX.

## Artifacts

Directory: `spike/out/g3/diagnosis/minimal_conv1d/`

- Working minimals: `tiny_conv1d_dynamo.onnx`, `tiny_weight_norm_*.onnx`, …
- Full failing graph (already in tree): `spike/out/g2/kokoro_decoder_t96_edge_dynamo.onnx`
- JSON: `minimal_conv1d_report.json`
