#!/usr/bin/env bash
# No API key required: health-check the image and verify a known proof.
set -euo pipefail
cd "$(dirname "$0")/.."
test -x .venv/bin/python || { echo "Run bash scripts/setup.sh first." >&2; exit 1; }
.venv/bin/python -m re_harness.smoke --problems sample-problems

