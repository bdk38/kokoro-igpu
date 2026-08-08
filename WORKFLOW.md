# Team Workflow — Kokoro iGPU TTS

**Status:** both products **SHIPPED** — PoC `poc-complete` + Prototype `prototype-complete`; filings **RESEARCH HOLD**
**Audience:** Nexus (bdk), Chief Architect (Fable), Orchestrator (Grok 4.5)  
**Sandbox (lab monorepo):** `/data/intel-igpu-tts` → https://github.com/bdk38/kokoro-igpu  
**Appliance (Product B):** `/data/kokoro-igpu-genai` → https://github.com/bdk38/kokoro-igpu-genai  
**Related:** [CONTRIBUTORS.md](CONTRIBUTORS.md), `Fable/`, `Grok/`, `notes/`, `notes/00-host-inventory.txt`, `docs/INDEX.md`

This document freezes the collaboration structure so it can be referenced in-chat and shared across agents. It reflects what already worked in the **Warm Bucket Fix** ship-path loop (notes/11–18), the **Kokoro v1.0 Peek** research arc (notes/19–24), the **componentized decoder spike** closeout (notes/25–34), **v1.2.0 TTS cache** (notes/39–44), **S0 official GenAI** (notes/45–53), **I0 integration** (notes/54–67), and **dual-product ship** (notes/70–74, Fable note_33–35) — not a greenfield fantasy org chart.

**Current phase (2026-08-08):** Two finished products on two remotes.

| Product | Remote | Tag | Default | Face |
|---------|--------|-----|---------|------|
| **A — PoC** | `bdk38/kokoro-igpu` (this sandbox) | **`poc-complete`** @ `f2ff370` (v1.5.1) | **`ort-cpu`** | ONNX v0.19 + patches; ov-gpu legacy proof leg |
| **B — Prototype** | `bdk38/kokoro-igpu-genai` | **`prototype-complete`** @ `8987f74` (v2.0.0) | **`ovgenai-gpu`** | Official Kokoro-82M int8 GenAI appliance |

R0 (PoC stranger clone) and R1 (genai stranger clone) both **PASS** with Nexus ears. Filings VERIFY pack under **RESEARCH HOLD** (notes/69) until Nexus clears duplicates. Product B optional polish: Fable note_35 docs-only (no re-tag). Decoder spike remains **PARKED**. B backlog (blends, chunk matrix, RAPL) needs new gates before work.

---

## Org chart

```text
                    THE NEXUS / SYSTEMS DIRECTOR
                              (bdk / me)
                                 |
              +------------------+------------------+
              |                                     |
              v                                     v
     CHIEF ARCHITECT                    ORCHESTRATOR / PIPELINE ENG
         (Fable)                              (Grok 4.5)
         Claude                                 xAI
                                                    |
                         +--------------------------+--------------------------+
                         |                          |                          |
                         v                          v                          v
                  THE MECHANIC              SPECIALIST POOL            (same pool)
               (Grok Build — CLI)         parallel sub-agents         scaled as needed
                                                    |
                                    +---------------+---------------+--- ...
                                    |               |               |
                                    v               v               v
                              The Profiler   The Validator   ad-hoc specialists
                              (metrics/JIT)  (parity/ear/    (research, stash,
                                              go-kill)        docs, repro, …)
```

**Structural rule:** Fable and Grok are **peers under Nexus**, not a chain of command through each other. Architecture proposes; silicon disposes; Nexus decides.

**Scale rule:** The Orchestrator is **not limited to two specialists**. Profiler and Validator are the default standing hats. Additional specialists are spun up via **parallel sub-agents** whenever the work fan-out justifies it (research threads, multi-log greps, dual-path repros, doc stashing, etc.).

---

## Roles

### Nexus / Systems Director — bdk

- Mission, priorities, and kill switches
- Product defaults (e.g. ort-cpu vs ov-gpu demo path)
- Ear / listening gate on quality claims
- Greenlight ship, spike, park, or upstream filing
- Final credit and repo direction

Does **not** need to run probes or author graph patches unless choosing to.

### Chief Architect — Fable (Claude)

