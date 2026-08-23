#!/usr/bin/env bash
# One-shot WSL setup for the RE take-home kit. Run inside Ubuntu-22.04.
set -euo pipefail
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
cd "$HOME/verified-mechanism/re-takehome-main"
LOG="$HOME/verified-mechanism/setup_run.log"
exec > >(tee -a "$LOG") 2>&1

echo "========== SETUP START $(date -Iseconds) =========="
echo "cwd=$(pwd)"
echo "HOME=$HOME"
echo "python=$(python3 --version) $(which python3)"
echo "venv_python=$PWD/.venv/bin/python"
"$PWD/.venv/bin/python" --version
free -h
docker stop avid-server 2>/dev/null || true

IMAGE=$("$PWD/.venv/bin/python" - <<'PY'
from re_harness.config import HarnessSettings
print(HarnessSettings.from_env(n_workers=1).lean_image)
PY
)
echo "TARGET=$IMAGE"
if [ -z "$IMAGE" ]; then
  echo "FATAL: empty image ref" >&2
  exit 2
fi

echo "--- docker pull begin $(date -Iseconds) ---"
docker pull "$IMAGE"
echo "--- docker pull end $(date -Iseconds) ---"

echo "--- health begin $(date -Iseconds) ---"
docker run --rm --network=none --read-only --user 65532:65532 \
  --cap-drop=ALL --security-opt no-new-privileges=true \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m,mode=1777 \
  --tmpfs /work:rw,nosuid,nodev,size=64m,mode=1777 \
  "$IMAGE" health
echo "--- health end $(date -Iseconds) ---"

"$PWD/.venv/bin/python" -m pip install --quiet --upgrade pip
"$PWD/.venv/bin/python" -m pip install --quiet -e .

if [ ! -f .env ]; then
  echo "Next: cp .env.example .env and add the OpenRouter key."
fi
echo "========== SETUP OK $(date -Iseconds) =========="
docker images --digests | head -15
free -h
