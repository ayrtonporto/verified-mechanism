#!/usr/bin/env bash
# Heavy per-theorem sampling on the two remaining hard problems.
set -uo pipefail
cd ~/Documentos/verified-mechanism/re-takehome-main
export LEAN_CONTAINER_MEMORY=8g N_WORKERS=1 VM_BUDGET_USD=1.00 \
       COMPARATOR_TIMEOUT_S=900 LEAN_CHECK_TIMEOUT_S=300 PYTHONUNBUFFERED=1 \
       REPAIR_TEMPERATURE=0.9 REPAIR_MAX_REPAIR_TURNS=4
log(){ echo "[$(date -u +%FT%TZ)] $*"; }

while pgrep -f "multisample_combine.py|fastdrive.py" >/dev/null 2>&1; do sleep 20; done

log "=== rmo_2000_2 N=16 START ==="
.venv/bin/python multisample_combine.py --set sets/mt_sf_hard --id rmo_2000_2 \
  --agent experiments_agents.nm_pf:create_agent --n 16 \
  --out outputs_fast/msc_rmo2 > msc_rmo2.out 2>&1
log "=== rmo_2000_2 END ==="

log "=== rmo_2000_3 N=16 START ==="
.venv/bin/python multisample_combine.py --set sets/mt_sf_hard --id rmo_2000_3 \
  --agent experiments_agents.nm_pf:create_agent --n 16 \
  --out outputs_fast/msc_rmo3 > msc_rmo3.out 2>&1
log "=== rmo_2000_3 END ==="
log "RMO_QUEUE_DONE"