- Diagnosis, graph surgery, export/seam design
- Falsifiable experiment design (predicted PASS/FAIL branches, often with expected durations/log signatures)
- Scripts, server features, and tooling authorship when in design mode
- Strategic framing (black-box tier vs componentized fork vs official GenAI path)
- Handoffs as `Fable/note_N` (+ script paths when applicable)
- May green-light technical readiness (e.g. “drafts are filing-ready”, S0 gate sign-off); Nexus still owns external actions (GitHub issue submit, product default)

Does **not** own final hardware truth on bdk-server. May propose measurements; Orchestrator runs and records them. May catch measurement methodology bugs (see Warm Bucket Fix / note_11 cold vs steady) — Orchestrator treats those as first-class blockers.

### Orchestrator / Pipeline Engineer — Grok 4.5

- Own the run plan on the host: constraints, sequencing, risk calls
- Dispatch Mechanic, Profiler, Validator, and any extra specialists
- QC all delegated work (Build diffs, sub-agent reports, probe outputs)
- Author decisive measurement notes under **`notes/NN-*.md`** (canonical location — not only `Grok/`)
- Fold Nexus ear verdicts back into the same note before the next Architect turn
- Push back on architecture when data disagrees (peer challenge)
- Keep ship path and spike/probe path from silently stealing each other
- Host/repo hygiene: safe process control, no secrets in chat, evidence packing for upstream

Primary interface to Nexus for “what did silicon say?”

---

## Specialist pool (under Orchestrator)

Specialists are **roles the Orchestrator wears or delegates**, not fixed headcount. Standing defaults:

| Specialist | Charter | Typical outputs |
|------------|---------|-----------------|
| **The Mechanic** (Grok Build CLI) | Multi-file implementation against a locked design/protocol | Code in `scripts/`, server changes, export scaffolding, `spike/` probes |
| **The Profiler** | Timing, device proof, cache/JIT behavior, resource traces | RTF tables, cold/warm matrices, `intel_gpu_top` / exec-device evidence |
| **The Validator** | Correctness and product-claim gates | Parity/maxdiff, ear-aligned verdicts, go/kill write-ups, README-honesty checks |

### Elastic specialists (parallel sub-agents)

When useful, Orchestrator may run **2–5 parallel sub-agents** (or more sequential waves), for example:

- **Researcher** — GitHub/HF/papers/OpenVINO internals → stash under `/data/kokoro-openvino` or `/data/github` or briefs in `notes/`
- **Repro technician** — isolated one-command repros for upstream issues
- **Artifact librarian** — normalize logs, inventories, SHA256, path indexes
- **Doc/honesty editor** — draft issue text or README corrections *after* Validator sign-off
- **Dual-path runner** — e.g. ort-cpu vs ov-gpu matrices in parallel when isolation allows

Naming new specialists in a note is encouraged when it clarifies the handoff; they do not require a chart revision first.

**Sub-agent model choice:** default **non/low-reasoning** for retrieval, log-grep, and fan-out. Orchestrator may pick a **reasoning** worker per dispatch when the task is credibility-sensitive (e.g. drafting one-command upstream repros). That is judgment, not a fixed chart rule.

### Mechanic discipline

Grok Build is powerful (`--always-approve`). Default constraints:

- Narrow prompt, explicit cwd, definition of done
- Implement against a **fixed** measurement or design plan — including a **written** go/kill gate when the work is spike/probe-path
- No drive-by architecture or README product claims
- Orchestrator always QC: diff review, tests/probes, residual risk

**Ship-path freeze (mechanical):** During spike/probe sessions, Build/Mechanic work lives under a dedicated tree (default `spike/` or `spike/ov263-genai/`) and/or a spike branch. **Off-limits to Build prompts** unless Nexus explicitly lifts the freeze **or the active gate is a ship-path integration (I0) with written bars**:

- `scripts/kokoro_server.py` — **I0 may edit** under Fable note_29 + notes/54 (version bump, new backends only; no silent default flip)
- `models/patched/` (ship ONNX) — still read-only unless a dedicated ship gate says otherwise
- product defaults / README **performance claims** — Validator first; flags/tables OK

If a spike/probe result needs a server or patched-model change, it returns through the normal **ship-path loop** (Fable note → probe → ears/Validator → commit), not a side edit from a spike Build run.

Prefer Build for implementation loops; prefer Orchestrator + Profiler/Validator for measurement authorship.

