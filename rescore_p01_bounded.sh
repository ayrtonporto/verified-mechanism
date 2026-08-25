#!/usr/bin/env bash
# Rescore only p01 from the bounded run (no LLM calls).
set -euo pipefail
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
export LEAN_CONTAINER_MEMORY="${LEAN_CONTAINER_MEMORY:-8g}"
export COMPARATOR_TIMEOUT_S="${COMPARATOR_TIMEOUT_S:-900}"

KIT="$HOME/verified-mechanism/re-takehome-main"
TMPSET="$HOME/verified-mechanism/tmp-p01-set"
RUN="$KIT/outputs/baseline/20260823T231035Z"
cd "$KIT"

test -f "$RUN/p01_linear/solution.lean"
test -f "$TMPSET/manifest.json"

echo "=== RESCORE START $(date -Iseconds) ==="
echo "run=$RUN mem=$LEAN_CONTAINER_MEMORY comparator_timeout=$COMPARATOR_TIMEOUT_S"
.venv/bin/python -m re_harness.evaluator \
  --problems "$TMPSET" \
  --out "$RUN" \
  --n-workers 1
echo "=== RESCORE END $(date -Iseconds) ==="

.venv/bin/python - <<'PY'
import json
from pathlib import Path
run = Path.home() / "verified-mechanism/re-takehome-main/outputs/baseline/20260823T231035Z"
for name in ("summary.json", "p01_linear/result.json"):
    p = run / name
    print("---", name, "---")
    if not p.exists():
        print("missing")
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    if name.endswith("summary.json"):
        print("total_points", data.get("total_points"), "/", data.get("max_points"))
        print("actual_cost_usd", data.get("actual_cost_usd"))
        for prob in data.get("problems", []):
            print(prob)
    else:
        for k in (
            "problem_id", "status", "passed", "points",
            "actual_cost_usd", "wall_s", "models_used", "failure_reason",
        ):
            if k in data:
                print(f"{k}: {data[k]}")
PY
