#!/usr/bin/env bash
# Source this to enter the project environment from any checkout:
#   source scripts/env.sh

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export INTEL_IGPU_TTS_ROOT="$PROJECT_ROOT"
export INTEL_IGPU_TTS_MODELS="$PROJECT_ROOT/models"
export INTEL_IGPU_TTS_CACHE="$PROJECT_ROOT/cache"
export OV_CACHE_DIR="${OV_CACHE_DIR:-$PROJECT_ROOT/cache/openvino}"
export ORT_OPENVINO_CACHE_DIR="${ORT_OPENVINO_CACHE_DIR:-$PROJECT_ROOT/cache/ort}"
mkdir -p "$OV_CACHE_DIR" "$ORT_OPENVINO_CACHE_DIR" "$PROJECT_ROOT/logs" "$PROJECT_ROOT/artifacts"

# Optional: import oneAPI env without sourcing setvars.sh in-process.
# (setvars.sh uses return/exit patterns that can break caller scripts under set -e.)
if [[ -z "${INTEL_IGPU_TTS_ONEAPI_LOADED:-}" && -f /opt/intel/oneapi/setvars.sh ]]; then
  _oneapi_exports="$(
    bash --noprofile --norc -c '
      source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1 || true
      export -p
    ' 2>/dev/null | grep -E '^declare -x (PATH|LD_LIBRARY_PATH|LIBRARY_PATH|PKG_CONFIG_PATH|CMAKE_PREFIX_PATH|ACL_BOARD_VENDOR_PATH|CPATH|NLSPATH|MANPATH|ONEAPI_ROOT|CMPLR_ROOT|INTELGPU|INTEL_)|_ROOT=|^declare -x ZE_|^declare -x SYCL_|^declare -x OCL_|^declare -x OpenCL_|^declare -x DNNL_|^declare -x TBB|^declare -x MKL|^declare -x FI_|^declare -x CLASSPATH=' || true
  )"
  if [[ -n "${_oneapi_exports}" ]]; then
    eval "${_oneapi_exports}"
  else
    if [[ -d /opt/intel/oneapi/compiler/latest/bin ]]; then
      export PATH="/opt/intel/oneapi/compiler/latest/bin:${PATH}"
    elif [[ -d /opt/intel/oneapi/compiler/2026.1/bin ]]; then
      export PATH="/opt/intel/oneapi/compiler/2026.1/bin:${PATH}"
    fi
  fi
  unset _oneapi_exports
  export INTEL_IGPU_TTS_ONEAPI_LOADED=1
fi

# Project venv takes precedence once it exists
if [[ -f "$PROJECT_ROOT/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/venv/bin/activate"
fi

export PATH="$PROJECT_ROOT/scripts:$PATH"

echo "[intel-igpu-tts] root=$PROJECT_ROOT"
echo "[intel-igpu-tts] models=$INTEL_IGPU_TTS_MODELS"
echo "[intel-igpu-tts] python=$(command -v python3 2>/dev/null || true) ($(python3 -V 2>/dev/null || true))"
if command -v sycl-ls >/dev/null 2>&1; then
  echo "[intel-igpu-tts] sycl devices:"
  sycl-ls 2>/dev/null | sed 's/^/  /' || true
fi