---

## Handoff contract (default interface)

Long cross-agent status prose is optional. The durable interface is files:

```text
Nexus
  │  priority / greenlight / ear verdict (file-level PASS/FAIL when audio)
  ▼
Fable  ──writes──►  Fable/note_N
                    (+ script path, predicted branches, kill criteria)
  │
  ▼
Grok   ──runs────►  probes / Build / sub-agents
       ──writes──►  notes/NN-short-slug.md          ← canonical
                    artifacts/…  (WAVs, tables)
                    artifacts/logs/… when logs back WAVs
                    (decisive table + product implication)
  │
  ▼
Nexus  ──ears────►  named PASS/FAIL per artifact (when quality in scope)
  │
  ▼
Grok   ──updates─►  same notes/NN-*.md with ear verdict + root-cause for Fable
  │
  ▼
Nexus  ──decides─►  ship | iterate | park | upstream | spike go/kill
```

Optional: short pointer stubs under `Grok/` are fine; **do not** let diverging full write-ups live only there (Warm Bucket Fix: moved canonical notes into `notes/`).

### Note expectations

**Fable → team**

- What’s changing and why
- Exact script/path to run (if any)
- Predicted branches (PASS/FAIL or go/kill), including expected log signatures / durations when known
- What *not* to touch (ship path freeze, version pins, byte-same trim, etc.)

**Grok → team**

- What was run (commands, versions, backend, cold vs steady methodology)
- Decisive table (not only narrative)
- Verdict in one line
- Product implication (docs/default/API honesty)
- Artifacts + log paths (WAVs under `artifacts/vNNN/`; supporting sanitized logs when they explain the WAVs)
- Open questions / recommended next gate
- After ears: update the **same** note so Fable does not chase chat archaeology

**Nexus → team**

- Approve, redirect, park, or kill
- Ear pass/fail **by filename** when quality is in scope (e.g. “s2_wallet moan; others PASS”)
- External actions: GitHub issue filing, token/credential setup, final product defaults

---

## Acceptance lenses (do not collapse)

| Lens | Owner hat | Question |
|------|-----------|----------|
| Design soundness | Architect | Is the seam/experiment the right bet? |
| Performance / mechanism | Profiler | What does the machine do, and why? |
| Truth / shippability | Validator | Is it correct, and may we claim it? |
| Priority | Nexus | Is this the work we should be doing now? |

**Hard rule that already saved us:** no README or product-default wording change until Validator signs the relevant matrix.  
Examples:

- `KOKORO_WARM_BUCKETS` warms a **shape** (and must use a real synthesize path), not arbitrary Read Aloud traffic (notes/19–20; Warm Bucket Fix v1.1.6 zeros-vs-real-text)
- WebUI **Response Splitting** can look like “server skips sentences” under ov-gpu RTF ≫ 1 — diagnose client split mode before blaming trim (notes/15)
- Never file or ship a steady-state RTF claim that silently averages **cold first infer** (Fable note_11 / notes/18)
- S0 official-path claims use the **written verdict vocabulary** only (`S0-GO-product` / `S0-GO-demo` / …) — never “GPU works” without offload proof + methodology

### Measurement honesty (Profiler + Validator)

Standing rules from Warm Bucket Fix (+ spike/S0):

1. **Name the methodology** in every timing note: cold first-infer vs steady-state; warmup discarded or not; direct `ov.Core` vs server bucket path vs GenAI pipeline.
2. **Discard warmup** (or report cold separately) before quoting mean RTF for product/upstream.
3. **Pre-warm must exercise the real request path** — dummy/all-zero pads can “succeed” without retiring lazy setup for real speech.
4. **Server vs direct** comparisons must call out token bucketing / pad-to-bucket effects on RTF denominators.
5. **Ears beat metrics** when they disagree; metrics explain ears, they do not override them on quality threads.
6. **Upstream packs** need live captures on this host, placeholder-free drafts, and cross-links — methodology bugs are filing blockers.
7. **Record stack identity** when results may age: OpenVINO wheel version, GenAI version, `intel-opencl-icd` / IGC / kernel (see host inventory + S0 A3).
8. **Gates before measurements.** Softening a bar after numbers exist requires Nexus + written amendment — not a quiet edit.

---

