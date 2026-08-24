#!/usr/bin/env bash
# Clean bounded e2e: p01 only, Qwen, max 3 turns, $1 cap, 8g Lean, 900s comparator.
# Run ONLY as: wsl.exe -d Ubuntu-22.04 -- bash /home/ayrton/verified-mechanism/run_p01_e2e_clean.sh
set -euo pipefail

export PATH="/home/ayrton/.pyshim:/home/ayrton/.local/bin:/usr/local/bin:/usr/bin:/bin"
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900
export LEAN_CHECK_TIMEOUT_S=300
export BASELINE_MODEL=qwen/qwen3.5-flash-02-23
export BASELINE_MAX_TURNS=3

KIT=/home/ayrton/verified-mechanism/re-takehome-main
TMPSET=/home/ayrton/verified-mechanism/tmp-p01-set
LOG=/home/ayrton/verified-mechanism/run_p01_e2e_clean.log
cd "$KIT"

exec > >(tee "$LOG") 2>&1

echo "========== E2E START $(date -Iseconds) =========="
echo "model=$BASELINE_MODEL turns=$BASELINE_MAX_TURNS"
echo "LEAN_CONTAINER_MEMORY=$LEAN_CONTAINER_MEMORY"
echo "COMPARATOR_TIMEOUT_S=$COMPARATOR_TIMEOUT_S"
echo "LEAN_CHECK_TIMEOUT_S=$LEAN_CHECK_TIMEOUT_S"
free -h | head -2

# 1-problem set
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

# Confirm harness sees overrides
.venv/bin/python - <<'PY'
import os
from re_harness.config import HarnessSettings
from re_harness.lean import _container_memory
s = HarnessSettings.from_env(n_workers=1)
assert s.api_key.startswith("sk-"), "missing key"
assert s.budget_usd == 1.0
assert s.comparator_timeout_s == 900, s.comparator_timeout_s
assert _container_memory() == "8g", _container_memory()
print("preflight_ok",
      "budget", s.budget_usd,
      "time", s.time_limit_s,
      "comparator_timeout", s.comparator_timeout_s,
      "container_mem", _container_memory(),
      "key_len", len(s.api_key))
PY

echo "=== run.py begin $(date -Iseconds) ==="
.venv/bin/python run.py \
  --problems "$TMPSET" \
  --out outputs \
  --agent baselines.simple_agent:create_agent
echo "=== run.py end $(date -Iseconds) ==="

# Report latest baseline run under outputs/baseline that has tmp set or newest timestamp
.venv/bin/python - <<'PY'
import json
from pathlib import Path

base = Path("outputs/baseline")
# prefer newest timestamped dir that has p01 result
candidates = sorted(
    [p for p in base.iterdir() if p.is_dir() and p.name[0].isdigit()],
    key=lambda p: p.name,
    reverse=True,
)
if not candidates:
    raise SystemExit("no timestamped baseline runs found")
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
        "actual_cost_usd", "wall_s", "models_used", "failure_reason",
    ):
        if k in r:
            print(f"{k}: {r[k]}")
    if "comparator" in r:
        c = r["comparator"]
        print("comparator.passed", c.get("passed"))
        print("comparator.timed_out", c.get("timed_out"))
        print("comparator.duration_ms", c.get("duration_ms"))
        out = c.get("output") or {}
        if isinstance(out, dict) and out.get("error"):
            print("comparator.error", out.get("error"))
    if "agent_metadata" in r:
        print("agent_metadata", r["agent_metadata"])
else:
    print("missing result")

# cost from events if result cost missing
ev = run / "p01_linear" / "events.jsonl"
if ev.exists():
    cost = 0.0
    n = 0
    for line in ev.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e.get("event") == "llm_response":
            n += 1
            u = (e.get("response") or {}).get("usage") or {}
            cost += float(u.get("cost") or 0)
    print(f"events_llm_calls={n} events_cost_usd={cost}")

ck = run / "p01_linear" / "checkpoint.json"
if ck.exists():
    print("checkpoint", ck.read_text(encoding="utf-8")[:500])
PY

echo "========== E2E END $(date -Iseconds) =========="
