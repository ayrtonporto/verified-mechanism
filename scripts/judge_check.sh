#!/usr/bin/env bash
# Run the applicant's default agent under the same one-problem contract as judging.
set -euo pipefail
cd "$(dirname "$0")/.."
test -x .venv/bin/python || { echo "Run bash scripts/setup.sh first." >&2; exit 1; }
.venv/bin/python - <<'PY'
from re_harness.config import HarnessSettings
if not HarnessSettings.from_env(n_workers=1).api_key:
    raise SystemExit("Set OPENROUTER_API_KEY in .env or the environment")
PY

WORK=$(mktemp -d "${TMPDIR:-/tmp}/re-takehome-judge.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/problems/p01_linear" "$WORK/outputs"
cp sample-problems/p01_linear/problem.md sample-problems/p01_linear/challenge.lean \
  "$WORK/problems/p01_linear/"
.venv/bin/python - "$WORK/problems/manifest.json" <<'PY'
import json, sys
from pathlib import Path
source = json.loads(Path("sample-problems/manifest.json").read_text())
source["set"] = "judge-check"
source["problems"] = [p for p in source["problems"] if p["id"] == "p01_linear"]
Path(sys.argv[1]).write_text(json.dumps(source, indent=2) + "\n")
PY

VM_TIME_LIMIT_S=28800 VM_BUDGET_USD=1.00 .venv/bin/python run.py \
  --problems "$WORK/problems" --out "$WORK/outputs" --n-workers 1

.venv/bin/python - "$WORK/outputs" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
candidates = sorted((root / "submission").glob("*"))
if len(candidates) != 1 or not candidates[0].is_dir():
    raise SystemExit(f"Expected exactly one timestamped submission run under {root}")
out = candidates[0]
required = [
    out / "run.json", out / "summary.json",
    out / "p01_linear" / "solution.lean",
    out / "p01_linear" / "result.json",
    out / "p01_linear" / "transcript.json",
    out / "p01_linear" / "events.jsonl",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit("Missing contract artifacts: " + ", ".join(missing))
result = json.loads((out / "p01_linear" / "result.json").read_text())
transcript = json.loads((out / "p01_linear" / "transcript.json").read_text())
assert isinstance(transcript.get("calls"), list), "transcript calls must be a list"
assert result.get("passed") is True, f"p01 did not pass: {result.get('status')}"
print(f"judge_check PASSED: {out}")
PY