## Dual critical paths (+ probe lane)

Keep these explicit so the org chart does not become silent parallel projects:

| Path | Goal | Status (2026-08-08) | Default owner emphasis |
|------|------|---------------------|------------------------|
| **Product A — PoC (monorepo)** | Clone → install → hear ONNX-era Kokoro (ort-cpu + ov-gpu proof) | **SHIPPED** — tag `poc-complete` @ `f2ff370` (v1.5.1); R0 PASS (notes/71–72) | Maintenance / honesty only unless new gate |
| **Product B — Prototype (appliance)** | Thin GenAI appliance; default `ovgenai-gpu` | **SHIPPED** — tag `prototype-complete` @ `8987f74` (v2.0.0); R1 PASS (notes/74); optional note_35 docs polish | Docs/backlog gates only |
| **Spike path (componentized decoder)** | Seam B → static-T decoder → OV-GPU realtime | **PARKED** (not GO) — notes/33–34; RCA notes/29–32. Revival = **new Fable gate + Nexus ack only** | — |
| **Probe path (S0)** | Official OV 2026.3 GenAI Kokoro on this Xe-LP | **CLOSED — `S0-GO-product`** (notes/45–53). Probe scripts remain under `spike/ov263-genai/`; side venv deleted after convergence | — |
| **Integration path (I0)** | Official GenAI as selectable backend + default decision | **CLOSED — `I0-GO-default-candidate`** (notes/54–67). Defaults **resolved by product face**: monorepo = ort-cpu; appliance = ovgenai-gpu | — |
| **Filings** | Upstream OpenVINO issues (shape-JIT, f16 MatMul, conv-ref) | **VERIFY done · RESEARCH HOLD** (notes/69, `issues/submit/`) — Nexus duplicate check before submit | Nexus + Orchestrator |

Nexus chooses which path is active for a given session. Probe/spike does not overwrite ship without an explicit call. Ship freeze enforcement is under **Mechanic discipline** above. **Do not silently change product defaults** across remotes.

### Board (open)

| Item | State |
|------|--------|
| Filings research hold | **Open** — lift only when Nexus clears file/comment/drop per draft |
| note_35 genai docs polish | Docs-only on appliance; **no re-tag** |
| Product B backlog | blends-on-genai, chunk-overhead matrix, RAPL/E-core — **each needs own gate** |
| Decoder O1–O4 | **PARKED** |

### Ship queue (completed — historical)

1. ~~**v1.1.8 / v1.2.0 cache**~~ — **DONE** (`8893249` C1+C2; notes/39–44)  
2. ~~**S0 official GenAI probe**~~ — **DONE `S0-GO-product`** (notes/45–53)  
3. ~~**I0.1–I0.5**~~ — **DONE** backend + RTF + regression + ov-gpu legacy (notes/54–67)  
4. ~~**Default decision**~~ — **RESOLVED** dual-face (notes/68, 70–71, Fable note_33–34)  
5. ~~**PoC productize + R0**~~ — **DONE** `poc-complete` (notes/71–72)  
6. ~~**Prototype segregate + seed + R1**~~ — **DONE** `prototype-complete` (notes/73–74)  
7. **Upstream filing session** — VERIFY pack ready; **RESEARCH HOLD** until Nexus  
8. **Parked:** componentized fork O1–O4 until new gate  

### Ship-path loop (Warm Bucket Fix pattern)

```text
Fable patch + note  →  Grok probe matrix + notes/NN  →  Nexus ears by filename
        ↑                                                      │
        └──────── Grok updates same note with FAIL modes ←─────┘
                         → Fable next patch or CLOSE thread
```

Close the thread only on **explicit Nexus ear PASS** across the agreed probe set, not on log-only green.

### Probe-path loop (S0 pattern) — **completed 2026-08-07**

```text
Gate written (notes/36) → Fable sign-off (+ amendments 36b) → Nexus ack + priority
    → Grok side-env / spike/ov263-genai isolation → S0.1…S0.5 + A1–A3 report fields
    → notes/NN results + ears → verdict word only → stop
```

**Outcome:** `S0-GO-product` (notes/52–53). Optional S1/S2/S3 only on explicit Nexus open.

### Integration-path loop (I0 pattern) — **completed 2026-08-08**

