# Experiment registry

One row per **run** (one agent arm × one problem set × one timestamped harness output).

**How to fill USD:** `summary.json` → `actual_cost_usd` (from OpenRouter `usage.cost`).  
**calls_q / calls_g:** `agent_metadata` or count `llm_request` in `events.jsonl`.  
**lean_checks:** `agent_metadata.lean_checks` or Lean events.  
**wall:** `summary.json` → `wall_s`.  
**git:** short SHA of Windows SoT at run start.

| id | date | git | arm | set | pass_count | usd | calls_q | calls_g | lean_checks | wall | output_path | note |
|----|------|-----|-----|-----|------------|-----|---------|---------|-------------|------|-------------|------|
| CAL-Q-p01 | 2026-08-24 | 677c1a1 | S-Q (kit baseline) | tmp_p01_only | 1/1 | 0.00017719 | 1 | 0 | 1 | 191.97s | WSL `re-takehome-main/outputs/baseline/20260824T040147Z/` | Canonical local recipe: 8g + 900s comparator; `BASELINE_MAX_TURNS=3`; Qwen; passed REPL+comparator. Still valid reference. |
| CAL-G-p01 | 2026-08-25 | 677c1a1+dirty | S-G | tmp_p01_only | 1/1 | 0.00007538 | 0 | 1 | 1 | 193.11s | WSL `re-takehome-main/outputs/s_g/20260825T041102Z/` | Twin calib: `experiments_agents.s_g:create_agent`; recipe 8g+900s; `BASELINE_MAX_TURNS=3`; 1 turn; comparator passed. Tree had uncommitted Phase0/1 work. |
| CAL-G-p01-win | 2026-08-25 | e177389+ | S-G | tmp_p01_only | 0/1 harness_error | 0.00009 | 0 | 1 | — | 221s | `outputs/s_g/20260825T051130Z/` | Windows Python + D:\Docker\bin\docker.exe + WSL TCP :2375. LLM OK; Lean REPL WinError 10038; comparator TCP timeout. **Not green.** Docker Desktop blocked by C: free space (~3.2GB < 3.5GB). |
| SQ-Sdev | 2026-08-25 | f5d84e8 | S-Q | S_dev | 2/9 | 0.075662145 | 58 | 0 | 58 | 2524.309s | sshrun `outputs/s_q/20260825T164554Z/` | First frozen-split arm. Ran on sshrun (harness code 5ae617f + sets scp'd from f5d84e8); caps `BASELINE_MAX_TURNS=8`, `VM_BUDGET_USD=0.15/prob`, 8g/900s. Passes both E (p01,p03); all M/H fail with `build failed` (model solution non-compiling — legit, not harness error). ~6.4 turns/prob avg. run_id 5ddf01bc. |

## Legend

| arm | factory |
|-----|---------|
| S-Q | `experiments_agents.s_q:create_agent` |
| S-G | `experiments_agents.s_g:create_agent` |
| R-Q | `experiments_agents.r_q:create_agent` |
| R-G | `experiments_agents.r_g:create_agent` |
| H-QG | `experiments_agents.h_qg:create_agent` |
| H-GQ | `experiments_agents.h_gq:create_agent` |

Kit-faithful alternate for S: `baselines.simple_agent:create_agent` + `BASELINE_MODEL=...`.
