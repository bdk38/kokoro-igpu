#!/usr/bin/env python3
"""
Padding-statistics sub-experiment (Fable/note_18 §3.4).

Compare decoder(unpadded T) vs decoder(zero-padded T_bucket) on the real
region only. Pure PyTorch CPU. Spike-only.

Branch P1: real-region maxdiff small, corr >= 0.999 → export OK to proceed
Branch P2: corr < 0.99 or gross level shift → try edge-replication padding
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import torch
import torch.nn.functional as F

# Reuse G0/G1 helpers (same package dir)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_ladder import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_OUT,
    DEFAULT_VOICE,
    DEFAULT_WEIGHTS,
    PHONEMES,
    SAMPLE_RATE,
    SEED,
    SPEED,
    TEXT,
    VOICE_NAME,
    construct_seam_inputs,
    g0_strict_load_decoder,
    load_ref_s,
    load_reference_kmodel,
    phonemes_to_input_ids,
    save_wav,
    set_determinism,
)

T_BUCKET = 96
SAMPLES_PER_FRAME = 600  # v1.0 lattice: 600 samples/frame


def g0_allowlist_check(missing_keys: list, unexpected_keys: list) -> Dict[str, Any]:
    """note_18 §2 automated allowlist."""
    outside = []
    for k in missing_keys:
        is_adain_norm = k.endswith(".norm.weight") or k.endswith(".norm.bias")
        # AdaIN path: *.norm1.norm.weight / encode.norm1.norm.weight etc.
        is_adain_norm = is_adain_norm and ".norm." in k
        is_stft = k.startswith("generator.stft.")
        if not (is_adain_norm or is_stft):
            outside.append(k)
    report = {
        "missing_keys": list(missing_keys),
        "unexpected_keys": list(unexpected_keys),
        "missing_outside_allowlist": outside,
        "n_missing_outside_allowlist": len(outside),
        "n_unexpected": len(unexpected_keys),
        "g0_pass_amended": len(outside) == 0 and len(unexpected_keys) == 0,
    }
    print(
        f"G0 allowlist: missing outside allowlist = {len(outside)}, "
        f"unexpected = {len(unexpected_keys)}"
    )
    if outside:
        print(f"  outside={outside}")
    return report


def pad_seam(
    seam: Dict[str, torch.Tensor],
    t_bucket: int,
    mode: str,
) -> Dict[str, torch.Tensor]:
    """
    Pad asr [1,C,T], F0/N [1,2T] to bucket. style unchanged.
    mode: 'zero' | 'edge'
    """
    asr = seam["asr"]
    f0 = seam["F0_pred"]
    n = seam["N_pred"]
    style = seam["style"]
    t = asr.shape[-1]
    assert f0.shape[-1] == 2 * t and n.shape[-1] == 2 * t, (f0.shape, n.shape, t)
    if t > t_bucket:
        raise ValueError(f"T={t} > t_bucket={t_bucket}")
    pad_t = t_bucket - t
    pad_f0 = 2 * t_bucket - f0.shape[-1]

    if pad_t == 0:
        return {k: v.clone() for k, v in seam.items()}

    if mode == "zero":
        asr_p = F.pad(asr, (0, pad_t), mode="constant", value=0.0)
        f0_p = F.pad(f0, (0, pad_f0), mode="constant", value=0.0)
        n_p = F.pad(n, (0, pad_f0), mode="constant", value=0.0)
    elif mode == "edge":
        # replicate last frame along time
        asr_p = F.pad(asr, (0, pad_t), mode="replicate")
        f0_p = F.pad(f0, (0, pad_f0), mode="replicate")
        n_p = F.pad(n, (0, pad_f0), mode="replicate")
    else:
        raise ValueError(mode)

    assert asr_p.shape[-1] == t_bucket
    assert f0_p.shape[-1] == 2 * t_bucket
    return {"asr": asr_p, "F0_pred": f0_p, "N_pred": n_p, "style": style.clone()}


def wave_metrics(a: torch.Tensor, b: torch.Tensor) -> Dict[str, float]:
    a = a.detach().float().reshape(-1).cpu()
    b = b.detach().float().reshape(-1).cpu()
    n = min(a.numel(), b.numel())
    a, b = a[:n], b[:n]
    diff = (a - b).abs()
    maxdiff = float(diff.max()) if n else float("nan")
    mean_abs = float(diff.mean()) if n else float("nan")
    # level
    rms_a = float(torch.sqrt((a * a).mean()).clamp_min(1e-12))
    rms_b = float(torch.sqrt((b * b).mean()).clamp_min(1e-12))
    # correlation (aligned, same length)
    a0 = a - a.mean()
    b0 = b - b.mean()
    denom = float(torch.sqrt((a0 * a0).sum() * (b0 * b0).sum()).clamp_min(1e-12))
    corr = float((a0 * b0).sum() / denom) if n else float("nan")
    return {
        "n_samples": int(n),
        "maxdiff": maxdiff,
        "mean_abs_diff": mean_abs,
        "corr": corr,
        "rms_a": rms_a,
        "rms_b": rms_b,
        "rms_ratio_b_over_a": rms_b / rms_a,
    }


def run_decoder(
    decoder: torch.nn.Module,
    seam: Dict[str, torch.Tensor],
    seed: int,
) -> torch.Tensor:
    set_determinism(seed)
    with torch.no_grad():
        audio = decoder(seam["asr"], seam["F0_pred"], seam["N_pred"], seam["style"])
    return audio.squeeze().detach().cpu().float()


def classify(metrics: Dict[str, float]) -> str:
    """note_18 §3.4 branches."""
    corr = metrics["corr"]
    # P2: audible-scale
    if corr < 0.99 or abs(metrics["rms_ratio_b_over_a"] - 1.0) > 0.1:
        return "P2"
    # P1: small but may be nonzero; corr >= 0.999
    if corr >= 0.999:
        return "P1"
    # Between 0.99 and 0.999 — still proceed-with-caution P1-ish; call P1_weak
    return "P1_weak"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=DEFAULT_CONFIG)
    p.add_argument("--weights", default=DEFAULT_WEIGHTS)
    p.add_argument("--voice", default=DEFAULT_VOICE)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT / "pad_stats")
    p.add_argument("--t-bucket", type=int, default=T_BUCKET)
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    print("## G0 load + allowlist (note_18 §2)")
    decoder, missing, unexpected, g0_raw = g0_strict_load_decoder(
        config, args.weights, disable_complex=True
    )
    g0 = g0_allowlist_check(missing, unexpected)
    g0["raw_strict_clean"] = g0_raw.get("strict_clean")
    if not g0["g0_pass_amended"]:
        print("HARD STOP: G0 allowlist failed")
        (args.out / "pad_stats_result.json").write_text(json.dumps({"g0": g0}, indent=2))
        return 2

    print("## Reference frontend → seam @ native T")
    set_determinism(args.seed)
    ref_model = load_reference_kmodel(args.config, args.weights, disable_complex=True)
    input_ids = phonemes_to_input_ids(ref_model, PHONEMES)
    ref_s = load_ref_s(args.voice, PHONEMES)
    seam = construct_seam_inputs(ref_model, input_ids, ref_s, speed=SPEED)
    # move to cpu float
    seam = {k: v.detach().cpu().float() for k, v in seam.items()}
    t_nat = int(seam["asr"].shape[-1])
    n_real = t_nat * SAMPLES_PER_FRAME
    print(f"native T={t_nat}  real_audio_samples={n_real}  t_bucket={args.t_bucket}")
    print(
        f"shapes asr={tuple(seam['asr'].shape)} F0={tuple(seam['F0_pred'].shape)} "
        f"N={tuple(seam['N_pred'].shape)} style={tuple(seam['style'].shape)}"
    )

    # Unpadded decode
    audio_nat = run_decoder(decoder, seam, args.seed)
    assert audio_nat.numel() == n_real, (audio_nat.numel(), n_real)

    results: Dict[str, Any] = {
        "g0": g0,
        "constants": {
            "seed": args.seed,
            "text": TEXT,
            "phonemes": PHONEMES,
            "voice": VOICE_NAME,
            "t_native": t_nat,
            "t_bucket": args.t_bucket,
            "samples_per_frame": SAMPLES_PER_FRAME,
            "n_real_samples": n_real,
        },
        "modes": {},
    }

    for mode in ("zero", "edge"):
        print(f"\n## mode={mode} pad to T={args.t_bucket}")
        seam_p = pad_seam(seam, args.t_bucket, mode=mode)
        audio_p = run_decoder(decoder, seam_p, args.seed)
        expect_full = args.t_bucket * SAMPLES_PER_FRAME
        assert audio_p.numel() == expect_full, (audio_p.numel(), expect_full)
        # real region = leading n_real samples (pad is trailing time)
        audio_p_real = audio_p[:n_real]
        m = wave_metrics(audio_nat, audio_p_real)
        branch = classify(m)
        print(
            f"  real-region maxdiff={m['maxdiff']:.6g} mean_abs={m['mean_abs_diff']:.6g} "
            f"corr={m['corr']:.8f} rms_ratio={m['rms_ratio_b_over_a']:.6f} → {branch}"
        )
        results["modes"][mode] = {"metrics": m, "branch": branch}

        save_wav(args.out / f"unpadded_T{t_nat}.wav", audio_nat, SAMPLE_RATE)
        save_wav(args.out / f"padded_{mode}_T{args.t_bucket}_full.wav", audio_p, SAMPLE_RATE)
        save_wav(
            args.out / f"padded_{mode}_T{args.t_bucket}_realregion.wav",
            audio_p_real,
            SAMPLE_RATE,
        )

    # Primary decision uses zero-pad (export default)
    primary = results["modes"]["zero"]["branch"]
    edge_b = results["modes"]["edge"]["branch"]
    if primary in ("P1", "P1_weak"):
        verdict = primary
        action = "proceed_to_g2_export"
    elif edge_b in ("P1", "P1_weak"):
        verdict = "P2_then_edge_" + edge_b
        action = "use_edge_replication_padding_for_export"
    else:
        verdict = "P2"
        action = "redesign_bucket_before_ov"

    results["primary_branch_zero_pad"] = primary
    results["edge_branch"] = edge_b
    results["verdict"] = verdict
    results["recommended_action"] = action

    out_json = args.out / "pad_stats_result.json"
    out_json.write_text(json.dumps(results, indent=2))
    print(f"\n**Verdict:** {verdict}")
    print(f"**Action:** {action}")
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
