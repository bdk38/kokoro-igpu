#!/usr/bin/env python3
"""
G2 — decoder-only ONNX export @ fixed T=96 (Fable/note_18–19).

- spike/ only; ship freeze held
- G0 allowlist check on load (note_18 §2)
- Noise hoisted: sine_noise, uv_noise, phase_rand (3 stochastic sites)
- disable_complex=True; edge-replication pad; static shapes
- ORT-CPU export parity vs PyTorch with identical noise
- Ear set: ≥3 real-text utterances → WAVs for Nexus
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

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
    construct_seam_inputs,
    g0_strict_load_decoder,
    load_ref_s,
    load_reference_kmodel,
    phonemes_to_input_ids,
    set_determinism,
)
from pad_stats import g0_allowlist_check, pad_seam  # noqa: E402

T_BUCKET = 96
SAMPLES_PER_FRAME = 600  # audio = F0_len * 300 = 2T * 300 = 600T
HARMONIC_DIM = 9  # harmonic_num 8 + 1
AUDIO_LEN = T_BUCKET * SAMPLES_PER_FRAME  # 57600
F0_LEN = 2 * T_BUCKET  # 192

OPSET = 17

EAR_TEXTS = [
    "Hello from the spike ladder.",
    "Seven silver swans swam south.",
    "Remember the keys and wallet.",
]


# ---------------------------------------------------------------------------
# Exportable decoder: graph-level noise inputs
# ---------------------------------------------------------------------------


class DecoderExport(nn.Module):
    """
    Wraps a loaded Decoder. forward() takes seam tensors + hoisted noise.

    Stochastic sites (note_18/19):
      1. SineGen phase init: torch.rand → phase_rand [B, dim]
      2. SineGen harmonic noise: randn_like(sine_waves) → sine_noise [B, L, dim]
      3. SourceModule noise branch: randn_like(uv) → uv_noise [B, L, 1]
    """

    def __init__(self, decoder: nn.Module):
        super().__init__()
        self.decoder = decoder
        sg = decoder.generator.m_source.l_sin_gen
        self.sine_amp = float(sg.sine_amp)
        self.noise_std = float(sg.noise_std)
        self.harmonic_num = int(sg.harmonic_num)
        self.dim = int(sg.dim)
        self.sampling_rate = float(sg.sampling_rate)
        self.voiced_threshold = float(sg.voiced_threshold)
        self.upsample_scale = float(sg.upsample_scale)
        self.flag_for_pulse = bool(sg.flag_for_pulse)

    def _f02uv(self, f0: torch.Tensor) -> torch.Tensor:
        return (f0 > self.voiced_threshold).to(dtype=torch.float32)

    def _f02sine(self, f0_values: torch.Tensor, phase_rand: torch.Tensor) -> torch.Tensor:
        """SineGen._f02sine with hoisted phase_rand [B, dim] instead of torch.rand."""
        rad_values = (f0_values / self.sampling_rate) % 1
        # phase_rand: [B, dim]; fundamental dim0 = 0; applied at first time step only
        rand_ini = phase_rand.clone()
        rand_ini = torch.cat(
            [torch.zeros_like(rand_ini[:, :1]), rand_ini[:, 1:]], dim=1
        )
        rad_values = rad_values.clone()
        rad_values[:, 0, :] = rad_values[:, 0, :] + rand_ini
        if self.flag_for_pulse:
            raise RuntimeError("flag_for_pulse path not used by Kokoro export")
        rad_values = F.interpolate(
            rad_values.transpose(1, 2),
            scale_factor=1.0 / self.upsample_scale,
            mode="linear",
        ).transpose(1, 2)
        phase = torch.cumsum(rad_values, dim=1) * (2 * math.pi)
        phase = F.interpolate(
            phase.transpose(1, 2) * self.upsample_scale,
            scale_factor=float(self.upsample_scale),
            mode="linear",
        ).transpose(1, 2)
        return torch.sin(phase)

    def _sine_gen_forward(
        self,
        f0: torch.Tensor,
        sine_noise: torch.Tensor,
        phase_rand: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """SineGen.forward with hoisted sine_noise + phase_rand."""
        # f0: [B, L, 1]
        fn = f0 * torch.arange(
            1, self.harmonic_num + 2, device=f0.device, dtype=f0.dtype
        ).view(1, 1, -1)
        sine_waves = self._f02sine(fn, phase_rand) * self.sine_amp
        uv = self._f02uv(f0)
        noise_amp = uv * self.noise_std + (1 - uv) * self.sine_amp / 3
        noise = noise_amp * sine_noise
        sine_waves = sine_waves * uv + noise
        return sine_waves, uv, noise

    def _source_forward(
        self,
        f0: torch.Tensor,
        sine_noise: torch.Tensor,
        uv_noise: torch.Tensor,
        phase_rand: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        src = self.decoder.generator.m_source
        sine_wavs, uv, _ = self._sine_gen_forward(f0, sine_noise, phase_rand)
        sine_merge = src.l_tanh(src.l_linear(sine_wavs))
        noise = uv_noise * (self.sine_amp / 3)
        return sine_merge, noise, uv

    def _generator_forward(
        self,
        x: torch.Tensor,
        s: torch.Tensor,
        f0_curve: torch.Tensor,
        sine_noise: torch.Tensor,
        uv_noise: torch.Tensor,
        phase_rand: torch.Tensor,
    ) -> torch.Tensor:
        g = self.decoder.generator
        f0 = g.f0_upsamp(f0_curve[:, None]).transpose(1, 2)  # [B, L, 1]
        # Note: SourceModule returns noi_source, but Generator never uses it
        # (only har_source → STFT). uv_noise is therefore graph-dead; kept as
        # optional API input for inventory honesty, but export may drop it.
        har_source, _noi_source, _uv = self._source_forward(
            f0, sine_noise, uv_noise, phase_rand
        )
        har_source = har_source.transpose(1, 2).squeeze(1)
        har_spec, har_phase = g.stft.transform(har_source)
        har = torch.cat([har_spec, har_phase], dim=1)
        for i in range(g.num_upsamples):
            x = F.leaky_relu(x, negative_slope=0.1)
            x_source = g.noise_convs[i](har)
            x_source = g.noise_res[i](x_source, s)
            x = g.ups[i](x)
            if i == g.num_upsamples - 1:
                x = g.reflection_pad(x)
            x = x + x_source
            xs = None
            for j in range(g.num_kernels):
                if xs is None:
                    xs = g.resblocks[i * g.num_kernels + j](x, s)
                else:
                    xs = xs + g.resblocks[i * g.num_kernels + j](x, s)
            x = xs / g.num_kernels
        x = F.leaky_relu(x)
        x = g.conv_post(x)
        spec = torch.exp(x[:, : g.post_n_fft // 2 + 1, :])
        phase = torch.sin(x[:, g.post_n_fft // 2 + 1 :, :])
        return g.stft.inverse(spec, phase)

    def forward(
        self,
        asr: torch.Tensor,
        F0_curve: torch.Tensor,
        N: torch.Tensor,
        s: torch.Tensor,
        sine_noise: torch.Tensor,
        uv_noise: torch.Tensor,
        phase_rand: torch.Tensor,
    ) -> torch.Tensor:
        d = self.decoder
        F0 = d.F0_conv(F0_curve.unsqueeze(1))
        Nn = d.N_conv(N.unsqueeze(1))
        x = torch.cat([asr, F0, Nn], dim=1)
        x = d.encode(x, s)
        asr_res = d.asr_res(asr)
        res = True
        for block in d.decode:
            if res:
                x = torch.cat([x, asr_res, F0, Nn], dim=1)
            x = block(x, s)
            if block.upsample_type != "none":
                res = False
        x = self._generator_forward(x, s, F0_curve, sine_noise, uv_noise, phase_rand)
        # Force static output shape for ONNX (CustomSTFT inverse can look dynamic).
        x = x.reshape(1, 1, AUDIO_LEN)
        return x


def sample_noises(
    audio_len: int = AUDIO_LEN,
    dim: int = HARMONIC_DIM,
    seed: int = SEED,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    g = torch.Generator(device="cpu")
    g.manual_seed(seed)
    sine_noise = torch.randn(1, audio_len, dim, generator=g)
    uv_noise = torch.randn(1, audio_len, 1, generator=g)
    phase_rand = torch.rand(1, dim, generator=g)
    phase_rand = phase_rand.clone()
    phase_rand[:, 0] = 0.0
    return sine_noise, uv_noise, phase_rand


def wave_metrics(a: torch.Tensor, b: torch.Tensor) -> Dict[str, float]:
    a = a.detach().float().reshape(-1).cpu()
    b = b.detach().float().reshape(-1).cpu()
    n = min(a.numel(), b.numel())
    a, b = a[:n], b[:n]
    diff = (a - b).abs()
    a0, b0 = a - a.mean(), b - b.mean()
    denom = float(torch.sqrt((a0 * a0).sum() * (b0 * b0).sum()).clamp_min(1e-12))
    corr = float((a0 * b0).sum() / denom) if n else float("nan")
    return {
        "n": int(n),
        "maxdiff": float(diff.max()) if n else float("nan"),
        "mean_abs": float(diff.mean()) if n else float("nan"),
        "corr": corr,
    }


def save_wav(path: Path, audio: torch.Tensor, sr: int = SAMPLE_RATE) -> None:
    x = audio.detach().float().cpu().numpy().reshape(-1)
    x = np.clip(x, -1.0, 1.0)
    pcm = (x * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def text_to_phonemes(text: str) -> str:
    from kokoro import KPipeline

    pipe = KPipeline(lang_code="a", model=False)
    # KPipeline yields chunks; take first grapheme→phoneme for short lines
    parts = []
    for result in pipe(text):
        # result is a Result or tuple depending on version
        ps = getattr(result, "phonemes", None)
        if ps is None and isinstance(result, (tuple, list)):
            ps = result[0] if result else ""
        if ps:
            parts.append(ps)
    if not parts:
        raise RuntimeError(f"No phonemes for text={text!r}")
    return "".join(parts)


def build_edge_padded_seam(
    ref_model: nn.Module,
    phonemes: str,
    voice_path: str,
    t_bucket: int = T_BUCKET,
) -> Dict[str, torch.Tensor]:
    input_ids = phonemes_to_input_ids(ref_model, phonemes)
    ref_s = load_ref_s(voice_path, phonemes)
    seam = construct_seam_inputs(ref_model, input_ids, ref_s, speed=SPEED)
    seam = {k: v.detach().cpu().float() for k, v in seam.items()}
    t = seam["asr"].shape[-1]
    if t > t_bucket:
        raise ValueError(f"native T={t} > bucket {t_bucket}; need larger bucket")
    padded = pad_seam(seam, t_bucket, mode="edge")
    padded["t_native"] = torch.tensor([t], dtype=torch.long)
    return padded


def real_region_audio(audio: torch.Tensor, t_native: int) -> torch.Tensor:
    n = int(t_native) * SAMPLES_PER_FRAME
    a = audio.reshape(-1)
    return a[:n]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--weights", default=DEFAULT_WEIGHTS)
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "g2")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--opset", type=int, default=OPSET)
    ap.add_argument("--skip-export", action="store_true")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "t_bucket": T_BUCKET,
        "pad_mode": "edge",
        "audio_len": AUDIO_LEN,
        "opset": args.opset,
        "noise_sites": [
            {
                "name": "phase_rand",
                "source": "SineGen._f02sine torch.rand",
                "shape": [1, HARMONIC_DIM],
            },
            {
                "name": "sine_noise",
                "source": "SineGen.forward randn_like(sine_waves)",
                "shape": [1, AUDIO_LEN, HARMONIC_DIM],
            },
            {
                "name": "uv_noise",
                "source": "SourceModuleHnNSF.forward randn_like(uv)",
                "shape": [1, AUDIO_LEN, 1],
            },
        ],
        "n_noise_sites": 3,
    }
    print("## Noise hoist inventory (3 sites — within note_18 threshold ≤3)")
    for s in report["noise_sites"]:
        print(f"  {s['name']}: {s['shape']}  ← {s['source']}")

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    print("\n## G0 load + allowlist")
    decoder, missing, unexpected, _ = g0_strict_load_decoder(
        config, args.weights, disable_complex=True
    )
    g0 = g0_allowlist_check(missing, unexpected)
    report["g0"] = g0
    if not g0["g0_pass_amended"]:
        print("HARD STOP G0")
        (args.out / "g2_result.json").write_text(json.dumps(report, indent=2))
        return 2

    export_mod = DecoderExport(decoder).eval()
    print(
        "Export module forward signature: "
        "forward(asr, F0_curve, N, style, sine_noise, uv_noise, phase_rand)"
    )
    print(
        f"Static shapes: asr[1,512,{T_BUCKET}] F0/N[1,{F0_LEN}] style[1,128] "
        f"sine_noise[1,{AUDIO_LEN},{HARMONIC_DIM}] uv_noise[1,{AUDIO_LEN},1] "
        f"phase_rand[1,{HARMONIC_DIM}] → audio[1,1,{AUDIO_LEN}]"
    )

    # Reference model for frontend
    set_determinism(args.seed)
    ref_model = load_reference_kmodel(args.config, args.weights, disable_complex=True)

    # --- Parity on ladder text (edge-padded) ---
    print("\n## Export-parity prep (ladder text, edge pad)")
    set_determinism(args.seed)
    seam = build_edge_padded_seam(ref_model, PHONEMES, args.voice, T_BUCKET)
    t_native = int(seam.pop("t_native").item())
    sine_n, uv_n, phase_r = sample_noises(AUDIO_LEN, HARMONIC_DIM, args.seed)

    with torch.no_grad():
        pt_audio = export_mod(
            seam["asr"],
            seam["F0_pred"],
            seam["N_pred"],
            seam["style"],
            sine_n,
            uv_n,
            phase_r,
        )
    pt_audio = pt_audio.squeeze().cpu().float()
    assert pt_audio.numel() == AUDIO_LEN, pt_audio.shape

    # Cross-check: original decoder with same seed should be close if we
    # drive the same RNG sequence — optional diagnostic only.
    set_determinism(args.seed)
    with torch.no_grad():
        orig = decoder(
            seam["asr"], seam["F0_pred"], seam["N_pred"], seam["style"]
        ).squeeze().cpu().float()
    # orig uses internal randn; not identical to hoisted unless we matched draws.
    # Report as diagnostic, not gate.
    diag = wave_metrics(real_region_audio(orig, t_native), real_region_audio(pt_audio, t_native))
    report["diagnostic_orig_decoder_vs_export_mod_same_seed"] = diag
    print(f"diagnostic orig-vs-export_mod (same seed, not gate): {diag}")

    onnx_path = args.out / "kokoro_decoder_t96_edge.onnx"
    if not args.skip_export:
        print("\n## ONNX export")
        dummy = (
            seam["asr"],
            seam["F0_pred"],
            seam["N_pred"],
            seam["style"],
            sine_n,
            uv_n,
            phase_r,
        )
        # uv_noise is unused by Generator (noi_source discarded) — export without it
        # so ORT feeds match the live graph. phase_rand + sine_noise remain.
        class _ExportNoUv(nn.Module):
            def __init__(self, core: DecoderExport):
                super().__init__()
                self.core = core

            def forward(self, asr, F0_curve, N, s, sine_noise, phase_rand):
                # zeros same shape as would-be uv_noise; no effect on outputs
                uv_noise = torch.zeros(
                    sine_noise.shape[0],
                    sine_noise.shape[1],
                    1,
                    dtype=sine_noise.dtype,
                    device=sine_noise.device,
                )
                return self.core(
                    asr, F0_curve, N, s, sine_noise, uv_noise, phase_rand
                )

        export_for_onnx = _ExportNoUv(export_mod).eval()
        dummy_onnx = (
            seam["asr"],
            seam["F0_pred"],
            seam["N_pred"],
            seam["style"],
            sine_n,
            phase_r,
        )
        input_names = ["asr", "F0", "N", "style", "sine_noise", "phase_rand"]
        output_names = ["audio"]
        # Prefer legacy exporter for this graph (CustomSTFT + interpolate path).
        torch.onnx.export(
            export_for_onnx,
            dummy_onnx,
            str(onnx_path),
            input_names=input_names,
            output_names=output_names,
            opset_version=args.opset,
            do_constant_folding=True,
            dynamic_axes=None,
            dynamo=False,
        )
        import onnx

        model_onnx = onnx.load(str(onnx_path))
        onnx.checker.check_model(model_onnx)
        print(f"onnx.checker PASS  path={onnx_path}")
        print(f"opset={args.opset}")
        for inp in model_onnx.graph.input:
            t = inp.type.tensor_type
            dims = [d.dim_value for d in t.shape.dim]
            print(f"  input {inp.name}: {dims}")
        for out in model_onnx.graph.output:
            t = out.type.tensor_type
            dims = [d.dim_value for d in t.shape.dim]
            print(f"  output {out.name}: {dims}")
        report["onnx_path"] = str(onnx_path)
        report["onnx_checker"] = "PASS"
        report["io_shapes"] = {
            "inputs": {
                inp.name: [d.dim_value for d in inp.type.tensor_type.shape.dim]
                for inp in model_onnx.graph.input
            },
            "outputs": {
                out.name: [d.dim_value for d in out.type.tensor_type.shape.dim]
                for out in model_onnx.graph.output
            },
        }

        print("\n## ORT-CPU export parity (identical edge-padded inputs + noise)")
        import onnxruntime as ort

        sess = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        feeds = {
            "asr": seam["asr"].numpy(),
            "F0": seam["F0_pred"].numpy(),
            "N": seam["N_pred"].numpy(),
            "style": seam["style"].numpy(),
            "sine_noise": sine_n.numpy(),
            "phase_rand": phase_r.numpy(),
        }
        # PT reference must match export graph (no uv_noise effect)
        with torch.no_grad():
            pt_audio = export_for_onnx(
                seam["asr"],
                seam["F0_pred"],
                seam["N_pred"],
                seam["style"],
                sine_n,
                phase_r,
            ).squeeze().cpu().float()
        ort_out = sess.run(None, feeds)[0]
        ort_audio = torch.from_numpy(np.asarray(ort_out)).float().reshape(-1)
        # Full buffer + real region
        full_m = wave_metrics(pt_audio, ort_audio)
        real_m = wave_metrics(
            real_region_audio(pt_audio, t_native),
            real_region_audio(ort_audio, t_native),
        )
        report["export_parity"] = {
            "pad_mode": "edge",
            "comparison": "PyTorch DecoderExport vs ORT-CPU, identical inputs+noise",
            "full_buffer": full_m,
            "real_region": real_m,
            "t_native": t_native,
            "bar_maxdiff": 1e-3,
            "bar_corr": 0.9999,
        }
        pass_md = real_m["maxdiff"] <= 1e-3
        pass_corr = real_m["corr"] >= 0.9999
        g2_parity_pass = bool(pass_md or pass_corr)
        report["export_parity"]["g2_parity_pass"] = g2_parity_pass
        print(
            f"  full:  maxdiff={full_m['maxdiff']:.6g} corr={full_m['corr']:.8f}\n"
            f"  real:  maxdiff={real_m['maxdiff']:.6g} corr={real_m['corr']:.8f}  "
            f"PASS={g2_parity_pass}"
        )
        save_wav(args.out / "parity_pt.wav", real_region_audio(pt_audio, t_native))
        save_wav(args.out / "parity_ort.wav", real_region_audio(ort_audio, t_native))
    else:
        g2_parity_pass = False
        report["onnx_checker"] = "skipped"

    # --- Ear set ---
    print("\n## Ear set (≥3 utterances, CPU frontend → ONNX decoder → real-region trim)")
    ear_files = []
    if onnx_path.exists():
        import onnxruntime as ort

        sess = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        for i, text in enumerate(EAR_TEXTS):
            set_determinism(args.seed + 10 + i)
            try:
                ps = text_to_phonemes(text) if i > 0 else PHONEMES
            except Exception as e:
                print(f"  phoneme fail text[{i}]: {e}")
                if i == 0:
                    ps = PHONEMES
                else:
                    continue
            set_determinism(args.seed + 10 + i)
            try:
                seam_i = build_edge_padded_seam(ref_model, ps, args.voice, T_BUCKET)
            except ValueError as e:
                print(f"  skip ear[{i}]: {e}")
                continue
            t_n = int(seam_i.pop("t_native").item())
            sn, un, pr = sample_noises(AUDIO_LEN, HARMONIC_DIM, args.seed + 10 + i)
            feeds = {
                "asr": seam_i["asr"].numpy(),
                "F0": seam_i["F0_pred"].numpy(),
                "N": seam_i["N_pred"].numpy(),
                "style": seam_i["style"].numpy(),
                "sine_noise": sn.numpy(),
                "phase_rand": pr.numpy(),
            }
            audio = torch.from_numpy(sess.run(None, feeds)[0]).float().reshape(-1)
            audio_r = real_region_audio(audio, t_n)
            fname = f"ear_{i+1}.wav"
            save_wav(args.out / fname, audio_r)
            meta = {
                "file": fname,
                "text": text,
                "phonemes": ps,
                "t_native": t_n,
                "n_samples": int(audio_r.numel()),
                "pad_mode": "edge",
            }
            ear_files.append(meta)
            print(f"  wrote {fname}  T={t_n}  samples={audio_r.numel()}  text={text!r}")
    report["ear_set"] = ear_files
    report["g2_parity_pass"] = report.get("export_parity", {}).get(
        "g2_parity_pass", False
    )
    report["awaiting_nexus_ears"] = True
    report["uv_noise_note"] = (
        "uv_noise/SourceModule noi_source is unused by Generator; "
        "ONNX graph inputs are asr,F0,N,style,sine_noise,phase_rand only."
    )

    out_json = args.out / "g2_result.json"
    out_json.write_text(json.dumps(report, indent=2))
    print(f"\n**G2 parity pass:** {report['g2_parity_pass']}")
    print(f"**Ear files for Nexus:** {[e['file'] for e in ear_files]}")
    print(f"wrote {out_json}")
    # Exit 0 if onnx+ears produced even when parity bar fails — note carries verdict
    return 0 if ear_files else 1


if __name__ == "__main__":
    raise SystemExit(main())
