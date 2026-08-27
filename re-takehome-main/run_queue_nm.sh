#!/usr/bin/env bash
# Unattended queue for the 2-3h window. Single Lean worker → strictly sequential.
set -uo pipefail
cd ~/Documentos/verified-mechanism/re-takehome-main
export LEAN_CONTAINER_MEMORY=8g N_WORKERS=1 VM_BUDGET_USD=10.00 \
       COMPARATOR_TIMEOUT_S=900 LEAN_CHECK_TIMEOUT_S=300 PYTHONUNBUFFERED=1 \
       REPAIR_MAX_REPAIR_TURNS=4

log(){ echo "[$(date -u +%FT%TZ)] $*"; }

# wait until any prior fastdrive run releases the Lean worker
log "waiting for worker to be free..."
while pgrep -f "fastdrive.py" >/dev/null 2>&1; do sleep 30; done
log "worker free — starting queue"

# Q1: NMBANK-PF (lemma bank, plan->formalize proposer) on the 3 hard ×3.
#     Best-odds legitimate p09 attempt: PF-GQ produced p09_b's deep prefix; the bank
#     hands p09_b's verified periodicity have to p09_a; NearMiss finishes.
log "=== Q1 NMBANK-PF hard3 x3 START ==="
.venv/bin/python fastdrive.py --problems sets/mt_sf_hard \
  --agent experiments_agents.nmbank_pf:create_agent --repeat 3 \
  --out outputs_fast/nmbank_pf_hard3 > queue_q1_nmbank_pf.out 2>&1
log "=== Q1 END (see queue_q1_nmbank_pf.out) ==="

# Q2: NMBANK-G (G tactic proposer) on the 3 hard ×3 — a second diverse proposer.
log "=== Q2 NMBANK-G hard3 x3 START ==="
.venv/bin/python fastdrive.py --problems sets/mt_sf_hard \
  --agent experiments_agents.nmbank_g:create_agent --repeat 3 \
  --out outputs_fast/nmbank_g_hard3 > queue_q2_nmbank_g.out 2>&1
log "=== Q2 END (see queue_q2_nmbank_g.out) ==="

# Q3: MT-NM-G on full S_dev ×3 — regression + variance + hard retry.
log "=== Q3 MT-NM-G S_dev x3 START ==="
.venv/bin/python fastdrive.py --problems sets/S_dev \
  --agent experiments_agents.mt_nm_g:create_agent --repeat 3 \
  --out outputs_fast/mtnm_sdev > queue_q3_mtnm_sdev.out 2>&1
log "=== Q3 END (see queue_q3_mtnm_sdev.out) ==="

log "QUEUE_DONE"
