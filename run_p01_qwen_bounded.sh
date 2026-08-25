#!/usr/bin/env bash
# Bounded calibration run: p01_linear only, Qwen, 3 turns, $1 cap.
set -euo pipefail
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
export LEAN_CONTAINER_MEMORY="${LEAN_CONTAINER_MEMORY:-8g}"
export BASELINE_MODEL="${BASELINE_MODEL:-qwen/qwen3.5-flash-02-23}"
export BASELINE_MAX_TURNS="${BASELINE_MAX_TURNS:-3}"

KIT="$HOME/verified-mechanism/re-takehome-main"
TMPSET="$HOME/verified-mechanism/tmp-p01-set"
cd "$KIT"

rm -rf "$TMPSET"
mkdir -p "$TMPSET/p01_linear"
cp sample-problems/p01_linear/problem.md sample-problems/p01_linear/challenge.lean "$TMPSET/p01_linear/"
cat > "$TMPSET/manifest.json" <<'EOF'
{
  "schema_version": 1,
  "set": "tmp_p01_only",
  "problems": [
    {
      "id": "p01_linear",
      "theorem_names": ["p01_linear"],
      "definition_names": [],
      "numeric_answer_names": []
    }
  ]
}
EOF

echo "=== RUN START $(date -Iseconds) ==="
echo "model=$BASELINE_MODEL turns=$BASELINE_MAX_TURNS mem=$LEAN_CONTAINER_MEMORY problem=p01_linear"
echo "budget/time from .env via harness"

.venv/bin/python run.py \
  --problems "$TMPSET" \
  --out outputs \
  --agent baselines.simple_agent:create_agent

echo "=== RUN END $(date -Iseconds) ==="

# Latest baseline run directory
RUNDIR="$(ls -1dt outputs/baseline/*/ 2>/dev/null | head -1 || true)"
echo "RUNDIR=$RUNDIR"
if [ -n "${RUNDIR}" ]; then
  .venv/bin/python - <<PY
import json
from pathlib import Path
run = Path(r"""$RUNDIR""")
summary = run / "summary.json"
result = run / "p01_linear" / "result.json"
print("--- summary ---")
if summary.exists():
    s = json.loads(summary.read_text(encoding="utf-8"))
    print("total_points", s.get("total_points"), "/", s.get("max_points"))
    print("actual_cost_usd", s.get("actual_cost_usd"))
    print("wall_s", s.get("wall_s"))
    for p in s.get("problems", []):
        print(p)
print("--- result ---")
if result.exists():
    r = json.loads(result.read_text(encoding="utf-8"))
    for k in (
        "problem_id", "status", "passed", "points",
        "actual_cost_usd", "reserved_cost_usd", "wall_s",
        "models_used", "failure_reason", "agent_metadata",
    ):
        if k in r:
            print(f"{k}: {r[k]}")
PY
fi