```text
Gate (Fable note_29) → Grok lock (notes/54 G1–G6) → Fable accept (note_30) → Nexus ack (notes/55)
    → I0.1 voice ears (notes/56) → filings submit OR Nexus waiver (notes/58)
    → ship venv convergence 2026.3+GenAI (notes/59) → I0.2 backend → I0.3 served RTF
    → I0.4 regression → I0.5 ov-gpu disposition → verdict I0-GO-default-candidate
    → dual-product face (PoC monorepo ort-cpu + GenAI appliance) → R0/R1 → tags
```

**Outcome:** both products tagged; default question closed by **product boundary**, not a single-repo flip.

---

## Tooling map (Orchestrator)

| Need | Tool / path |
|------|-------------|
| Host inspect, probes, servers, git QC | Open Terminal |
| Multi-file code implementation | Grok Build CLI (`grok`) — **Mechanic** |
| Parallel research / retrieval / fan-out | Sub-agents — default **non/low-reasoning**; reasoning OK per-dispatch for hard repros |
| Durable team memory | `notes/`, `Fable/note_*`, this file, `CONTRIBUTORS.md` |
| Host/stack truth | `notes/00-host-inventory.txt` (refresh when runtime/driver changes) |
| Model/export research stash | `/data/kokoro-openvino` |
| Upstream source reference | `/data/github/openvino`, `openvino.genai`, `openvino_notebooks` |
| Evidence WAVs + supporting sanitized logs | `artifacts/` (Git LFS); raw `logs/` usually gitignored |
| Large ONNX/weights | **Download locally** — not in git (repo convention) |
| Lab monorepo (Product A) | `/data/intel-igpu-tts` — github.com/bdk38/kokoro-igpu — default **ort-cpu** v1.5.1; tag `poc-complete` |
| GenAI appliance (Product B) | `/data/kokoro-igpu-genai` — github.com/bdk38/kokoro-igpu-genai — default **ovgenai-gpu** v2.0.0; tag `prototype-complete` |
| Project runtime (lab) | `/data/intel-igpu-tts/venv` — OpenVINO **2026.3** + GenAI |
| S0 probe scripts | `spike/ov263-genai/` (historical); side venv **deleted** after convergence (notes/59, 74) |
| Official GenAI pack | HF `OpenVINO/kokoro-82M-int8-ov` → `models/kokoro-82M-int8-ov/` (both repos; download, not git) |
| Prototype evidence | `artifacts/prototype/` (S0/I0/R1 WAVs); map in `artifacts/prototype/README.md` |
| OV compile cache | Versioned dirs under `cache/` (e.g. `openvino-2026.2.1-drv2622/`, 2026.3 dirs) |
| Filings drafts | `issues/submit/` (VERIFY bodies + attachments); research hold notes/69 |

### Host / repo hygiene (learned the hard way)

- **No secrets in chat.** Tokens via private credential store / TTY loader (e.g. `~/.config/git/approve-github-token.sh`), never pasted into Open WebUI.
- **Process control:** avoid broad `pkill` patterns that match the controlling shell; use PID files or narrow filters when restarting `kokoro_server`.
- **Shell quoting:** multi-line probes and draft fills → write a `.py` under `scripts/` or `/tmp` and run it; heredoc/quoting breakage wasted cycles in Warm Bucket Fix. Prefer explicit venv paths (`venv/bin/python`) over `source` under non-bash runners.
- **Git credit:** split commits by concern when practical; `Co-authored-by` Fable + Grok trailers; full narrative credit stays in `CONTRIBUTORS.md` + contributor write-ups.
- **Statuses:** keep dual full statuses when both agents roll up a phase; add a short compiled summary for the repo (pattern: notes/16 Grok + notes/16-fable + notes/17 summary; spike: notes/33×2 + notes/34).
- **LFS:** artifacts (WAVs, and sanitized logs that support them) in LFS; models stay out unless Nexus explicitly changes policy.

---

## Phase RACI templates

Abbreviations: **R**esponsible, **A**ccountable, **C**onsulted, **I**nformed.  
Nexus reprioritizes which template is active. Do not run ship + full probe at full blast without an explicit call.

**Reference, not process:** Mid-session, the **handoff contract** and the **four acceptance lenses** govern. If a RACI cell conflicts with those, follow the handoff contract. RACI tables are orientation aids — do not block work to keep them perfectly synchronized.

