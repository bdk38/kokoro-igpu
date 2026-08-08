#!/usr/bin/env bash
# PoC + Prototype smoke: health + WAV out. ort-cpu required; GPU legs if device present.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/venv/bin/python"
[[ -x "$PY" ]] || PY="${PYTHON:-python3}"
OUT="${ROOT}/artifacts/poc_ship/smoke"
mkdir -p "$OUT"
PORT="${SMOKE_PORT:-8899}"
FOX='The quick brown fox jumps over the lazy dog.'

echo "[smoke] python=$PY root=$ROOT out=$OUT"
fail=0

speech_wav() {
  local backend_tag="$1"
  local wav="$OUT/${backend_tag}.wav"
  "$PY" - <<PY
import json, urllib.request
body = json.dumps({
    "input": """$FOX""",
    "voice": "af_bella",
    "response_format": "wav",
}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:${PORT}/v1/audio/speech",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=600) as r:
    open("""$wav""", "wb").write(r.read())
print("wrote", """$wav""")
PY
}

run_backend() {
  local backend="$1"
  shift
  local tag="$1"
  shift
  local log="$OUT/${tag}.log"
  if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
    echo "[smoke] port $PORT busy"; return 1
  fi
  env KOKORO_BACKEND="$backend" KOKORO_TTS_CACHE=0 "$@" \
    "$PY" scripts/kokoro_server.py --host 127.0.0.1 --port "$PORT" \
    >"$log" 2>&1 &
  local pid=$!
  local ok=0 i
  for i in $(seq 1 120); do
    if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      ok=1; break
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "[smoke] $tag server died early"; tail -25 "$log" || true
      return 1
    fi
    sleep 1
  done
  if [[ "$ok" != 1 ]]; then
    echo "[smoke] $tag health timeout"; tail -40 "$log" || true
    kill "$pid" 2>/dev/null || true
    return 1
  fi
  echo "[smoke] $tag health=$(curl -sf "http://127.0.0.1:${PORT}/health")"
  if ! speech_wav "$tag"; then
    echo "[smoke] $tag speech failed"; kill "$pid" 2>/dev/null || true; return 1
  fi
  local sz
  sz=$(wc -c <"$OUT/${tag}.wav" | tr -d ' ')
  echo "[smoke] $tag wav=$OUT/${tag}.wav bytes=$sz"
  if [[ "$sz" -lt 10000 ]]; then
    echo "[smoke] $tag WAV too small"
    kill "$pid" 2>/dev/null || true
    return 1
  fi
  echo "[smoke] $tag PASS → $OUT/${tag}.wav"
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  sleep 1
  return 0
}

echo "=== ort-cpu (required) ==="
if run_backend ort-cpu ort_cpu; then :; else fail=1; fi

if "$PY" -c "import openvino as ov; raise SystemExit(0 if 'GPU' in ov.Core().available_devices else 1)" 2>/dev/null; then
  echo "=== ov-gpu patched (if model present) ==="
  if [[ -f models/patched/kokoro-v0_19.gpu4d.stft.onnx ]]; then
    if run_backend ov-gpu ov_gpu \
      KOKORO_MODEL="${ROOT}/models/patched/kokoro-v0_19.gpu4d.stft.onnx" \
      KOKORO_GPU_PRECISION=f32; then :; else fail=1; fi
  else
    echo "[smoke] skip ov-gpu — patched model missing (MODELS.md)"
  fi
  echo "=== ovgenai-gpu (if pack present) ==="
  if [[ -f models/kokoro-82M-int8-ov/openvino_model.xml ]]; then
    if run_backend ovgenai-gpu ovgenai_gpu \
      KOKORO_GENAI_MODEL="${ROOT}/models/kokoro-82M-int8-ov"; then :; else fail=1; fi
  else
    echo "[smoke] skip ovgenai-gpu — pack missing (MODELS.md)"
  fi
else
  echo "[smoke] no OpenVINO GPU — skipped GPU legs"
fi

echo
echo "[smoke] WAV paths for ears:"
ls -la "$OUT"/*.wav 2>/dev/null || true
if [[ "$fail" -ne 0 ]]; then
  echo "[smoke] FAIL"; exit 1
fi
echo "[smoke] PASS"; exit 0
