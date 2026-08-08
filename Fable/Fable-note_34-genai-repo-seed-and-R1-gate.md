# Fable/note_34 — Prototype repo seed spec + R1 reproduction gate (answers notes/73)

**Date:** 2026-08-08
**Author:** Fable (Chief Architect)
**Type:** ARCHITECT DECISION INPUT + EXECUTION SPEC — answers Grok notes/73 §4 (B-options) and §7 (four questions); defines the kokoro-igpu-genai seed and its ship gate.
**Park status:** The note_33 §4 condition — "second repo parked until this repo clones-and-speaks" — is **satisfied**: `poc-complete` tagged @ `f2ff370`, R0 rehearsal PASS (notes/72), Nexus ears PASS 3/3. The park lifts on its own written terms, not by exception.
**Related:** notes/70–73, Fable note_31/32/33, WORKFLOW.md.

---

## 0. Verification performed (architect, against the pushed repo)

Fresh clone of `bdk38/kokoro-igpu` inspected directly:

| Check | Result |
|-------|--------|
| Tag `poc-complete` on `f2ff370` (R0 portable-paths fix) | confirmed |
| R0 record (notes/72): P0 hardcoded sandbox paths, voices-SHA mismatch, phantom `env.sh` — found, fixed, re-smoke PASS | confirmed |
| README two-Run-block structure, honest numbers, MODELS.md hashes + executable surgery | confirmed |
| `openvino_genai` import lazy (inside backend selector, line ~590) | confirmed — one-codebase-two-lineages statement held |
| Repo default `ort-cpu` (`BACKEND = os.environ.get("KOKORO_BACKEND", "ort-cpu")`, line 155) | confirmed |
| **Drift found:** FastAPI registers `version="1.5.1"` (line 1171); server docstring + README footer still say **1.5.0** | cosmetic — fix spec §5.1; do **not** re-tag |

---

## 1. Notes/73 §4 — B-options answer: **B1, then stop**

1. **Commit `artifacts/prototype/**` WAVs (LFS) + the README map.** This is the S0/I0 ear evidence made durable — exactly what honest-log wants on GitHub, not on one disk.
2. **Delete `venv-s0-ov263` (~5 GB) — ack'd.** Convergence closed dual-track (notes/59); `spike/ov263-genai/requirements-s0.lock.txt` is committed. The venv is reproducible from paper and holds no information the lock doesn't.
3. **No B2 tree moves.** The tagged repo just passed R0 against this exact layout; path churn now would invalidate the rehearsal we banked. B2 stays available later if ever justified — it is not, today.
4. B3 (populate sibling) proceeds — **per this spec**, §3–§4, not ad hoc.

---

## 2. Notes/73 §7 — the four questions, answered

### Q1 — Product face: **server-only thin tree**

The genai repo is the **appliance**; the monorepo is the **shelf**. Contents: server + requirements + pack-scoped MODELS + smoke + README + a short provenance pointer. The full S0/I0 lab (notes/45–67, spike tree, matrices) stays in the monorepo — copying notes forward forks the evidence chain into two diverging sources of truth. Provenance travels by **pointer** (tag + note ranges + verdict words), not by duplication.

### Q2 — Monorepo Product B docs: **keep the run block, add one line**

The dual-product README is part of the tagged record and the Prototype genuinely runs from that tree. Do not gut §2. Add a single line to the monorepo README §2 (post-tag commit, fine):

> *Product B development continues at https://github.com/bdk38/kokoro-igpu-genai (seeded from this repo @ poc-complete).*

**No submodule/subtree** — that is coupling machinery for a problem a hyperlink solves.

### Q3 — Seed: **copy, with provenance by pointer — not history extraction**

Monorepo history is interleaved: the server file carries both products in every commit. A filter-repo extraction would produce a technically-true-but-misleading standalone history at real effort cost. Instead the seed commit message states its origin:

```
feat: seed Prototype (Product B) from bdk38/kokoro-igpu @ f2ff370 (poc-complete)
```

The history of record stays where it happened.

### Q4 — Default backend: **yes, `ovgenai-gpu`**

This is the clean resolution of the default saga. Monorepo default stayed `ort-cpu` because that is the **PoC's** face; the genai repo **is** Product B, and `I0-GO-default-candidate` earned it exactly this role. README documents `ovgenai-cpu` as the no-GPU fallback in the first screen.

**Server file stays intact** — all backends present, including ort-cpu/ov-gpu code paths. Rationale: minimum divergence from the monorepo lineage keeps manual backports cheap; the README simply doesn't advertise the ONNX legs. Divergence is default + version identity + docs, nothing else.

---

## 3. Seed manifest (Grok R — execute)

From monorepo @ `f2ff370` into `bdk38/kokoro-igpu-genai` (on top of existing `README.md` stub + `LICENSE` @ `6fe076f`):

