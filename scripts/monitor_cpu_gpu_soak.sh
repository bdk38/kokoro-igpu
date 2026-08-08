#!/bin/bash
# 1 Hz CPU + intel_gpu_top join logger for Kokoro soak.
set -u
ROOT=/data/intel-igpu-tts
JOIN="$ROOT/logs/cpu_gpu_monitor_ovgpu_soak.log"
GPULOG="$ROOT/logs/gpu_monitor_ovgpu_soak.log"
STATUS=/tmp/kokoro_cpu_gpu_status.txt
KPID=$(cat /tmp/kokoro-server.pid 2>/dev/null || true)

mkdir -p "$ROOT/logs"
echo "t_iso load1 kokoro_pcpu kokoro_rss_mb host_busy_pct gpu_max_pct gpu_rcs_pct" > "$JOIN"

prev_total=0
prev_idle=0
read_cpu() {
  read -r _ u n s i iq si st rest < /proc/stat
  echo $((u + n + s + i + iq + si + st)) "$i"
}
read prev_total prev_idle < <(read_cpu)

for _ in $(seq 1 3600); do
  ts=$(date -Iseconds)
  read -r l1 _ < /proc/loadavg

  if [[ -n "${KPID:-}" && -d "/proc/$KPID" ]]; then
    pcpu=$(ps -p "$KPID" -o pcpu= | tr -d ' ')
    rss=$(ps -p "$KPID" -o rss= | tr -d ' ')
    rss_mb=$(awk -v r="$rss" 'BEGIN { printf "%.1f", r / 1024 }')
  else
    pcpu=NA
    rss_mb=NA
  fi

  read -r c_total c_idle < <(read_cpu)
  dt=$((c_total - prev_total))
  di=$((c_idle - prev_idle))
  if (( dt > 0 )); then
    hbusy=$(awk -v dt="$dt" -v di="$di" 'BEGIN { printf "%.1f", 100 * (1 - di / dt) }')
  else
    hbusy=0
  fi

  read -r gmax grcs < <(python3 - "$GPULOG" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.exists() or p.stat().st_size == 0:
    print("NA NA")
    raise SystemExit
s = p.read_text(errors="replace").strip()
if s.startswith("["):
    s = s[1:]
dec = json.JSONDecoder()
idx = 0
last = None
while idx < len(s):
    while idx < len(s) and s[idx] in " \n\r\t,":
        idx += 1
    if idx >= len(s) or s[idx] == "]":
        break
    try:
        o, off = dec.raw_decode(s, idx)
        last = o
        idx = off
    except Exception:
        break
if not last:
    print("NA NA")
    raise SystemExit
engines = last.get("engines") or {}
vals = []
rcs = None

def add(name, busy):
    global rcs
    if busy is None:
        return
    try:
        b = float(busy)
    except Exception:
        return
    if b <= 1.0:
        b *= 100.0
    vals.append(b)
    n = str(name).lower()
    if "render" in n or n.startswith("rcs"):
        rcs = b

if isinstance(engines, list):
    for e in engines:
        add(e.get("name") or e.get("class") or "", e.get("busy", e.get("load")))
elif isinstance(engines, dict):
    for k, v in engines.items():
        if isinstance(v, dict):
            add(k, v.get("busy", v.get("load")))
        else:
            add(k, v)
gmax = max(vals) if vals else None

def fmt(x):
    return "NA" if x is None else f"{x:.1f}"

print(fmt(gmax), fmt(rcs))
PY
)

  printf "%s %s %s %s %s %s %s\n" "$ts" "$l1" "$pcpu" "$rss_mb" "$hbusy" "$gmax" "$grcs" >> "$JOIN"
  printf "[%s] load %s | kokoro CPU %s%% RSS %sMB | host busy %s%% | GPU max %s%% rcs %s%%\n" \
    "$ts" "$l1" "$pcpu" "$rss_mb" "$hbusy" "$gmax" "$grcs" > "$STATUS"

  prev_total=$c_total
  prev_idle=$c_idle
  sleep 1
done
