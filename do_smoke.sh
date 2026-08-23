#!/usr/bin/env bash
# Smoke with cold-start-friendly local overrides (local only).
set -euo pipefail
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
# First Mathlib/comparator cold build on this box can exceed the 180s default.
export COMPARATOR_TIMEOUT_S="${COMPARATOR_TIMEOUT_S:-900}"
export LEAN_CHECK_TIMEOUT_S="${LEAN_CHECK_TIMEOUT_S:-300}"
# 5g kit default thrashs Mathlib import on this laptop; 8g finishes in ~44s.
export LEAN_CONTAINER_MEMORY="${LEAN_CONTAINER_MEMORY:-8g}"
cd "$HOME/verified-mechanism/re-takehome-main"
LOG="$HOME/verified-mechanism/smoke_run.log"
exec > >(tee -a "$LOG") 2>&1

echo "========== SMOKE START $(date -Iseconds) =========="
echo "cwd=$(pwd)"
echo "COMPARATOR_TIMEOUT_S=$COMPARATOR_TIMEOUT_S LEAN_CHECK_TIMEOUT_S=$LEAN_CHECK_TIMEOUT_S LEAN_CONTAINER_MEMORY=$LEAN_CONTAINER_MEMORY"
free -h
bash scripts/smoke_test.sh
echo "========== SMOKE OK $(date -Iseconds) =========="
free -h