### A. Ship-path quality loop (Warm Bucket Fix lens)

| Work package | Nexus | Fable | Grok orch. | Mechanic | Profiler | Validator |
|--------------|:-----:|:-----:|:----------:|:--------:|:--------:|:---------:|
| Priority / close-thread authority | A | C | C | — | I | C |
| Patch design + server/script change | I | R | C | C | I | I |
| Probe matrix + notes/NN + artifacts | I | C | A | I | R | C |
| Ear PASS/FAIL by filename | R/A | I | I | — | I | C |
| Fold ears into note + FAIL root-cause | I | C | R | — | C | R |
| Product/docs honesty (WebUI, RTF, warm) | A | C | R | I | C | R |
| Upstream issue captures + draft fill | I | C | R | — | R | R |
| File issues on GitHub | A (submit) | C (green-light text) | C | — | I | C |
| Repo commit / LFS / push | A | I | R | C | I | I |

### B. Historical — componentized decoder spike (PARKED)

Kept for provenance and any **future revival** (which requires a **new** gate note, not this table alone).

| Work package | Nexus | Fable | Grok orch. | Mechanic | Profiler | Validator |
|--------------|:-----:|:-----:|:----------:|:--------:|:--------:|:---------:|
| Mission / go-kill authority | A | C | C | — | I | C |
| Seam B design, strict-load + hooks plan | A (priority) | R | C | I | I | C |
| Decoder-only export / probe code | I | C | A | R | I | I |
| Cold/warm/restart + CACHE_DIR matrix | I | C | A | I | R | C |
| Parity / ear / spike go-kill write-up | A (final) | C | A | I | C | R |
| Ship-path freezes | A | C | R | I | I | R |
| Written go/kill gate before impl | A (ack) | R | C | I | C | C |

Closeout: **PARKED** — notes/33–34. Do not extend G3 without Nexus reset + new gate.

### C. S0 probe lens (official OV 2026.3 GenAI Kokoro)

| Work package | Nexus | Fable | Grok orch. | Mechanic | Profiler | Validator |
|--------------|:-----:|:-----:|:----------:|:--------:|:--------:|:---------:|
| Mission / ack / priority vs ship queue | A | C (signed) | C | — | I | C |
| Gate text (36 + 36b amendments) | A (final ack) | R sign-off | R draft/fold | — | I | C |
| Side env + `spike/ov263-genai` probes | I | C | A | R | I | I |
| Offload + RTF + A1 shape-JIT report | I | C | A | I | R | C |
| Precision (A2) + driver versions (A3) | I | C | A | I | R | C |
| Ears S0.4 by filename | R/A | I | I | — | I | C |
| Verdict word + filing implication | A | C | R | — | C | R |
| Ship freeze enforcement | A | C | R | I | I | R |
| Optional S1/S2 open | A | C | C | I | C | C |
| Optional S3 (fork revival gate) | A | R (new note) | C | I | C | C |

**S0 gate was dual-acked and executed:** notes/36 + 36b + Nexus ack → **S0-GO-product** (notes/52–53). Defining success after seeing results remains an anti-pattern for future gates.

### D. I0 integration lens (official GenAI as selectable backend)

| Work package | Nexus | Fable | Grok orch. | Mechanic | Profiler | Validator |
|--------------|:-----:|:-----:|:----------:|:--------:|:--------:|:---------:|
| Mission / ack / default-later | A | C | C | — | I | C |
| Gate text + amendments (G1–G6) | A (ack) | R design | R lock fold | — | I | C |
| Filings waiver or submit | A | C | R record | — | I | C |
| Ship venv convergence 2026.3+GenAI | A | C | R | C | I | C |
| `ovgenai-*` backend + per-chunk + cache | I | C | A | R | I | I |
| Served RTF / novel-tax (I0.3) | I | C | A | I | R | C |
| ort-cpu regression (I0.4) | I | C | A | I | C | R |
| Ears I0.1/I0.2 by filename | R/A | I | I | — | I | C |
| Verdict word + default-question open | A | C | R | — | C | R |
| Ship freeze (no silent default flip) | A | C | R | I | I | R |

---

## What this model is optimized for

