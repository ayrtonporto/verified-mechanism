#!/usr/bin/env bash
# Poll S-G calib status (no nested shell vars from Windows)
set -euo pipefail
LOG=/home/ayrton/verified-mechanism/run_p01_sg_calib.log
OUT=/home/ayrton/verified-mechanism/re-takehome-main/outputs/s_g
echo "=== POLL $(date -Iseconds) ==="
pgrep -af 'run_p01_sg|run.py|re_harness.worker' || echo NO_PROC
echo "--- log ---"
if [ -f "$LOG" ]; then
  tail -30 "$LOG"
else
  echo "no log yet"
fi
echo "--- outputs ---"
ls -la "$OUT" 2>/dev/null || echo "no s_g dir"
LATEST=$(ls -1dt "$OUT"/*/ 2>/dev/null | head -1 || true)
echo "LATEST=${LATEST:-none}"
if [ -n "${LATEST:-}" ]; then
  ls -la "${LATEST}p01_linear" 2>/dev/null || true
  if [ -f "${LATEST}summary.json" ]; then
    echo HAS_SUMMARY
    cat "${LATEST}summary.json"
  else
    echo NO_SUMMARY
  fi
  if [ -f "${LATEST}p01_linear/result.json" ]; then
    echo HAS_RESULT
    cat "${LATEST}p01_linear/result.json" | head -c 2500
    echo
  fi
  if [ -f "${LATEST}p01_linear/events.jsonl" ]; then
    wc -l "${LATEST}p01_linear/events.jsonl"
    python3 -c "
import json
from pathlib import Path
p=Path('${LATEST}p01_linear/events.jsonl')
for line in p.read_text().splitlines():
    e=json.loads(line)
    print(e.get('seq'), e.get('event'), e.get('actual_cost_usd',''))
"
  fi
fi
if grep -q 'S-G CALIB END' "$LOG" 2>/dev/null; then
  echo STATUS=DONE
  exit 0
fi
if pgrep -f 'run_p01_sg_calib.sh' >/dev/null || pgrep -f 'run.py --problems' >/dev/null; then
  echo STATUS=RUNNING
  exit 0
fi
echo STATUS=DEAD
exit 1
