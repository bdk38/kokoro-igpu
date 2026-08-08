# notes/57 — Filings location + board (post I0.1)

**Date:** 2026-08-08  
**Nexus:** Filings are in `/data/intel-igpu-tts/issues`; **complete and file at end** (not blocking I0.1 — already done).  
**I0.2 / convergence:** still gated on **filings submit** or **explicit Nexus waiver** (Option A / G5).

---

## Filings tree

| Path | Role |
|------|------|
| `issues/filing-1-shape-jit.md` | **New S0-informed draft #1** (Fable 2026-08-08) — shape-JIT; VERIFY markers for Grok |
| `issues/filing-2-f16-matmul.md` | **New S0-informed draft #2** — reframed pack-dependent; must not claim official pack broken |
| `issues/filing-3-conv-ref.md` | **New S0-informed draft #3** — f32 ref-conv + int8 contrast |
| `issues/openvino-issue-1-f16-matmul.md` | Earlier filled draft (2026-08-04) |
| `issues/openvino-issue-2-f32-conv-ref-kernels.md` | Earlier filled draft (2026-08-04) |
| `issues/captures/` | Host captures supporting drafts |

**Endgame:** Grok VERIFY pass on filing-1/2/3 → Nexus GitHub submit → unlocks ship venv convergence without waiver.

---

## Board now

| Track | Status |
|-------|--------|
| I0.1 voice | **CLOSED** — both first-class (notes/56) |
| Filings | **Drafts present**; complete + file **at end** (Nexus) |
| Filings→I0 gate | **WAIVED** notes/58 |
| Convergence | **DONE** notes/59 — ship venv 2026.3+GenAI |
| I0.2 ovgenai-gpu | **CLOSED PASS** notes/60 — ears 4/4 |
| I0.3 served RTF | **PASS** notes/62 — fox/multi steady ~0.73 |
| I0.4 regression | **PASS** notes/64 |
| I0.5 ov-gpu | **legacy-marked** notes/66 |
| I0 verdict | **`I0-GO-default-candidate`** notes/67 |
| Ship server | ort-cpu + cache on :8880 (v1.3.0 code) |
| S0 | **S0-GO-product** closed (notes/52–53) |

---

## One-line

**I0 CLOSED; default ovgenai-gpu; filings VERIFY-ready but RESEARCH HOLD (notes/69) — Nexus duplicate check before submit; commit still open.**
