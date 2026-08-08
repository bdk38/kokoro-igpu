#!/usr/bin/env python3
"""v1.1.8 shape-key experiment (Fable note_19 follow-up).

QUESTION
--------
notes/19 showed warm state on ov-gpu does not transfer across content
within a compiled bucket. Hypothesis (Fable): warm is keyed on the EXACT
internal dynamic shape -- the total output frame count produced by the
duration predictor -- not on the text itself. The GPU plugin JIT-compiles
shape-specialized kernels per concrete internal shape, cached in-memory
per process; CACHE_DIR does not persist them.

Discriminating test: two DIFFERENT texts A and B whose bucket-96 padded
inference yields EXACTLY equal raw (pre-trim) sample counts. Fresh
process, run A cold, warm it up, then B first-ever:

  B WARM  -> warm is keyed on internal shape; content irrelevant.
             (README fix: "pre-warm pins a shape, not a bucket";
              upstream issue: per-shape kernel JIT not persisted by
              CACHE_DIR, ~15-25 s per novel shape on Xe-LP f32.)
  B COLD  -> keying is deeper than total frame count (per-token duration
             vector? something stranger). Bigger upstream story.

DESIGN
------
Phase 1 (this process): compile bucket 96 (cache hit expected), then run
~72 novel candidate sentences ONCE each, recording raw n_samples + wall +
process-CPU time per infer. Output frame counts live on a discrete
lattice (frames x hop), so exact collisions among 72 candidates are very
likely. Also: re-run candidate #1 and the last candidate at the end
(warm-survival check after ~70 intervening novel infers). Writes
phase1_matrix.json and an auto-picked (A, B, control C) into
phase1_picks.json. Every phase-1 infer is also a fresh cold-RTF sample --
free distribution data for the upstream report.

Phase 2 (MUST be a fresh process -- in-memory kernel cache resets): reads
the picks, asserts A/B sample-count equality reproduces, then runs:

    1. A #1            expect COLD  (~16-25 s)
    2. A #2            expect MID/WARM (v117: 2nd hit not always steady)
    3. A #3            expect WARM  (~3-4 s wall, RTF~0.9 trimmed-basis)
    4. B #1  <== THE TEST (first-ever text, same internal shape as A)
    5. B #2            completes the picture either way
    6. C #1            control: different shape, never seen -> expect
                       COLD (proves the process still *can* be cold, so a
                       warm B wasn't some global warm-up)
    7. A @ speed=1.05  bonus: same text, changed durations -> new shape
                       -> expect COLD if shape-keyed (key is frames, not
                       text)

CPU-time instrumentation: kernel JIT is host-CPU work. For each infer we
record process CPU seconds (all threads). The discriminator is the
EXCESS: if (cold_wall - warm_wall) ~= (cold_cpu - warm_cpu), the extra
~15-20 s is host-side compilation, not GPU execution. (Ratio alone can't
be used -- the plugin may busy-poll even when warm.)

RUN (Grok)
----------
    cd /data/intel-igpu-tts
    source scripts/env.sh
    export KOKORO_MODEL=models/patched/kokoro-v0_19.gpu4d.stft.onnx
    # server STOPPED -- this probe owns the GPU directly, no HTTP.
    python scripts/probe_v118_shape_key.py --phase 1   # ~25-35 min
    python scripts/probe_v118_shape_key.py --phase 2   # fresh proc, ~2-3 min

Optional: --device CPU on phase 1 checks whether ov-cpu is content-cold
at all (separate question, cheap).

Artifacts: artifacts/v118/phase1_matrix.json, phase1_picks.json,
phase2_result.json. No WAVs by default (raw sample counts are the data);
--save-wavs if ears are wanted.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kokoro_server as ks  # noqa: E402  (tokenizer, style, OvBackend)

BUCKET_TARGET = 96
WARM_WALL_S = 6.0    # wall-time bands for 4-7 s raw audio at bucket 96
COLD_WALL_S = 12.0   # (v117: cold 16-25 s, warm 3-4 s; MID between)

# ----------------------------------------------------------------------
# candidate pool -- 72 novel sentences, 8-13 words, targeted to land in
# bucket 96 (real tokens roughly 40-90). None previously used in probes.
# ----------------------------------------------------------------------
POOL = [
    "The old red barn stood alone beside the frozen river.",
    "A gentle rain fell softly on the quiet village square.",
    "My brother painted the garden fence a deep shade of green.",
    "The tired sailor watched the harbor lights from the pier.",
    "She placed the copper kettle on the iron stove to boil.",
    "Every morning the baker stacks warm loaves in the window.",
    "The children built a crooked castle from wet gray sand.",
    "A single candle flickered in the dusty library window.",
    "The mountain trail curved sharply above the misty valley.",
    "He folded the letter twice and slid it under the door.",
    "Two black horses grazed slowly in the frosted meadow.",
    "The clockmaker adjusted the tiny gears with steady hands.",
    "Autumn leaves drifted across the empty tennis court.",
    "The ferry crossed the channel before the storm arrived.",
    "Grandmother kept her silver thimble in a velvet box.",
    "The young pilot checked the fuel gauge one more time.",
    "A curious raccoon opened the latch on the garden gate.",
    "The professor wrote three long equations on the board.",
    "Fresh snow covered the rooftops of the sleeping town.",
    "The fisherman mended his torn net beside the lighthouse.",
    "She hummed a quiet tune while sorting the mail.",
    "The green tractor pulled a heavy cart of ripe apples.",
    "A distant train whistle echoed through the pine forest.",
    "The tailor measured the wool coat with a cloth tape.",
    "Bright kites danced above the windy autumn beach.",
    "The librarian stamped each book with careful attention.",
    "Warm bread and honey waited on the kitchen table.",
    "The carpenter sanded the oak shelf until it shone.",
    "A gray heron stood motionless in the shallow marsh.",
    "The night nurse checked the charts under a dim lamp.",
    "Purple clouds gathered slowly over the western hills.",
    "The mechanic tightened the last bolt on the engine.",
    "A small boat drifted past the reeds at sunset.",
    "The gardener trimmed the hedge into a neat square.",
    "Cold wind rattled the shutters of the old farmhouse.",
    "The violinist tuned her strings before the concert began.",
    "A striped cat napped on the sunny porch railing.",
    "The miners followed the narrow tunnel toward the light.",
    "Steam rose gently from the mug of black coffee.",
    "The archer drew the bow and held her breath.",
    "Yellow buses lined the curb outside the brick school.",
    "The chef sliced the onions with quick even strokes.",
    "A lone wolf crossed the ridge under the full moon.",
    "The clerk counted the coins twice before closing the drawer.",
    "Soft moss covered the stones along the forest path.",
    "The dancer practiced the same turn until midnight.",
    "A rusty windmill creaked above the dry wheat field.",
    "The twins raced their bicycles down the gravel lane.",
    "Heavy fog rolled off the bay before dawn.",
    "The potter shaped the clay bowl on the spinning wheel.",
    "A red fox slipped quietly between the garden rows.",
    "The umpire brushed the plate and called for play.",
    "Thin ice cracked near the edge of the pond.",
    "The welder lowered his mask and struck the arc.",
    "A paper lantern swayed above the crowded market stall.",
    "The shepherd whistled once and the dog circled the flock.",
    "Loose gravel slid beneath the climber's worn boots.",
    "The judge read the verdict in a level voice.",
    "A brass band marched slowly past the town hall.",
    "The florist wrapped the roses in crisp white paper.",
    "Dark waves pounded the rocks below the cliff path.",
    "The printer fed clean sheets into the humming press.",
    "A silver plane climbed steeply into the morning haze.",
    "The beekeeper lifted the frame with slow calm hands.",
    "Round pumpkins ripened along the crooked garden wall.",
    "The cobbler nailed a new heel to the leather boot.",
    "A late owl called twice from the hollow elm.",
    "The surveyor planted a stake at the field corner.",
    "Sweet smoke curled from the chimney of the cabin.",
    "The diver checked her gauge and rolled off the stern.",
    "A patched canoe rested upside down on the dock.",
    "The organist held the final chord until it faded.",
]

SPEED_BONUS = 1.05


# ----------------------------------------------------------------------
# shared plumbing
# ----------------------------------------------------------------------

def make_backend(device):
    return ks.OvBackend(ks.MODEL_PATH, device, ks.GPU_PRECISION
                        if device == "GPU" else "f32", ks.CACHE_DIR)


def prep(text, voice=ks.DEFAULT_VOICE):
    """Replicate synthesize() for a single chunk, minus trim: returns
    (padded_tokens[1,96] int64, style[1,256] f32, n_real) or None if the
    text does not land in bucket 96."""
    parsed = ks.parse_voice_spec(voice)
    parts, _ = parsed
    ids = ks.phonemes_to_ids(text, "en-us")
    n = len(ids) + 2
    if n > BUCKET_TARGET:
        return None
    style = ks.style_for_parts(parts, len(ids))
    tokens = np.array([[0, *ids, 0]], dtype=np.int64)
    tokens = np.pad(tokens, ((0, 0), (0, BUCKET_TARGET - n)))
    return tokens, style, len(ids)


def raw_infer(be, tokens, style, speed=1.0):
    """Direct padded infer through the backend's compiled request,
    bypassing trim. Returns (n_samples, wall_s, cpu_s)."""
    sp = np.array([speed], dtype=np.float32)
    with be._lock:
        _, req = be._get(BUCKET_TARGET)
        c0 = time.process_time()
        t0 = time.perf_counter()
        result = req.infer({"tokens": tokens, "style": style, "speed": sp})
        wall = time.perf_counter() - t0
        cpu = time.process_time() - c0
    audio = np.asarray(list(result.values())[0]).reshape(-1)
    return audio, int(audio.size), round(wall, 3), round(cpu, 3)


def label(wall):
    if wall <= WARM_WALL_S:
        return "WARM"
    if wall >= COLD_WALL_S:
        return "COLD"
    return "MID"


def row(name, text, n_real, n_samples, wall, cpu, speed=1.0):
    r = {"name": name, "text": text, "n_real": n_real,
         "n_samples": n_samples, "raw_audio_s": round(n_samples / ks.SR, 4),
         "wall_s": wall, "cpu_s": cpu,
         "rtf_raw": round(wall / (n_samples / ks.SR), 2),
         "speed": speed, "label": label(wall)}
    print("  %-14s n_real=%-3d n_samples=%-7d raw=%.3fs wall=%6.2fs "
          "cpu=%6.2fs rtf_raw=%5.2f -> %s"
          % (name, n_real, n_samples, n_samples / ks.SR, wall, cpu,
             r["rtf_raw"], r["label"]), flush=True)
    return r


# ----------------------------------------------------------------------
# pair picking (pure logic -- unit-testable offline)
# ----------------------------------------------------------------------

def pick_pair_and_control(entries, min_control_gap=1500):
    """entries: list of dicts with name/text/n_real/n_samples.
    Returns (picks_dict, collisions, lattice) where picks_dict has
    a/b/control or is None when no exact collision exists."""
    groups = {}
    for e in entries:
        groups.setdefault(e["n_samples"], []).append(e)
    collisions = {k: v for k, v in groups.items() if len(v) >= 2}

    uniq = sorted(groups)
    diffs = [b - a for a, b in zip(uniq, uniq[1:])]
    lattice = 0
    for d in diffs:
        lattice = math.gcd(lattice, d)

    if not collisions:
        near = sorted(zip(diffs, uniq, uniq[1:]))[:5] if diffs else []
        return None, {"near_misses": [
            {"delta": d, "a_samples": a, "b_samples": b} for d, a, b in near
        ]}, lattice

    def pref(grp):
        # prefer pairs whose members differ in real token count: the
        # strongest form of the claim (different text AND different real
        # length, same internal shape)
        best = None
        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                dn = abs(grp[i]["n_real"] - grp[j]["n_real"])
                cand = (dn, grp[i], grp[j])
                if best is None or cand[0] > best[0]:
                    best = cand
        return best

    key = max(collisions, key=lambda k: pref(collisions[k])[0])
    _, a, b = pref(collisions[key])

    control = None
    for e in entries:
        gap = abs(e["n_samples"] - key)
        if gap >= min_control_gap:
            if control is None or gap < abs(control["n_samples"] - key):
                control = e  # closest shape that is still clearly distinct
    picks = {"a": a, "b": b, "control": control,
             "shared_n_samples": key,
             "n_collision_groups": len(collisions)}
    return picks, collisions, lattice


# ----------------------------------------------------------------------
# phases
# ----------------------------------------------------------------------

def phase1(args):
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    be = make_backend(args.device)
    print("[v118] phase 1: screening %d candidates on %s "
          "(each first infer is a fresh cold sample)"
          % (len(POOL), be.name), flush=True)
    if "patched" not in ks.MODEL_PATH:
        print("[v118] WARNING: KOKORO_MODEL=%r does not look like the "
              "patched model" % ks.MODEL_PATH, flush=True)

    entries, skipped = [], []
    for i, text in enumerate(POOL):
        name = "c%02d" % i
        p = prep(text)
        if p is None:
            skipped.append({"name": name, "text": text,
                            "reason": "exceeds bucket 96"})
            print("  %-14s SKIP (over bucket 96)" % name, flush=True)
            continue
        tokens, style, n_real = p
        audio, n_samples, wall, cpu = raw_infer(be, tokens, style)
        e = row(name, text, n_real, n_samples, wall, cpu)
        entries.append(e)
        if args.save_wavs:
            (outdir / (name + ".wav")).write_bytes(ks.to_wav_bytes(audio))

    # warm-survival: first and last candidates again after the gauntlet
    revisits = []
    for tag, e in (("revisit_first", entries[0]), ("revisit_last",
                                                   entries[-1])):
        tokens, style, n_real = prep(e["text"])
        _, n_samples, wall, cpu = raw_infer(be, tokens, style)
        assert n_samples == e["n_samples"], \
            "non-deterministic sample count on %s" % e["name"]
        revisits.append(row(tag + ":" + e["name"], e["text"], n_real,
                            n_samples, wall, cpu))

    picks, collisions, lattice = pick_pair_and_control(entries)
    matrix = {"device": be.name, "model": ks.MODEL_PATH,
              "bucket": BUCKET_TARGET, "entries": entries,
              "skipped": skipped, "revisits": revisits,
              "lattice_gcd_samples": lattice}
    (outdir / "phase1_matrix.json").write_text(json.dumps(matrix, indent=2))

    print("\n[v118] lattice gcd of unique sample counts: %d samples"
          % lattice, flush=True)
    if picks is None:
        print("[v118] NO exact collision in the pool. Nearest misses:")
        for m in collisions["near_misses"]:
            print("  delta=%d  (%d vs %d)"
                  % (m["delta"], m["a_samples"], m["b_samples"]))
        print("[v118] extend POOL and re-run phase 1; do not run phase 2.")
        (outdir / "phase1_picks.json").write_text(json.dumps(
            {"picks": None, "near": collisions}, indent=2))
        return

    print("[v118] %d collision group(s); picked:" %
          picks["n_collision_groups"])
    for k in ("a", "b", "control"):
        e = picks[k]
        print("  %s: %-5s n_real=%-3d n_samples=%-7d %r"
              % (k.upper(), e["name"], e["n_real"], e["n_samples"],
                 e["text"]))
    (outdir / "phase1_picks.json").write_text(json.dumps(picks, indent=2))
    print("[v118] wrote phase1_matrix.json + phase1_picks.json")
    print("[v118] now run: python scripts/probe_v118_shape_key.py --phase 2")
    print("[v118] (phase 2 MUST be a fresh process -- do not re-use this "
          "one; the in-memory kernel cache is the thing under test)")


def phase2(args):
    outdir = Path(args.outdir)
    picks = json.loads((outdir / "phase1_picks.json").read_text())
    if not picks or picks.get("a") is None:
        sys.exit("[v118] phase1_picks.json has no pair; re-run phase 1")
    A, B, C = picks["a"], picks["b"], picks["control"]
    be = make_backend("GPU")
    print("[v118] phase 2 on %s: A=%s B=%s (shared n_samples=%d) "
          "control C=%s (n_samples=%d)"
          % (be.name, A["name"], B["name"], picks["shared_n_samples"],
             C["name"], C["n_samples"]), flush=True)

    seq = [("A1", A, 1.0), ("A2", A, 1.0), ("A3", A, 1.0),
           ("B1_TEST", B, 1.0), ("B2", B, 1.0),
           ("C1_control", C, 1.0), ("A_speed", A, SPEED_BONUS)]
    results = []
    for tag, e, speed in seq:
        tokens, style, n_real = prep(e["text"])
        _, n_samples, wall, cpu = raw_infer(be, tokens, style, speed)
        r = row(tag + ":" + e["name"], e["text"], n_real, n_samples,
                wall, cpu, speed)
        results.append(r)
        if speed == 1.0 and n_samples != e["n_samples"]:
            print("  !! n_samples drifted vs phase 1 (%d != %d) -- "
                  "determinism assumption broken, verdict void"
                  % (n_samples, e["n_samples"]), flush=True)
            r["drift"] = True

    (outdir / "phase2_result.json").write_text(json.dumps(
        {"picks": picks, "sequence": results}, indent=2))

    by = {r["name"].split(":")[0]: r for r in results}
    b1, c1, a3, asp = by["B1_TEST"], by["C1_control"], by["A3"], by["A_speed"]
    print("\n--- VERDICT ---")
    if any(r.get("drift") for r in results):
        print("VOID: sample counts drifted across processes; investigate "
              "determinism before interpreting.")
        return
    if c1["label"] != "COLD":
        print("CONTROL FAILED: C first-ever ran %s -- the process cannot "
              "be shown cold, B's result is uninterpretable." % c1["label"])
        return
    if b1["label"] == "WARM":
        print("SHAPE-KEYED CONFIRMED: first-ever B ran WARM (wall=%.2fs vs "
              "A3=%.2fs) while control C ran COLD. Warm state is keyed on "
              "internal output shape, not content." % (b1["wall_s"],
                                                       a3["wall_s"]))
    elif b1["label"] == "COLD":
        print("CONTENT-KEYED (deeper than total frames): B first-ever ran "
              "COLD despite exact shape match with warmed A. Keying "
              "involves more than the output frame count.")
    else:
        print("MID: B1 wall=%.2fs -- partial transfer? Compare against A2 "
              "(%.2fs); may indicate async background compilation. Needs "
              "a repeat run." % (b1["wall_s"], by["A2"]["wall_s"]))
    print("A@speed=%.2f ran %s (expected COLD if key is frames-not-text)."
          % (SPEED_BONUS, asp["label"]))
    print("CPU-excess check: cold-vs-warm wall delta %.1fs, cpu delta "
          "%.1fs (similar deltas => the cold cost is host-side JIT)."
          % (c1["wall_s"] - a3["wall_s"], c1["cpu_s"] - a3["cpu_s"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, required=True, choices=(1, 2))
    ap.add_argument("--device", default="GPU", choices=("GPU", "CPU"))
    ap.add_argument("--outdir",
                    default="/data/intel-igpu-tts/artifacts/v118")
    ap.add_argument("--save-wavs", action="store_true")
    args = ap.parse_args()
    (phase1 if args.phase == 1 else phase2)(args)


if __name__ == "__main__":
    main()