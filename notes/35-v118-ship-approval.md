# notes/35 — v1.1.8 ship (closed)

**Date:** 2026-08-07  
**Author:** Grok (Orchestrator)  
**Status:** **SHIPPED + pushed** `8854d24` — Nexus wrap-up = **Option A**  
**Runtime:** ship dual-track — OpenVINO **2026.2.1** + drivers 26.22.38646.7 (`notes/38`)

---

## Decision

| Option | Meaning | Result |
|--------|---------|--------|
| **A. Approve v1.1.8 as written** | `KOKORO_WARM_TEXT` + honesty docs + v1.1.7 near-capacity bucket prewarm | **SELECTED** |
| B. Docs-only | — | not taken |
| C. Hold | — | not taken |

---

## What v1.1.8 contains

1. **v1.1.7 behavior:** `KOKORO_WARM_BUCKETS` pre-warm via real synthesize near bucket capacity (`_prewarm_text_for`). Trim remains v1.1.5 class.  
2. **`KOKORO_WARM_TEXT`:** `|`-separated exact phrases at startup after bucket pre-warm — pins demo shapes.  
3. **Docstring + README honesty:** shape-keyed warm; WARM_BUCKETS ≠ varied Read Aloud accelerator; ort-cpu default.  
4. **Version** `1.1.8` (`FastAPI(..., version="1.1.8")`).

---

## Smoke (2026-08-07, ship venv 2026.2.1)

### ort-cpu (product default)

| Check | Result |
|-------|--------|
| `py_compile` | OK |
| `/health` | `backend=ort-cpu` ok |
| Fox `/v1/audio/speech` | **200**, `X-Kokoro-RTF: 0.40`, wav 181244 B |
| WAV | `artifacts/v118_ship/ort_cpu_fox.wav` |
| Log | `logs/v118_ort_cpu_server.log` |

### ov-gpu demo + WARM_BUCKETS=96 + WARM_TEXT=fox

Startup log:

- compiled bucket=96  
- pre-warmed bucket=96 via synthesize (shape-keyed)  
- pre-warmed text=fox  

| Request | X-Kokoro-RTF | Note |
|---------|-------------:|------|
| Fox after pin | **0.95** | warm-class for pinned shape |
| Novel (“keys wallet passport…”) | **7.35** | cold novel shape — honesty holds |
| Fox repeat | **0.97** | still warm-class |

WAVs: `artifacts/v118_ship/ov_gpu_fox_after_warm.wav`, `ov_gpu_novel.wav`, `ov_gpu_fox_repeat.wav`  
Log: `logs/v118_ov_gpu_server.log`

**Product implication unchanged:** ort-cpu default; ov-gpu demo; WARM_TEXT pins exact phrases only; novel traffic still pays shape cold.

---

## One-line

**v1.1.8 Option A closed: server smoke ort-cpu RTF 0.40; ov-gpu fox pin ~0.95 RTF vs novel 7.35; shape-key honesty demonstrated on the wire.**

---

## Fable note_29 (Architect read-back)

Agreed and folded: the three-number table (fox pin 0.95 / novel 7.35 / fox repeat 0.97) is the on-the-wire validation of notes/18–20 shape-key work via the **real request path**, not only harness.

### Server warm vs harness warm (informative — not a discrepancy)

| Path | Warm fox-class RTF | Notes |
|------|-------------------:|-------|
| Server after `KOKORO_WARM_TEXT` pin | ~**0.95–0.97** | `X-Kokoro-RTF`; includes server bucket/pad path |
| Direct harness steady (notes/38 rollback) | ~**0.66** | raw infer / audio; no server bucket denominator |

Per WORKFLOW measurement-honesty item 4: server vs direct must call out token bucketing / pad-to-bucket effects on RTF denominators. **Do not quote 0.95 and 0.66 as conflicting product claims.** Both are consistent with shape-keyed warm; different measurement paths.

