#!/usr/bin/env bash
# Unattended queue for the 2-3h window. Single Lean worker → strictly sequential.
# Waits for the current p09 run to free the worker, then runs two high-value jobs.
set -uo pipefail
cd ~/Documentos/verified-mechanism/re-takehome-main
export LEAN_CONTAINER_MEMORY=8g N_WORKERS=1 VM_BUDGET_USD=10.00 \
       COMPARATOR_TIMEOUT_S=900 LEAN_CHECK_TIMEOUT_S=300 PYTHONUNBUFFERED=1 \
       REPAIR_MAX_REPAIR_TURNS=4

log(){ echo "[$(date -u +%FT%TZ)] $*"; }

# 1) wait until the current mt_p09 fastdrive run releases the Lean worker
log "waiting for current p09 run to finish..."
while pgrep -f "fastdrive.py --problems sets/mt_p09" >/dev/null 2>&1; do sleep 30; done
log "worker free — starting queue"

# Q1: NMBANK-G (lemma-bank) on the 3 hard problems ×3 — the legitimate p09 attempt
log "=== Q1 NMBANK-G hard3 x3 START ==="
.venv/bin/python fastdrive.py --problems sets/mt_sf_hard \
  --agent experiments_agents.nmbank_g:create_agent --repeat 3 \
  --out outputs_fast/nmbank_hard3 > queue_q1_nmbank_hard3.out 2>&1
log "=== Q1 END (see queue_q1_nmbank_hard3.out) ==="

# Q2: MT-NM-G on full S_dev ×3 — regression + variance + hard retry with NearMiss
log "=== Q2 MT-NM-G S_dev x3 START ==="
.venv/bin/python fastdrive.py --problems sets/S_dev \
  --agent experiments_agents.mt_nm_g:create_agent --repeat 3 \
  --out outputs_fast/mtnm_sdev > queue_q2_mtnm_sdev.out 2>&1
log "=== Q2 END (see queue_q2_mtnm_sdev.out) ==="

log "QUEUE_DONE"
