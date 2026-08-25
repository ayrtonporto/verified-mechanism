#!/usr/bin/env bash
# S-G twin calib: GPT-OSS solo x p01_linear
# Mirror of run_p01_e2e_clean.sh with experiments_agents.s_g factory.
# Run: wsl.exe -d Ubuntu-22.04 -- bash /home/ayrton/verified-mechanism/run_p01_sg_calib.sh
set -euo pipefail

export PATH="/home/ayrton/.pyshim:/home/ayrton/.local/bin:/usr/local/bin:/usr/bin:/bin"
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900
export LEAN_CHECK_TIMEOUT_S=300
export BASELINE_MAX_TURNS=3
export BASELINE_MODEL=openai/gpt-oss-120b

KIT=/home/ayrton/verified-mechanism/re-takehome-main
TMPSET=/home/ayrton/verified-mechanism/tmp-p01-set
LOG=/home/ayrton/verified-mechanism/run_p01_sg_calib.log
cd "$KIT"
# kit root on path so experiments_agents + baselines import in worker children
export PYTHONPATH="${KIT}${PYTHONPATH:+:$PYTHONPATH}"

exec > >(tee "$LOG") 2>&1

echo "========== S-G CALIB START $(date -Iseconds) =========="
echo "agent=experiments_agents.s_g:create_agent"
echo "BASELINE_MAX_TURNS=$BASELINE_MAX_TURNS"
echo "LEAN_CONTAINER_MEMORY=$LEAN_CONTAINER_MEMORY"
echo "COMPARATOR_TIMEOUT_S=$COMPARATOR_TIMEOUT_S"
free -h | head -2

# drop incomplete prior s_g runs
if [ -d outputs/s_g ]; then
  for d in outputs/s_g/*/; do
    [ -d "$d" ] || continue
    if [ ! -f "${d}summary.json" ]; then
      echo "removing incomplete $d"
      rm -rf "$d"
    fi
  done
fi

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

.venv/bin/python - <<'PY'
from re_harness.config import HarnessSettings
from re_harness.lean import _container_memory
from experiments_agents.s_g import create_agent
s = HarnessSettings.from_env(n_workers=1)
assert s.api_key.startswith("sk-"), "missing key"
assert s.budget_usd == 1.0
assert s.comparator_timeout_s == 900, s.comparator_timeout_s
assert _container_memory() == "8g", _container_memory()
a = create_agent()
assert a.model == "openai/gpt-oss-120b" and a.arm == "S-G"
print(
    "preflight_ok",
    "budget", s.budget_usd,
    "comparator_timeout", s.comparator_timeout_s,
    "container_mem", _container_memory(),
    "agent_model", a.model,
    "max_turns", a.max_turns,
)
PY

echo "=== run.py begin $(date -Iseconds) ==="
.venv/bin/python run.py \
  --problems "$TMPSET" \
  --out outputs \
  --agent experiments_agents.s_g:create_agent
echo "=== run.py end $(date -Iseconds) ==="

.venv/bin/python - <<'PY'
import json
from pathlib import Path

base = Path("outputs/s_g")
candidates = sorted(
    [p for p in base.iterdir() if p.is_dir() and p.name[0].isdigit()],
    key=lambda p: p.name,
    reverse=True,
)
if not candidates:
    raise SystemExit("no timestamped s_g runs found")
run = candidates[0]
print("RUNDIR", run)
summary = run / "summary.json"
result = run / "p01_linear" / "result.json"
print("--- summary.json ---")
if summary.exists():
    s = json.loads(summary.read_text(encoding="utf-8"))
    print("set", s.get("set"))
    print("total_points", s.get("total_points"), "/", s.get("max_points"))
    print("actual_cost_usd", s.get("actual_cost_usd"))
    print("wall_s", s.get("wall_s"))
    for p in s.get("problems", []):
        print(p)
else:
    print("missing summary")
print("--- result.json ---")
if result.exists():
    r = json.loads(result.read_text(encoding="utf-8"))
    for k in (
        "problem_id", "status", "passed", "points",
        "wall_s", "models_used", "failure_reason",
    ):
        if k in r:
            print(f"{k}: {r[k]}")
    print("budget.spent_usd", (r.get("budget") or {}).get("spent_usd"))
    c = r.get("comparator") or {}
    print("comparator.passed", c.get("passed"))
    print("comparator.timed_out", c.get("timed_out"))
    print("comparator.duration_ms", c.get("duration_ms"))
    print("agent_metadata", r.get("agent_metadata"))
else:
    print("missing result")

ev = run / "p01_linear" / "events.jsonl"
if ev.exists():
    cost = 0.0
    n = 0
    for line in ev.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e.get("event") == "llm_response":
            n += 1
            cost += float(e.get("actual_cost_usd") or 0)
    print(f"events_llm_calls={n} events_cost_usd={cost}")
PY

echo "========== S-G CALIB END $(date -Iseconds) =========="
