#!/usr/bin/env bash
# Download stock Kokoro assets into ./models (weights are not shipped in git).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS="$ROOT/models"
mkdir -p "$MODELS" "$MODELS/patched"

echo "[download] target=$MODELS"

download() {
  local url="$1" out="$2"
  if [[ -f "$out" ]]; then
    echo "[skip] $out"
    return 0
  fi
  echo "[get] $url"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 -o "$out" "$url"
  else
    wget -O "$out" "$url"
  fi
}

# Primary path used by this PoC: v0.19 ONNX + voices pack.
# Sources may move; override with env URLs if needed.
KOKORO_ONNX_URL="${KOKORO_ONNX_URL:-https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx}"
VOICES_URL="${VOICES_URL:-https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin}"

download "$KOKORO_ONNX_URL" "$MODELS/kokoro-v0_19.onnx"

# This repo expects voices-v1.0.bin
if [[ ! -f "$MODELS/voices-v1.0.bin" ]]; then
  tmp="$MODELS/.voices-download.bin"
  download "$VOICES_URL" "$tmp"
  mv "$tmp" "$MODELS/voices-v1.0.bin"
fi

echo "[download] done"
ls -lh "$MODELS/kokoro-v0_19.onnx" "$MODELS/voices-v1.0.bin"

# Expected hashes (MODELS.md) — warn on mismatch, do not delete
EXPECTED_ONNX_SHA="dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c"
EXPECTED_VOICES_SHA="d19762d46cf0e6648cb28a7711df1637aad15818185d13f4ff840d57f2f6dfed"
if command -v sha256sum >/dev/null 2>&1; then
  got=$(sha256sum "$MODELS/kokoro-v0_19.onnx" | awk '{print $1}')
  if [[ "$got" != "$EXPECTED_ONNX_SHA" ]]; then
    echo "[warn] kokoro-v0_19.onnx sha256 mismatch: $got" >&2
    echo "[warn] expected $EXPECTED_ONNX_SHA" >&2
  else
    echo "[ok] kokoro-v0_19.onnx sha256"
  fi
  got=$(sha256sum "$MODELS/voices-v1.0.bin" | awk '{print $1}')
  if [[ "$got" != "$EXPECTED_VOICES_SHA" ]]; then
    echo "[warn] voices-v1.0.bin sha256 mismatch: $got" >&2
    echo "[warn] expected $EXPECTED_VOICES_SHA" >&2
  else
    echo "[ok] voices-v1.0.bin sha256"
  fi
fi
echo
echo "Next: build the GPU-friendly patched graph:"
echo "  source scripts/env.sh"
echo "  python scripts/patch_kokoro_v2.py \\"
echo "    --model models/kokoro-v0_19.onnx \\"
echo "    --output models/patched/kokoro-v0_19.gpu4d.stft.onnx \\"
echo "    --stamp-stft"
