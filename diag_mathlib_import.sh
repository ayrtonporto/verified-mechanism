#!/usr/bin/env bash
# Diagnostic: can Mathlib import finish if we raise the container memory cap?
# The kit hardcodes 5g; this is ONLY a local diagnostic, not a kit patch.
set -euo pipefail
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
cd "$HOME/verified-mechanism/re-takehome-main"
IMAGE=$(.venv/bin/python - <<'PY'
from re_harness.config import HarnessSettings
print(HarnessSettings.from_env(n_workers=1).lean_image)
PY
)
MEM="${1:-8g}"
LOG="$HOME/verified-mechanism/mathlib_import_diag.log"
exec > >(tee -a "$LOG") 2>&1
echo "========== DIAG START $(date -Iseconds) MEM=$MEM =========="
echo "IMAGE=$IMAGE"
free -h

# Match harness protocol: JSON line + blank line terminator.
# Use python to drive stdin so we can time and capture cleanly.
.venv/bin/python - <<PY
import json, subprocess, time, sys
image = ${IMAGE@Q}
mem = ${MEM@Q}
argv = [
    "docker", "run", "--rm", "-i", "--pull=never",
    "--name", "re-diag-mathlib-import",
    "--network=none", "--read-only", "--user", "65532:65532",
    "--cap-drop=ALL", "--security-opt", "no-new-privileges=true",
    "--memory", mem, "--memory-swap", mem,
    "--cpus", "4", "--pids-limit", "512",
    "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g,mode=1777",
    "--tmpfs", "/work:rw,nosuid,nodev,size=1g,mode=1777",
    "-e", "HOME=/tmp", "-w", "/work",
    image, "repl",
]
print("argv=", " ".join(argv), flush=True)
t0 = time.monotonic()
proc = subprocess.Popen(
    argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
payload = (json.dumps({"cmd": "import Mathlib"}) + "\n\n").encode()
try:
    out, err = proc.communicate(payload, timeout=600)
except subprocess.TimeoutExpired:
    proc.kill()
    out, err = proc.communicate()
    print(f"TIMEOUT after {time.monotonic()-t0:.1f}s", flush=True)
    print("stdout_tail:", out[-2000:], flush=True)
    print("stderr_tail:", err[-2000:], flush=True)
    sys.exit(124)
dt = time.monotonic() - t0
print(f"elapsed_s={dt:.1f} returncode={proc.returncode}", flush=True)
print("stdout:", out.decode("utf-8", "replace")[:4000], flush=True)
print("stderr:", err.decode("utf-8", "replace")[:2000], flush=True)
sys.exit(0 if proc.returncode == 0 and out.strip() else 1)
PY
ec=$?
echo "========== DIAG END $(date -Iseconds) exit=$ec =========="
free -h
exit $ec
