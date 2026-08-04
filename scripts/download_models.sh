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
echo
echo "Next: build the GPU-friendly patched graph:"
echo "  source scripts/env.sh"
echo "  python scripts/patch_kokoro_v2.py \\"
echo "    --model models/kokoro-v0_19.onnx \\"
echo "    --output models/patched/kokoro-v0_19.gpu4d.stft.onnx \\"
echo "    --stamp-stft"
