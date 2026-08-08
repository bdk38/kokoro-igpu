#!/usr/bin/env python3
"""
G0 strict-load + G1 forward-hooks ladder for Kokoro seam B.

Spike-only instrument (Fable/note_17). No ONNX / OpenVINO.

Seam B (model.py):
  audio = decoder(asr, F0_pred, N_pred, ref_s[:, :128])
  predictor style uses ref_s[:, 128:]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

# ---------------------------------------------------------------------------
# Fixed parity-instrument constants
# ---------------------------------------------------------------------------
SEED = 0
TEXT = "Hello from the spike ladder."
# Resolved once via KPipeline(lang_code='a', model=False) for TEXT; keep deterministic.
PHONEMES = "həlˈO fɹʌm ðə spˈIk lˈædəɹ."
VOICE_NAME = "af_bella"
SPEED = 1.0
SAMPLE_RATE = 24000
G1_WAVE_MAXDIFF_PASS = 1e-4

DEFAULT_CONFIG = "/data/kokoro-openvino/huggingface/Kokoro-82M/config.json"
DEFAULT_WEIGHTS = "/data/kokoro-openvino/huggingface/Kokoro-82M/kokoro-v1_0.pth"
DEFAULT_VOICE = "/data/kokoro-openvino/huggingface/Kokoro-82M/voices/af_bella.pt"
DEFAULT_OUT = Path(__file__).resolve().parent / "out"


def set_determinism(seed: int = SEED) -> None:
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def strip_module_prefix(state_dict: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    out = {}
    for k, v in state_dict.items():
        if k.startswith("module."):
            out[k[len("module.") :]] = v
        else:
            out[k] = v
    return out


def build_standalone_decoder(config: dict, disable_complex: bool = True) -> torch.nn.Module:
    from kokoro.istftnet import Decoder

    return Decoder(
        dim_in=config["hidden_dim"],
        style_dim=config["style_dim"],
        dim_out=config["n_mels"],
        disable_complex=disable_complex,
        **config["istftnet"],
    )


def g0_strict_load_decoder(
    config: dict,
    weights_path: str,
    disable_complex: bool = True,
) -> Tuple[torch.nn.Module, List[str], List[str], dict]:
    """
    G0: build a fresh Decoder, load ckpt['decoder'] after stripping module.,
    report missing/unexpected as the strict=True gate evidence.

    torch.load_state_dict(strict=True) raises and does not return lists on
    mismatch, so we load with strict=False to obtain IncompatibleKeys (and
    populate weights for the ladder), then treat non-empty lists as G0 fail.
    """
    ckpt = torch.load(weights_path, map_location="cpu", weights_only=True)
    if not isinstance(ckpt, dict) or "decoder" not in ckpt:
        raise RuntimeError(
            f"Checkpoint is not a submodule state_dict dict with 'decoder' key; "
            f"top keys={list(ckpt.keys()) if isinstance(ckpt, dict) else type(ckpt)}"
        )

    decoder = build_standalone_decoder(config, disable_complex=disable_complex)
    decoder.eval()
    prepared = strip_module_prefix(ckpt["decoder"])

    # Prefer the strict=True API when clean; always capture full lists.
    try:
        incompat = decoder.load_state_dict(prepared, strict=True)
        missing_keys = list(incompat.missing_keys)
        unexpected_keys = list(incompat.unexpected_keys)
    except RuntimeError:
        incompat = decoder.load_state_dict(prepared, strict=False)
        missing_keys = list(incompat.missing_keys)
        unexpected_keys = list(incompat.unexpected_keys)

    print(f"missing_keys={missing_keys} unexpected_keys={unexpected_keys}")

    report = {
        "missing_keys": missing_keys,
        "unexpected_keys": unexpected_keys,
        "n_missing": len(missing_keys),
        "n_unexpected": len(unexpected_keys),
        "strict_clean": len(missing_keys) == 0 and len(unexpected_keys) == 0,
        "n_ckpt_decoder_keys": len(prepared),
    }
    return decoder, missing_keys, unexpected_keys, report


def load_reference_kmodel(
    config_path: str,
    weights_path: str,
    disable_complex: bool = True,
) -> torch.nn.Module:
    from kokoro import KModel

    model = KModel(
        repo_id="hexgrad/Kokoro-82M",
        config=config_path,
        model=weights_path,
        disable_complex=disable_complex,
    )
    model.eval()
    return model


def phonemes_to_input_ids(model: torch.nn.Module, phonemes: str) -> torch.LongTensor:
    input_ids = list(
        filter(lambda i: i is not None, map(lambda p: model.vocab.get(p), phonemes))
    )
    assert len(input_ids) + 2 <= model.context_length, (
        len(input_ids) + 2,
        model.context_length,
    )
    return torch.LongTensor([[0, *input_ids, 0]])


def load_ref_s(voice_path: str, phonemes: str) -> torch.FloatTensor:
    """Voice pack is (510, 1, 256); KPipeline.infer uses pack[len(ps)-1] → (1, 256)."""
    pack = torch.load(voice_path, map_location="cpu", weights_only=True)
    if not isinstance(pack, torch.Tensor):
        raise TypeError(f"Expected voice tensor, got {type(pack)}")
    idx = len(phonemes) - 1
    ref_s = pack[idx]
    if ref_s.dim() == 1:
        ref_s = ref_s.unsqueeze(0)
    return ref_s.float()


def construct_seam_inputs(
    model: torch.nn.Module,
    input_ids: torch.LongTensor,
    ref_s: torch.FloatTensor,
    speed: float = SPEED,
) -> Dict[str, torch.Tensor]:
    """
    Same frontend math as KModel.forward_with_tokens up through asr/F0/N/style,
    without calling decoder. Source of truth: kokoro/model.py.
    """
    device = model.device
    input_ids = input_ids.to(device)
    ref_s = ref_s.to(device)

    input_lengths = torch.full(
        (input_ids.shape[0],),
        input_ids.shape[-1],
        device=device,
        dtype=torch.long,
    )
    text_mask = torch.arange(input_lengths.max(), device=device).unsqueeze(0).expand(
        input_lengths.shape[0], -1
    ).type_as(input_lengths)
    text_mask = torch.gt(text_mask + 1, input_lengths.unsqueeze(1)).to(device)

    bert_dur = model.bert(input_ids, attention_mask=(~text_mask).int())
    d_en = model.bert_encoder(bert_dur).transpose(-1, -2)
    s = ref_s[:, 128:]
    d = model.predictor.text_encoder(d_en, s, input_lengths, text_mask)
    x, _ = model.predictor.lstm(d)
    duration = model.predictor.duration_proj(x)
    duration = torch.sigmoid(duration).sum(axis=-1) / speed
    pred_dur = torch.round(duration).clamp(min=1).long().squeeze()
    indices = torch.repeat_interleave(
        torch.arange(input_ids.shape[1], device=device), pred_dur
    )
    pred_aln_trg = torch.zeros(
        (input_ids.shape[1], indices.shape[0]), device=device
    )
    pred_aln_trg[indices, torch.arange(indices.shape[0], device=device)] = 1
    pred_aln_trg = pred_aln_trg.unsqueeze(0).to(device)
    en = d.transpose(-1, -2) @ pred_aln_trg
    F0_pred, N_pred = model.predictor.F0Ntrain(en, s)
    t_en = model.text_encoder(input_ids, input_lengths, text_mask)
    asr = t_en @ pred_aln_trg
    style = ref_s[:, :128]
    return {
        "asr": asr,
        "F0_pred": F0_pred,
        "N_pred": N_pred,
        "style": style,
        "pred_dur": pred_dur,
    }


def _to_cpu_tensor(obj: Any) -> Optional[torch.Tensor]:
    if torch.is_tensor(obj):
        return obj.detach().float().cpu().clone()
    if isinstance(obj, (tuple, list)):
        # Prefer first tensor; if multiple, stack only if same shape else first.
        tensors = [x for x in obj if torch.is_tensor(x)]
        if not tensors:
            return None
        if len(tensors) == 1:
            return tensors[0].detach().float().cpu().clone()
        # Pack multiple tensor outputs into one flat vector for comparison.
        flats = [t.detach().float().cpu().reshape(-1) for t in tensors]
        return torch.cat(flats, dim=0).clone()
    return None


class HookStore:
    """Register forward hooks on every named submodule (skip empty name)."""

    def __init__(self, root: torch.nn.Module, prefix: str = ""):
        self.outputs: Dict[str, torch.Tensor] = {}
        self.order: List[str] = []
        self.handles = []
        self.prefix = prefix
        for name, mod in root.named_modules():
            if not name:
                continue
            full = f"{prefix}{name}" if prefix else name
            self.handles.append(mod.register_forward_hook(self._make_hook(full)))

    def _make_hook(self, name: str):
        def hook(_module, _inp, out):
            t = _to_cpu_tensor(out)
            if t is None:
                return
            if name not in self.outputs:
                self.order.append(name)
            self.outputs[name] = t

        return hook

    def remove(self) -> None:
        for h in self.handles:
            h.remove()
        self.handles.clear()


def compare_tensors(
    name: str,
    ref: Optional[torch.Tensor],
    mir: Optional[torch.Tensor],
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "name": name,
        "shape_ref": None,
        "shape_mir": None,
        "maxdiff": None,
        "mean_abs_diff": None,
        "cosine_similarity": None,
        "status": "OK",
    }
    if ref is None and mir is None:
        row["status"] = "SKIP_BOTH_NONE"
        return row
    if ref is None:
        row["shape_mir"] = list(mir.shape) if mir is not None else None
        row["status"] = "FAIL_MISSING_REF"
        return row
    if mir is None:
        row["shape_ref"] = list(ref.shape)
        row["status"] = "FAIL_MISSING_MIR"
        return row

    row["shape_ref"] = list(ref.shape)
    row["shape_mir"] = list(mir.shape)
    if list(ref.shape) != list(mir.shape):
        row["status"] = "FAIL_SHAPE_MISMATCH"
        # Still report a best-effort flat maxdiff on min-length overlap.
        a = ref.reshape(-1).float()
        b = mir.reshape(-1).float()
        n = min(a.numel(), b.numel())
        if n > 0:
            d = (a[:n] - b[:n]).abs()
            row["maxdiff"] = float(d.max().item())
            row["mean_abs_diff"] = float(d.mean().item())
        return row

    a = ref.float().reshape(-1)
    b = mir.float().reshape(-1)
    diff = (a - b).abs()
    row["maxdiff"] = float(diff.max().item()) if a.numel() else 0.0
    row["mean_abs_diff"] = float(diff.mean().item()) if a.numel() else 0.0
    # Cosine in f32; handle zero vectors.
    na = torch.linalg.vector_norm(a)
    nb = torch.linalg.vector_norm(b)
    if na.item() == 0.0 and nb.item() == 0.0:
        row["cosine_similarity"] = 1.0
    elif na.item() == 0.0 or nb.item() == 0.0:
        row["cosine_similarity"] = 0.0
    else:
        row["cosine_similarity"] = float(torch.dot(a, b).div(na * nb).item())
    return row


def branch_verdict(
    g0_missing: List[str],
    g0_unexpected: List[str],
    rungs: List[Dict[str, Any]],
    wave_maxdiff_ref_vs_captured: Optional[float],
) -> str:
    """
    Fable/note_17 branch labels:
      A: G0 non-empty missing/unexpected OR single rung maxdiff jumps ≥3 orders
      B: G0 clean but rung0 (seam inputs) already diverges
      C: G0 clean, rung0 clean, gradual monotonic growth across rungs
      none: otherwise (e.g. clean rungs but final wave diverges)
    """
    g0_dirty = bool(g0_missing) or bool(g0_unexpected)

    # Rung-0 = seam.* rows
    seam_rows = [r for r in rungs if r["name"].startswith("seam.")]
    rung0_div = False
    for r in seam_rows:
        md = r.get("maxdiff")
        if r.get("status") not in (None, "OK") and r.get("status") != "OK":
            if str(r.get("status", "")).startswith("FAIL"):
                rung0_div = True
        if md is not None and md > 1e-5:
            rung0_div = True

    # Discontinuous jump ≥ 3 orders of magnitude between consecutive comparable rungs
    jump = False
    jump_at = None
    comparable = [
        r
        for r in rungs
        if r.get("maxdiff") is not None and r.get("status") == "OK"
    ]
    for i in range(1, len(comparable)):
        prev = comparable[i - 1]["maxdiff"]
        cur = comparable[i]["maxdiff"]
        # 3 orders of magnitude: cur/prev >= 1e3, with guard for near-zero prev
        if prev <= 0.0:
            if cur >= 1e-3:
                jump = True
                jump_at = comparable[i]["name"]
                break
        elif cur / prev >= 1e3 and cur >= 1e-6:
            jump = True
            jump_at = comparable[i]["name"]
            break

    if g0_dirty or jump:
        return "A" + (f" (jump@{jump_at})" if jump_at else "")

    if not g0_dirty and rung0_div:
        return "B"

    # C: gradual monotonic growth across non-seam rungs
    body = [
        r
        for r in rungs
        if not r["name"].startswith("seam.")
        and r.get("maxdiff") is not None
        and r.get("status") == "OK"
    ]
    if not g0_dirty and not rung0_div and body:
        diffs = [r["maxdiff"] for r in body]
        # Monotonic non-decreasing within float noise; and material growth
        mono = all(diffs[i] <= diffs[i + 1] + 1e-12 for i in range(len(diffs) - 1))
        growth = diffs[-1] > max(diffs[0] * 10.0, 1e-6) if diffs[0] is not None else False
        # "Gradual" — no 3-order jump already checked; allow soft monotonic via cumulative max
        soft_mono = True
        running = diffs[0]
        for d in diffs[1:]:
            if d + 1e-12 < running * 0.5 and d < running - 1e-5:
                # large drop — not gradual growth signature
                soft_mono = False
                break
            running = max(running, d)
        if (mono or soft_mono) and growth:
            return "C"

    if (
        wave_maxdiff_ref_vs_captured is not None
        and wave_maxdiff_ref_vs_captured > G1_WAVE_MAXDIFF_PASS
        and not rung0_div
        and not jump
    ):
        return "none (clean-ish rungs but final wave diverges, or no A/B/C match)"

    return "none"


def save_wav(path: Path, audio: torch.Tensor, sr: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    x = audio.detach().float().cpu().reshape(-1).numpy()
    x = np.clip(x, -1.0, 1.0)
    pcm = (x * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def fmt_num(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    if x == 0.0:
        return "0"
    if abs(x) < 1e-3 or abs(x) >= 1e4:
        return f"{x:.6e}"
    return f"{x:.6f}"


def print_table(rungs: List[Dict[str, Any]], waves: Dict[str, float], verdict: str) -> None:
    print()
    print("## G1 hook ladder")
    print()
    hdr = (
        f"{'rung':<42} {'shape_ref':<22} {'shape_mir':<22} "
        f"{'maxdiff':>12} {'mean_abs':>12} {'cosine':>10} {'status':<18}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in rungs:
        sr = str(r.get("shape_ref"))
        sm = str(r.get("shape_mir"))
        if len(sr) > 22:
            sr = sr[:19] + "..."
        if len(sm) > 22:
            sm = sm[:19] + "..."
        print(
            f"{r['name']:<42} {sr:<22} {sm:<22} "
            f"{fmt_num(r.get('maxdiff')):>12} {fmt_num(r.get('mean_abs_diff')):>12} "
            f"{fmt_num(r.get('cosine_similarity')):>10} {str(r.get('status')):<18}"
        )
    print()
    print("## Waveform maxdiffs")
    for k, v in waves.items():
        print(f"  {k}: {fmt_num(v)}")
    print()
    print(f"**Branch verdict:** {verdict}")
    print()


def write_csv(path: Path, rungs: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "name",
        "shape_ref",
        "shape_mir",
        "maxdiff",
        "mean_abs_diff",
        "cosine_similarity",
        "status",
    ]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rungs:
            row = {k: r.get(k) for k in fields}
            row["shape_ref"] = json.dumps(r.get("shape_ref"))
            row["shape_mir"] = json.dumps(r.get("shape_mir"))
            w.writerow(row)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kokoro seam-B G0+G1 hook ladder (spike)")
    p.add_argument("--config", default=DEFAULT_CONFIG)
    p.add_argument("--weights", default=DEFAULT_WEIGHTS)
    p.add_argument("--voice", default=DEFAULT_VOICE)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--text", default=TEXT)
    p.add_argument("--phonemes", default=PHONEMES,
                   help="If set (default: fixed for TEXT), skip G2P")
    p.add_argument("--speed", type=float, default=SPEED)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--no-wav", action="store_true", help="Skip writing wav previews")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    set_determinism(args.seed)
    torch.set_grad_enabled(False)

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    # ------------------------------------------------------------------
    # G0 — strict decoder load (run first)
    # ------------------------------------------------------------------
    print("## G0 — strict decoder load")
    print(f"weights={args.weights}")
    standalone_decoder, missing_keys, unexpected_keys, g0_report = g0_strict_load_decoder(
        config, args.weights, disable_complex=True
    )
    g0_path = out_dir / "g0_strict_load.json"
    with g0_path.open("w", encoding="utf-8") as f:
        json.dump(g0_report, f, indent=2)
    print(f"wrote {g0_path}")
    print(f"G0 strict_clean={g0_report['strict_clean']}")

    # Full reference KModel via normal kokoro API (local paths, no HF download)
    print("\n## Load reference KModel")
    ref_model = load_reference_kmodel(args.config, args.weights, disable_complex=True)
    # Keep on CPU, f32, eval
    ref_model = ref_model.to("cpu").float().eval()
    standalone_decoder = standalone_decoder.to("cpu").float().eval()

    phonemes = args.phonemes
    if args.text != TEXT and phonemes == PHONEMES:
        # User changed text but left default phonemes — re-resolve once.
        from kokoro import KPipeline

        pipe = KPipeline(lang_code="a", model=False, repo_id="hexgrad/Kokoro-82M")
        phonemes = None
        for r in pipe(args.text):
            phonemes = r.phonemes
            break
        if not phonemes:
            raise RuntimeError(f"G2P produced no phonemes for text={args.text!r}")
        print(f"resolved phonemes for custom text: {phonemes!r}")
    else:
        print(f"phonemes (fixed): {phonemes!r}")
        print(f"text (fixed): {args.text!r}")

    input_ids = phonemes_to_input_ids(ref_model, phonemes)
    ref_s = load_ref_s(args.voice, phonemes)
    print(f"input_ids shape={tuple(input_ids.shape)} ref_s shape={tuple(ref_s.shape)}")

    # ------------------------------------------------------------------
    # G1a — reference forward with hooks
    # ------------------------------------------------------------------
    print("\n## G1 — reference forward + hooks")
    captured_inputs: Dict[str, torch.Tensor] = {}

    def _capture_decoder_inputs(_module, args_in, kwargs_in):
        # decoder.forward(asr, F0_curve, N, s)
        if args_in and len(args_in) >= 4:
            asr, f0, n, s = args_in[0], args_in[1], args_in[2], args_in[3]
        else:
            asr = kwargs_in.get("asr")
            f0 = kwargs_in.get("F0_curve", kwargs_in.get("F0_pred"))
            n = kwargs_in.get("N")
            s = kwargs_in.get("s", kwargs_in.get("style"))
        captured_inputs["asr"] = asr.detach().float().cpu().clone()
        captured_inputs["F0_pred"] = f0.detach().float().cpu().clone()
        captured_inputs["N_pred"] = n.detach().float().cpu().clone()
        captured_inputs["style"] = s.detach().float().cpu().clone()

    pre_handle = ref_model.decoder.register_forward_pre_hook(
        _capture_decoder_inputs, with_kwargs=True
    )
    ref_hooks = HookStore(ref_model.decoder)

    set_determinism(args.seed)
    with torch.no_grad():
        audio_ref, pred_dur = ref_model.forward_with_tokens(
            input_ids.to(ref_model.device),
            ref_s.to(ref_model.device),
            args.speed,
        )
    audio_ref = audio_ref.detach().float().cpu().reshape(-1)
    pre_handle.remove()
    ref_hooks.remove()
    print(
        f"ref audio samples={audio_ref.numel()} pred_dur sum="
        f"{int(pred_dur.sum().item()) if pred_dur.dim() else int(pred_dur.item())}"
    )
    print(
        f"captured decoder inputs: "
        + ", ".join(f"{k}{tuple(v.shape)}" for k, v in captured_inputs.items())
    )
    print(f"ref decoder hook rungs captured: {len(ref_hooks.outputs)}")

    # ------------------------------------------------------------------
    # G1b — constructed seam inputs (Branch B check)
    # ------------------------------------------------------------------
    print("\n## G1 — constructed seam inputs")
    set_determinism(args.seed)
    with torch.no_grad():
        constructed = construct_seam_inputs(
            ref_model, input_ids, ref_s, speed=args.speed
        )
    # Move constructed to cpu for comparison
    constructed_cpu = {
        k: v.detach().float().cpu() if torch.is_tensor(v) else v
        for k, v in constructed.items()
    }

    rungs: List[Dict[str, Any]] = []
    for key in ("asr", "F0_pred", "N_pred", "style"):
        rungs.append(
            compare_tensors(
                f"seam.{key}",
                captured_inputs.get(key),
                constructed_cpu.get(key),
            )
        )

    # ------------------------------------------------------------------
    # G1c — mirror decoder on CAPTURED seam inputs + hooks
    # ------------------------------------------------------------------
    print("\n## G1 — standalone decoder on captured seam inputs")
    mir_hooks = HookStore(standalone_decoder)
    set_determinism(args.seed)
    with torch.no_grad():
        audio_mir_cap = standalone_decoder(
            captured_inputs["asr"],
            captured_inputs["F0_pred"],
            captured_inputs["N_pred"],
            captured_inputs["style"],
        )
    audio_mir_cap = audio_mir_cap.detach().float().cpu().reshape(-1)
    mir_hooks.remove()
    print(f"standalone (captured) audio samples={audio_mir_cap.numel()}")
    print(f"standalone hook rungs captured: {len(mir_hooks.outputs)}")

    # Match by module name (same named_modules suffix under decoder)
    # Prefer reference discovery order; include mir-only at end.
    names_ref = list(ref_hooks.order)
    names_mir_only = [n for n in mir_hooks.order if n not in ref_hooks.outputs]
    for name in names_ref + names_mir_only:
        # Normalize: if somehow prefixed, match by suffix
        ref_t = ref_hooks.outputs.get(name)
        mir_t = mir_hooks.outputs.get(name)
        if mir_t is None:
            # try suffix match
            for mk, mv in mir_hooks.outputs.items():
                if mk == name or mk.endswith(name) or name.endswith(mk):
                    mir_t = mv
                    break
        if ref_t is None:
            for rk, rv in ref_hooks.outputs.items():
                if rk == name or rk.endswith(name) or name.endswith(rk):
                    ref_t = rv
                    break
        rungs.append(compare_tensors(name, ref_t, mir_t))

    # ------------------------------------------------------------------
    # G1d — waveforms: ref vs standalone(captured) vs standalone(constructed)
    # ------------------------------------------------------------------
    print("\n## G1 — standalone decoder on constructed seam inputs")
    set_determinism(args.seed)
    with torch.no_grad():
        audio_mir_con = standalone_decoder(
            constructed_cpu["asr"],
            constructed_cpu["F0_pred"],
            constructed_cpu["N_pred"],
            constructed_cpu["style"],
        )
    audio_mir_con = audio_mir_con.detach().float().cpu().reshape(-1)

    def wave_maxdiff(a: torch.Tensor, b: torch.Tensor) -> float:
        if a.shape != b.shape:
            n = min(a.numel(), b.numel())
            if n == 0:
                return float("inf")
            return float((a.reshape(-1)[:n] - b.reshape(-1)[:n]).abs().max().item())
        return float((a - b).abs().max().item())

    waves = {
        "ref_vs_standalone_captured": wave_maxdiff(audio_ref, audio_mir_cap),
        "ref_vs_standalone_constructed": wave_maxdiff(audio_ref, audio_mir_con),
        "standalone_captured_vs_constructed": wave_maxdiff(audio_mir_cap, audio_mir_con),
    }
    g1_pass = waves["ref_vs_standalone_captured"] <= G1_WAVE_MAXDIFF_PASS

    verdict = branch_verdict(missing_keys, unexpected_keys, rungs, waves["ref_vs_standalone_captured"])
    print_table(rungs, waves, verdict)
    print(f"**G1 pass** (ref vs strict decoder on captured ≤ {G1_WAVE_MAXDIFF_PASS}): {g1_pass}")
    print(f"  maxdiff={fmt_num(waves['ref_vs_standalone_captured'])}")

    # Optional small wavs
    if not args.no_wav:
        save_wav(out_dir / "ref.wav", audio_ref)
        save_wav(out_dir / "standalone_captured.wav", audio_mir_cap)
        save_wav(out_dir / "standalone_constructed.wav", audio_mir_con)
        print(f"wrote wavs under {out_dir}")

    write_csv(out_dir / "ladder_table.csv", rungs)

    result = {
        "g0": g0_report,
        "constants": {
            "seed": args.seed,
            "text": args.text,
            "phonemes": phonemes,
            "voice": VOICE_NAME,
            "voice_path": args.voice,
            "speed": args.speed,
            "device": "cpu",
            "dtype": "f32",
            "disable_complex": True,
        },
        "rungs": rungs,
        "waveform_maxdiffs": waves,
        "branch_verdict": verdict,
        "g1_pass": g1_pass,
        "g1_threshold": G1_WAVE_MAXDIFF_PASS,
        "n_ref_hooks": len(ref_hooks.outputs),
        "n_mir_hooks": len(mir_hooks.outputs),
        "audio_samples_ref": int(audio_ref.numel()),
        "audio_samples_mir_captured": int(audio_mir_cap.numel()),
        "audio_samples_mir_constructed": int(audio_mir_con.numel()),
    }
    result_path = out_dir / "ladder_result.json"
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out_dir / 'ladder_table.csv'}")
    print(f"wrote {result_path}")
    return 0 if g0_report is not None else 1


if __name__ == "__main__":
    sys.exit(main())
