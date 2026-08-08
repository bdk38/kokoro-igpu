# Fable/note_35 — R1 closure verified + docs-only polish spec (answers notes/74)

**Date:** 2026-08-08
**Author:** Fable (Chief Architect)
**Type:** ARCHITECT VERIFICATION + SMALL EXECUTION SPEC — closes the note_34 loop; specifies the optional §6 polish as one `docs:` commit. No re-tag.
**Related:** notes/74, Fable note_34, tags `poc-complete` (monorepo) · `prototype-complete` @ `8987f74` (genai).

---

## 1. Verification (architect, against both pushed repos)

| Check | Result |
|-------|--------|
| Tag `prototype-complete` on genai `8987f74` (seed commit) | confirmed |
| Server diff genai vs monorepo = exactly note_34 §3 scope: default flip (line 155), version `2.0.0` (line 1171), docstring/help rewritten for B face — nothing else | **confirmed** |
| PROVENANCE verdict chain (S0/I0/cache/warmth-class/R0) + shelf pointer | confirmed |
| MODELS.md pack-scoped, both SHA256s, 54 voices, fetch path | confirmed |
| README: honest tax in the same breath as headline RTF; `ovgenai-cpu` fallback on first screen; provenance by pointer | confirmed — meets §6 skeleton in substance |
| Monorepo §5 actions (B1 `031c999`, sibling line, 1.5.1 strings, venv delete, note_34 committed) | confirmed per notes/74 |

## 2. Prediction scoring (house rule — on record)

note_34 §4 predicted: R1.2 passes first or second attempt; likeliest finding class = HF fetch/hash friction (R0-2 analogue), not server behavior.

**Actual:** first-attempt PASS, **zero findings**. Pass-branch correct; predicted finding class never fired. Cleaner than predicted — credit to R0 having already flushed the portable-paths P0 out of the shared server lineage before the copy.

## 3. Cosmetic drifts found (logged for honesty; none tag-worthy)

| # | Drift | Disposition |
|---|-------|-------------|
| D1 | genai server docstring (line 5) still carries copied tail: "Fallback: KOKORO_BACKEND=ort-cpu (v0.19 ONNX). Legacy: ov-gpu patched ONNX (I0.5)." Technically true (code paths exist; README §Limits says so honestly) but advertises models this repo doesn't fetch. | **Fix in §4** |
| D2 | PROVENANCE quotes the seed message slightly abbreviated vs. actual commit message | leave — trivial |
| D3 | FastAPI title "intel-igpu-tts" in both repos | leave — lineage, arguably a feature |

## 4. Polish spec — one `docs:` commit on genai main (Grok R; no re-tag)

### 4.1 Docstring tidy (D1)

Replace the two fallback/legacy sentences in `scripts/kokoro_server.py` line 5 with:

> `ONNX-era backends (ort-cpu, ov-gpu patched) remain in the binary for lineage but are not fetched by this repo — see the shelf: https://github.com/bdk38/kokoro-igpu`

### 4.2 README: add §Open WebUI (after §Smoke, before §Configuration)

The appliance's most likely serving target; monorepo has it, appliance doesn't.

```markdown
## Open WebUI

Admin → Settings → Audio → OpenAI-compatible:

- Base URL: `http://<host>:8880/v1`
- Model: `kokoro` · Voice: `af_bella`
- Response splitting: **Paragraphs** or **None** recommended — the
  novel-shape first hit (see Performance honesty) can make
  **Punctuation** splitting look like skipped sentences while a
  fresh shape compiles. Warmed/cached traffic is fine on any mode.

Deploy: `KOKORO_TTS_CACHE=1` + chunk-shaped `KOKORO_WARM_TEXT`
pinned in the unit/env file retires the tax for repeat phrasing.
```

### 4.3 README: one-line igt fingerprint note (in §Run it, GPU start block)

> `# proof of offload: watch intel_gpu_top — Render/3D busy during synthesis`

That's the whole commit. Suggested message: `docs: WebUI wiring + docstring lineage tidy (Fable note_35)`.

## 5. Project board after this note

| Track | State |
|-------|-------|
| PoC (Product A) | **SHIPPED** — `poc-complete` |
| Prototype (Product B) | **SHIPPED** — `prototype-complete`; §4 polish pending |
| Default backend question | **RESOLVED** — ort-cpu = PoC face (monorepo), ovgenai-gpu = appliance default (genai repo) |
| Filings (4 drafts) | RESEARCH HOLD stands (notes/69) — next natural track when Nexus opens it |
| Product B backlog | blends-on-genai, chunk-overhead matrix, RAPL/E-core stress — each needs its own gate before work |
| Decoder fork O1–O4 | PARKED — revival requires new gate (notes/34) |

## 6. One-line

**R1 closure verified byte-level: the appliance diverges from the shelf by exactly the specified edits; prediction scored (cleaner than predicted, zero findings); one docs-only polish commit specified (WebUI wiring, igt line, docstring lineage tidy) — no re-tag — and with both products tagged, the open board is filings (on hold), the gated B backlog, and nothing else.**

---

*Fable (Chief Architect), 2026-08-08. Grok: execute §4 as one commit when convenient. Nexus: nothing binding here — polish is at your discretion; the next real decision on the board is when (whether) to lift the filings research hold.*
