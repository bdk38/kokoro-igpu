# Contributors

This project was a human-led collaboration with two AI systems doing the heavy implementation and validation work on real hardware.

## Project lead

- **bdk38** ([@bdk38](https://github.com/bdk38)) — direction, decisions, listening tests, integration targets, and final product calls.

## AI contributors

GitHub’s automatic **Contributors** graph only lists GitHub user accounts that land commits. Grok and Claude are credited here and in the in-repo write-ups because that is the accurate record of who did the work.

### Claude (Anthropic) — “Fable” (Chief Architect)

- Role: diagnosis, graph surgery, experiment design, and architecture gates
- Write-up: [Fable/CONTRIBUTOR-Claude.md](Fable/CONTRIBUTOR-Claude.md)
- Close-out: [Fable/Fable-note_36-architect-closeout.md](Fable/Fable-note_36-architect-closeout.md)
- Major work:
  - identified the 3D linear Resize and dynamic-rank STFT blockers
  - authored `scripts/patch_kokoro_resize.py` and `scripts/patch_kokoro_v2.py`
  - authored `scripts/test_kokoro_ov_direct.py`, `scripts/tts_harness.py`, and the base `scripts/kokoro_server.py`
  - designed and iterated pad-tail trim through v1.1.5 (falsifiable predictions; terminal-gate removal)
  - Open WebUI Response Splitting diagnosis path and server wiring docstring guidance
  - S0/I0 gates, dual-track policy, PoC ship + GenAI seed specs (Fable notes 26–35)
  - architect close-out: dual-product board closed (note_36)

### Grok (xAI) — Orchestrator / Pipeline Engineer

- Role: hardware validation, measurement, ship-path execution, Open WebUI integration, dual-repo orchestration
- Write-up: [Grok/CONTRIBUTOR-Grok.md](Grok/CONTRIBUTOR-Grok.md)
- Close-out: [notes/77-orchestrator-closeout.md](notes/77-orchestrator-closeout.md)
- Major work:
  - executed every phase gate on Alder Lake UHD silicon
  - authored the canonical `notes/` phase reports
  - reconciled GPU quality metrics against human listening
  - wired Open WebUI and patched blend-voice / client compatibility in the server
  - validated OV-GPU proof path and later official GenAI path end to end
  - measured trim saga end-to-end (`notes/10`–`15`); closed v1.1.5
  - confirmed WebUI skip root cause (Punctuation × RTF≫1)
  - TTS cache C1+C2 ship, S0 probe execution (`S0-GO-product`), I0 integration (`I0-GO-default-candidate`)
  - R0/R1 stranger rehearsals; PoC + appliance productization; filings VERIFY pack (later PARKED)
  - dual-product WORKFLOW and orchestrator close-out (notes/77)

## How credit is represented in this repo

| Place | What it shows |
|-------|----------------|
| [CONTRIBUTORS.md](CONTRIBUTORS.md) | human-readable credit (this file) |
| [Fable/](Fable/) and [Grok/](Grok/) | first-person contributor write-ups |
| [notes/](notes/) | measurement log from the sandbox |
| Git commit history | currently authored as the project lead account for push/ops simplicity |
| GitHub Contributors graph | only GitHub accounts with commits/PRs; not a complete research credit list |

If you fork or extend this work, please keep the Fable/Grok write-ups and this file so the provenance stays honest.

## Operating model

- Team org chart, handoffs, and specialist pool: [WORKFLOW.md](WORKFLOW.md)

## Status rollups

- **Board (terminal):** [WORKFLOW.md](WORKFLOW.md) — both products SHIPPED; filings PARKED; decoder PARKED
- Architect close-out: [Fable/Fable-note_36-architect-closeout.md](Fable/Fable-note_36-architect-closeout.md)
- Orchestrator close-out: [notes/77-orchestrator-closeout.md](notes/77-orchestrator-closeout.md)
- Story index: [docs/INDEX.md](docs/INDEX.md)
- Early rollups (historical): [notes/17-repo-status-summary.md](notes/17-repo-status-summary.md), [notes/16-project-status.md](notes/16-project-status.md), [notes/16-project-status-fable.md](notes/16-project-status-fable.md)

## Sibling product

- GenAI appliance: https://github.com/bdk38/kokoro-igpu-genai (`prototype-complete`) — same human + Fable + Grok credit model
