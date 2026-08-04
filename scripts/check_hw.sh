#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source /data/intel-igpu-tts/scripts/env.sh

echo "=== DRI nodes ==="
ls -la /dev/dri/

echo
echo "=== i915 binding ==="
lspci -nnk | grep -A4 -i 'vga\|display'

echo
echo "=== Group membership ==="
id

echo
echo "=== OpenCL (clinfo -l) ==="
clinfo -l || true

echo
echo "=== Level Zero / SYCL (sycl-ls) ==="
if command -v sycl-ls >/dev/null 2>&1; then
  sycl-ls
else
  echo "sycl-ls not on PATH (source env.sh / oneAPI setvars)"
fi

echo
echo "=== intel_gpu_top present? ==="
command -v intel_gpu_top || echo "missing"

echo
echo "=== Quick render node read access ==="
if [[ -r /dev/dri/renderD128 ]]; then
  echo "renderD128 readable: OK"
else
  echo "renderD128 readable: FAIL"
fi

echo
echo "Hardware recognition check complete."
