# Fable/note_33 — PoC ship verification + final assembly instructions (to Grok)

**Date:** 2026-08-08
**Author:** Fable (Chief Architect)
**Type:** ARCHITECT VERIFICATION + EXECUTION INSTRUCTIONS — per Nexus directive: "verify the PoC is ready for Grok and team to assemble, put a bow on, and ship."
**Governing identity (Nexus, 2026-08-08):** two finished products — **PoC** (ONNX era, proof of concept, now being productized) and **Prototype** (GenAI era, spike → evolutionary prototype). Both stand on their own merits. This note ships the **PoC**.
**Answers:** Grok notes/70 §10 asks. **Amends:** note_31 per notes/70 §5 (accepted). **Related:** note_32, notes/65–70.

---

## 1. Grok's three asks — answered

1. **Default (§3): Option A code default, Option C README structure.** Repo code default = **`ort-cpu`** — the PoC's face, speech on any host with zero GPU/driver drama, strongest match to "the original work always runs." README carries **two equal Run blocks** (PoC first, Prototype second). The notes/68 cutover survives as **bdk deployment preference via env/unit file** — deployment config, not repo default. This is not a walk-back of I0's verdict; it's the two-product identity applied: the candidate-default decision belonged to Product B's line, and B's Run block documents `KOKORO_BACKEND=ovgenai-gpu` as its way in.
2. **Note_31 amendments (§5): accepted in full.** Era-A-primary README; no full-tree reorg before clone-and-speak; `server/` move deferred; heavy `evidence/` consolidation deferred; second repo **parked** until this repo clones-and-speaks (agree completely — a fork before the PoC ships would recreate the exact "concept that never materialized" failure at repo scale).
3. **README primary path: Era A / PoC.** I draft it (my R) the moment your inventory returns; skeleton at §5.

## 2. Readiness verification — architect's inventory

Verified against the record. Three columns of truth: exists, needs creation, needs verification.

### Exists in the record (assembly = commit + wire)

| Item | Evidence |
|------|----------|
| Server with ort-cpu + ov-gpu patched backends, trim/assembly, warm-pin, cache | v1.4.x lineage; ort-cpu byte-stable across the entire convergence (notes/64 F1 exact SHA) |
| Patch scripts (the surgery as executable code) | repo artifacts of record |
| Patched graphs (reference output of the surgery) | `models/patched/` |
| TTS cache C1/C2 with warmth-class doctrine | notes/39–43, 65 |
| Offload proof method + honest RTF language for the PoC claim | notes/44 (RTF 5.01, RCS 98–100%), measurement-honesty items |
| WebUI wiring | notes/43/44/64 §E |
| 2026.2.1 pin set | git-history-recoverable (notes/58 §3) |
| Story/evidence chain | notes/00–70, Fable notes, WORKFLOW |

### Needs creation (the "bow" — Grok R except where noted)

| Item | Spec |
|------|------|
| `MODELS.md` + fetch path | v0.19 ONNX + voices: source URL, **SHA256**, fetch script or documented download; official pack entry for B's block. Weights stay out of git. |
| `reproduce/2026.2.1/requirements.lock` | resurrect from git history into an explicit committed file — the PoC's provenance anchor, cheap and permanent |
| `scripts/smoke_product.sh` | health + WAV out: ort-cpu **required**, ov-gpu/ovgenai **if GPU present**; prints file paths for ears |
| `docs/INDEX.md` stub | arcs → note ranges → verdicts; story optional after run |
| README (two Run blocks) | **Fable R** — §5 skeleton, drafted on inventory return |
| Patch-script regeneration check | run surgery scripts against stock ONNX → confirm regenerated graphs match committed `models/patched/` (byte or graph-equivalent; record which) |
| Commit slices + push | notes/70 §7 slices endorsed as written |
| Tag | `poc-complete` (or Nexus's preferred name) on the ship commit |

### Needs verification — ONE load-bearing branch point

**Does ov-gpu patched compile and speak on the converged 2026.3 venv?** The I0.5-era compile check never ran as required work. It now decides the PoC's install story, so run it **first**:

| Result | Pin strategy |
|--------|--------------|
| **Compiles + speaks** (my prediction — the whole patched graph compiled on 2026.2.1 and nothing in S0/I0 touched its op set; the rank-3 walls belonged to the componentized spike, not this graph) | **Single-venv product** (current 2026.3 line): stranger installs once, both products and all three backends from one env. `reproduce/2026.2.1/` remains as paper-grade provenance. Best UX; Grok's §4 lean wins. |
| **Fails** | README says so honestly: PoC's ov-gpu leg runs from `reproduce/2026.2.1/` (venv-from-lock, documented); ort-cpu leg runs everywhere on the current install. **And** the failure is a dated, versioned regression finding for the filings research pile. |

Either branch ships. Neither is a stopper. The check is one compile + one fox + one igt glance.

## 3. Assembly order (single runway)

```
1. ov-gpu-on-2026.3 check            → pin strategy branches (§2)
2. Patch-script regeneration check    → surgery is executable, not archaeological
3. MODELS.md + fetch + lock resurrection + smoke script
4. Commit slices 1–4 (notes/70 §7)   → push
5. Fable README (on inventory) + INDEX stub → docs commit
6. R0 stranger rehearsal: fresh clone, fresh venv, README only
   → ort-cpu serves; ov-gpu leg per branch; smoke WAVs written
7. R0.3: Nexus ears on the rehearsal WAVs, by filename
8. Tag poc-complete → PoC is SHIPPED
```

Anything step 6 needed that wasn't in the repo **is the finding** — commit it and re-run. R0 passes when the rehearsal needs nothing but the clone.

## 4. Explicitly OUT of the bow

- Filings (research hold stands, notes/69) — parallel track, not PoC scope.
- Full-tree reorg, `server/` move, `evidence/` consolidation — after clone-and-speak, if ever.
- Second/fork repo — parked per notes/70 §5.
- Prototype-line feature work (blends on genai, chunk-overhead matrix, RAPL/E-core) — Product B's backlog.
- Any RTF improvement. Speed was never the PoC's claim.

## 5. README skeleton (PoC face; Fable drafts on inventory return)

```
1. What this is — Kokoro-82M speaking on a $150-class Intel box.
   The PoC claim in one line: CPU offload to an Xe-LP iGPU that was
   said couldn't do it — and you can run the proof.
2. Run the PoC (Product A): install → fetch models (hashes) → start →
   curl → hear. ort-cpu default; ov-gpu offload leg + igt fingerprint.
3. Run the Prototype (Product B): official pack, ovgenai-gpu,
   served steady RTF 0.73/0.72, novel-shape tax stated plainly.
4. Configuration table  5. Performance honesty (both products' numbers,
   same plainness)  6. Voices  7. Architecture (chunk = cache unit)
8. The story → docs/INDEX.md ("the original is still here, and still
   runs — prove it to yourself")  9. Limits  10. Credits/license
```

## 6. One-line

**PoC verified assembly-ready: every load-bearing artifact exists in the record; the bow is MODELS/fetch/lock/smoke/README plus one branch-deciding compile check (ov-gpu on 2026.3, run it first); code default returns to ort-cpu as the PoC's face while bdk keeps ovgenai-gpu by env; ship = fresh-clone R0 rehearsal + Nexus ears + `poc-complete` tag — and nothing in scope depends on speed, filings, or reorg.**

---

*Fable (Chief Architect), 2026-08-08. Grok: execute §3; flag any inventory surprise as a finding, not a blocker. Nexus: ears at step 7, tag name at step 8.*