1. **Falsifiable loops** — Architect predicts; Orchestrator measures; Nexus ears/decides.  
2. **Honest product claims** — Validator separates cold vs steady, shape-warm vs varied traffic, server bug vs WebUI config, official-path demo vs product-default.  
3. **Elastic horsepower** — parallel sub-agents when fan-out helps; no fake fixed headcount; default non/low-reasoning workers with per-dispatch exceptions.  
4. **Peer challenge** — Fable ⟂ Grok under Nexus; measurement methodology bugs are blockers, not nits.  
5. **Provenance** — canonical `notes/` + artifacts beat chat archaeology; dual statuses + short repo summary when a phase closes.  
6. **Park with evidence** — negative results (decoder spike) keep RCA and filing value; revival is gated, not emotional.

---

## Quick pointers for Fable onboarding (current)

| Doc | Why |
|-----|-----|
| This file | Org, handoffs, freezes, dual-repo board |
| `docs/INDEX.md` | Story map + product pointers |
| `notes/00-host-inventory.txt` | Live host/stack versions |
| `notes/70`–`74` | Finished-product boundary, PoC/R0, Prototype/R1 |
| `notes/52`–`53`, `67` | S0 + I0 verdict closeouts |
| `notes/69` + `issues/submit/` | Filings VERIFY · research hold |
| `Fable/Fable-note_33`–`35` | PoC ship, genai seed/R1, polish spec |
| `notes/34-spike-closeout-summary.md` | Decoder spike park rollup |
| Sibling README | https://github.com/bdk38/kokoro-igpu-genai |

---

## Revision history

| Date | Change |
|------|--------|
| 2026-08-07 | Initial workflow captured from Nexus org chart + Kokoro v1.0 Peek operating practice; specialist pool defined as elastic via parallel sub-agents. |
| 2026-08-07 | Incorporated **Warm Bucket Fix** operating lessons: canonical `notes/` path; ear-by-filename loop; measurement honesty (cold/steady, real-path warm); ship-path RACI template; repo/LFS/credential hygiene; upstream draft discipline. |
| 2026-08-07 | **Fable pre-spike review** (`Fable/pre-spike_discussion`): written go/kill gate required before decoder-export impl; mechanical ship freeze (`spike/` + server/patched ONNX off-limits to Build); RACI demoted to reference under handoff contract; sub-agent reasoning left to per-dispatch judgment. |
| 2026-08-07 | **Spike closeout:** componentized decoder export **PARKED** (not GO). Dual statuses `notes/33-spike-status-{grok,fable}.md` + summary `notes/34-spike-closeout-summary.md`. Measurement chain `notes/25`–`32`. Ship path never broken; next product candidate response/chunk cache; upstream packs green-lit Architect-side. |
| 2026-08-07 | **Dual-track env policy** (Fable note_27 / notes/38): ship completes on OV **2026.2.1** wheel + current drivers; S0 uses 2026.3 side venv; pre-registered walk-back ladder; notes/37 superseded-in-part. |
| 2026-08-07 | **Post-park operating update:** ship queue explicit; spike path marked PARKED with revival rule; **S0 probe path** added (notes/36+36b, Fable note_26 sign-off, awaiting Nexus); RACI template C for S0; OpenVINO **2026.3** env + `/data/github` arsenal + host inventory refresh pointers; measurement honesty items 7–8 (stack identity, gates-before-numbers). |
| 2026-08-08 | **Post–S0 / I0 refresh:** v1.2.0 cache shipped; S0 closed `S0-GO-product`; I0 path + RACI D; ship queue rewritten; tooling (GenAI pack, filings, convergence); dual-track ending under notes/58–59 waiver+convergence; default still ort-cpu. |
| 2026-08-08 | **Dual-product ship closeout:** PoC monorepo tagged `poc-complete` (R0); GenAI sibling `kokoro-igpu-genai` tagged `prototype-complete` (R1); defaults resolved by product face (ort-cpu vs ovgenai-gpu); I0 closed; filings remain RESEARCH HOLD; tooling map dual-remote; open board = filings + gated B backlog + optional note_35 docs polish. |

*Maintainer: Orchestrator (Grok 4.5) under Nexus direction. Fable should treat this as the shared org reference unless Nexus supersedes it.*