| Item | Source → dest | Delta at seed |
|------|---------------|---------------|
| `scripts/kokoro_server.py` | copy | **Two edits:** default `"ort-cpu"` → `"ovgenai-gpu"` (line ~155); version → **`2.0.0`** (line ~1171 + docstring rewritten for B-face). Nothing else. |
| `requirements.txt` / `requirements.lock.txt` | copy | verify GenAI pins present (they are — converged venv) |
| `MODELS.md` | **rewrite, B-scoped** | Official `OpenVINO/kokoro-82M-int8-ov` HF fetch + SHA256 of pack files + `SHIP_PACK_IDENTITY.txt` convention. No v0.19/patched entries. |
| `scripts/download_models.sh` | adapt or new `fetch_pack.sh` | HF pack fetch + hash verify; weights stay out of git |
| `scripts/smoke_product.sh` | adapt → `smoke.sh` | legs: **ovgenai-cpu required**, ovgenai-gpu if GPU present (igt glance); prints WAV paths for ears |
| `README.md` | **new (Fable R, §6 skeleton)** | replaces stub |
| `docs/PROVENANCE.md` | new, short | table: S0 → monorepo notes/45–53 → `S0-GO-product`; I0 → notes/54–67 → `I0-GO-default-candidate`; cache doctrine → notes/39–43, 65; link `poc-complete` tag |
| `.gitignore` / `.gitattributes` | copy, trim | LFS for smoke/ear WAVs if committed |
| `CONTRIBUTORS.md` | copy | credit continuity |

**Not seeded:** notes/, Fable/, Grok/, spike/, issues/, patched models, probe scripts, WORKFLOW.md (monorepo remains the process + lab home; genai PROVENANCE points at it).

**Version line rationale:** new default is a behavior change; `2.0.0` keeps the two lineages unconfusable in `/health` output. Monorepo continues 1.5.x.

## 4. R1 — reproduction gate (bars written before execution, per house rule)

Mirror of R0, which earned its keep finding a P0. One Grok session + one short listen.

- **R1.1 Inventory:** everything a stranger needs is in the repo — pack fetch with hashes, lock, run command, smoke.
- **R1.2 Stranger rehearsal:** fresh clone, fresh venv from committed requirements, README only. **Required:** `ovgenai-cpu` serves and speaks on any host. **If GPU present:** `ovgenai-gpu` serves, igt fingerprint recorded, smoke WAVs written. Novel-shape tax observed on first hit is **expected behavior, not a FAIL** — README states it.
- **R1.3 Ears:** Nexus, by filename.
- **PASS** = clone-and-speak with nothing but the README. Anything R1.2 needed that wasn't in the repo **is the finding** — commit and re-run.
- **Tag on pass:** `prototype-complete` (or Nexus's preferred name).

**Predicted branches:** R1.2 passes on first or second attempt; likeliest finding class is fetch-script/hash friction on the HF pack (the R0-2 analogue), not server behavior — the server is byte-identical to the tree that just passed R0 except two lines.

## 5. Monorepo-side actions (small, post-tag commits — do not re-tag)

1. **Version-string drift fix:** docstring + README footer `1.5.0` → `1.5.1` (matches FastAPI registration).
2. **B1 commit:** `artifacts/prototype/**` (LFS) + prototype README map.
3. **Sibling pointer line** in README §2 (Q2 wording above).
4. `venv-s0-ov263` delete (host hygiene, no repo change).

## 6. genai README skeleton (Fable R — drafts on Grok's seed inventory return)

```
1. What this is — official Kokoro-82M int8 (OpenVINO GenAI) served on a
   $150-class Intel iGPU. Warm steady RTF ~0.73; the honest tax stated
   in the same breath.
2. Run it: install → fetch pack (hashes) → start (default ovgenai-gpu)
   → curl → hear. ovgenai-cpu fallback for no-GPU hosts, first screen.
3. Configuration table (B-relevant env only)
4. Performance honesty: warm steady vs novel-shape first hit
   (tens of seconds, shape-keyed JIT); cache + chunk-shaped WARM_TEXT
   mitigation; never quote steady RTF as first-utterance latency.
5. Voices (54; af_bella default, af_heart first-class; timbre note)
6. Architecture: chunk = cache unit; per-chunk generate(); C1/C2 cache
7. Provenance → docs/PROVENANCE.md → monorepo (the story lives there)
8. Limits (no blends on genai; single-process; weights not in git)
9. Credits/license
```

## 7. Explicitly OUT of scope

- Prototype backlog features (blends on genai, chunk-overhead matrix, RAPL/E-core stress) — after R1 ships, gated per house rule.
- Filings — RESEARCH HOLD stands (notes/69); unaffected by the split.
- Monorepo B2 reorg — not now, possibly never.
- Any RTF improvement work.

## 8. One-line

**Park lifted by its own terms: seed kokoro-igpu-genai as a thin B-faced appliance — copied from `poc-complete` with exactly two server edits (default `ovgenai-gpu`, version 2.0.0), pack-scoped MODELS, provenance by pointer to the monorepo shelf — gate it with R1 (stranger clone, ovgenai-cpu required leg, GPU leg + igt where present, Nexus ears, tag), while the monorepo takes B1 plus a version-string fix and one sibling link, and nothing else moves.**

---

*Fable (Chief Architect), 2026-08-08. Grok: execute §3 manifest + §5 monorepo actions; run R1 per §4; return seed inventory so I draft the README (§6). Nexus: ears at R1.3, tag name on pass; the 5 GB venv delete is ack'd architect-side and awaits only your nod.*
