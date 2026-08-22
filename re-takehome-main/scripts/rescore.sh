#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test $# -ge 1 || { echo "Usage: $0 RUN_DIR [N_WORKERS]" >&2; exit 2; }
OUT=$1
N_WORKERS=${2:-1}
.venv/bin/python -m re_harness.evaluator \
  --problems sample-problems --out "$OUT" --n-workers "$N_WORKERS"
