#!/usr/bin/env bash
# Windows Python harness + docker.exe (D:\Docker\bin) → WSL engine via TCP.
# All on D:. Avoid MSYS /d/... paths when calling Win32 python.
set -euo pipefail

export PATH="/usr/bin:/bin:/d/Docker/bin:/c/Windows/System32:/c/Windows:/c/Program Files/Git/usr/bin:/c/Program Files/Git/mingw64/bin:/c/Program Files/Git/cmd"
export MSYS2_ARG_CONV_EXCL='*'
export UV_CACHE_DIR='D:\Python\uv-cache'
export UV_PYTHON_INSTALL_DIR='D:\Python\uv-python'
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900
export LEAN_CHECK_TIMEOUT_S=300
export BASELINE_MAX_TURNS=3
export BASELINE_MODEL=openai/gpt-oss-120b

# Windows paths for Win32 python
WIN_ROOT='D:\Mis documentos\Documentos\Verified Mechanism'
WIN_KIT="$WIN_ROOT\re-takehome-main"
WIN_TMP="$WIN_ROOT\tmp-p01-set-win"
WIN_LOG="$WIN_ROOT\run_p01_sg_win_smoke.log"
WIN_PY="$WIN_KIT\.venv\Scripts\python.exe"

# bash paths for file ops
BASH_ROOT="/d/Mis documentos/Documentos/Verified Mechanism"
BASH_KIT="$BASH_ROOT/re-takehome-main"
BASH_TMP="$BASH_ROOT/tmp-p01-set-win"

cd "$BASH_KIT"
export PYTHONPATH="$WIN_KIT"

WSL_IP=$(wsl.exe -d Ubuntu-22.04 -- hostname -I | awk '{print $1}' | tr -d '\r')
export DOCKER_HOST="tcp://${WSL_IP}:2375"

if ! docker.exe version >/dev/null 2>&1; then
  wsl.exe -d Ubuntu-22.04 -- bash -c 'pgrep -f "socat TCP-LISTEN:2375" >/dev/null || socat TCP-LISTEN:2375,bind=0.0.0.0,reuseaddr,fork UNIX-CONNECT:/var/run/docker.sock >/tmp/docker-tcp-proxy.log 2>&1 & sleep 1'
  sleep 1
fi

exec >"$BASH_ROOT/run_p01_sg_win_smoke.log" 2>&1

echo "========== WIN SMOKE START $(date -Iseconds 2>/dev/null || date) =========="
echo "DOCKER_HOST=$DOCKER_HOST"
echo "WIN_KIT=$WIN_KIT"
"$WIN_PY" -c "import sys; print(sys.executable)"
docker.exe version
echo "---"

rm -rf "$BASH_TMP"
mkdir -p "$BASH_TMP/p01_linear"
cp sample-problems/p01_linear/problem.md sample-problems/p01_linear/challenge.lean "$BASH_TMP/p01_linear/"
cat > "$BASH_TMP/manifest.json" <<'EOF'
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
ls -la "$BASH_TMP" "$BASH_TMP/manifest.json"

export PATH="/d/Docker/bin:/c/Windows/System32:/c/Windows"
export PYTHONPATH="$WIN_KIT"

"$WIN_PY" - <<'PY'
import os, shutil, subprocess
from pathlib import Path
os.chdir(r"D:\Mis documentos\Documentos\Verified Mechanism\re-takehome-main")
from dotenv import load_dotenv
load_dotenv(Path('.env'), override=True)
os.environ['LEAN_CONTAINER_MEMORY']='8g'
os.environ['COMPARATOR_TIMEOUT_S']='900'
assert shutil.which('docker'), 'docker not on PATH'
r=subprocess.run(['docker','version'], capture_output=True, text=True, timeout=30)
assert r.returncode==0, (r.stdout, r.stderr)
from re_harness.config import HarnessSettings
from re_harness.lean import _container_memory
from experiments_agents.s_g import create_agent
s=HarnessSettings.from_env(n_workers=1)
assert s.api_key.startswith('sk-')
assert _container_memory()=='8g'
a=create_agent()
print('preflight_ok', a.arm, a.model, 'docker_host', os.environ.get('DOCKER_HOST'))
print('tmp_exists', Path(r"D:\Mis documentos\Documentos\Verified Mechanism\tmp-p01-set-win\manifest.json").exists())
PY

echo "=== run.py begin ==="
"$WIN_PY" run.py \
  --problems "$WIN_TMP" \
  --out outputs \
  --agent experiments_agents.s_g:create_agent
echo "=== run.py end ==="

"$WIN_PY" - <<'PY'
import json
from pathlib import Path
base = Path(r"D:\Mis documentos\Documentos\Verified Mechanism\re-takehome-main\outputs\s_g")
runs=sorted([p for p in base.iterdir() if p.is_dir() and (p/'summary.json').exists()], key=lambda p:p.name, reverse=True)
run=runs[0]
print('RUNDIR', run)
s=json.loads((run/'summary.json').read_text(encoding='utf-8'))
print('points', s.get('total_points'), '/', s.get('max_points'))
print('actual_cost_usd', s.get('actual_cost_usd'))
print('wall_s', s.get('wall_s'))
for p in s.get('problems', []):
    print(p)
r=json.loads((run/'p01_linear'/'result.json').read_text(encoding='utf-8'))
print('status', r.get('status'), 'passed', r.get('passed'))
print('spent', (r.get('budget') or {}).get('spent_usd'))
print('comparator', (r.get('comparator') or {}).get('passed'))
print('meta', r.get('agent_metadata'))
print('platform', 'windows_python + docker.exe + WSL engine TCP')
PY
echo "========== WIN SMOKE END $(date -Iseconds 2>/dev/null || date) =========="
