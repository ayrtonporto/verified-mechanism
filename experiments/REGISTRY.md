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
| SQ-Sdev | 2026-08-25 | f5d84e8 | S-Q | S_dev | 2/9 | 0.075662145 | 58 | 0 | 58 | 2524.309s | sshrun `outputs/s_q/20260825T164554Z/` | **SUPERSEDED by Mx-SQ-Sdev** (pre-fix kit, `allow_fallbacks:False`). First frozen-split arm. Passes both E (p01,p03); all M/H `build failed`. run_id 5ddf01bc. |
| Mx-SQ-Sdev | 2026-08-26 | 7baca49 | S-Q | S_dev | 3/9 | 0.06814 | — | 0 | 53 | 2629s | sshrun `outputs/s_q/20260826T002548Z/` | Fixed-kit matrix. Pass: p01,p03,p06. run_id a526dc71. |
| Mx-SG-Sdev | 2026-08-26 | 7baca49 | S-G | S_dev | 4/9 | 0.08868 | 0 | — | 47 | 9730s | sshrun `outputs/s_g/20260826T010943Z/` | Fixed-kit; provider fallback routed GPT-OSS off busy AkashML → CoreWeave, 0×429. Pass: p01,p03,p05,putnam_2018_a1. run_id 49eb7ecd. |
| Mx-RQ-Sdev | 2026-08-26 | 7baca49 | R-Q | S_dev | 4/9 | 0.05630 | — | 0 | 26 | 2265s | sshrun `outputs/r_q/20260826T035159Z/` | Repair +1 vs S-Q; unlocks p10. Pass: p01,p03,p06,p10. run_id 8b5e4381. |
| Mx-RG-Sdev | 2026-08-26 | 7baca49 | R-G | S_dev | 5/9 | 0.05023 | 0 | — | 23 | 4877s | sshrun `outputs/r_g/20260826T042950Z/` | Best single arm; repair +1 vs S-G, unlocks p10. Pass: p01,p03,p05,p10,putnam_2018_a1. run_id ce1263ce. |
| Mx-HQG-Sdev | 2026-08-26 | 7baca49 | H-QG | S_dev | 4/9 | 0.02537 | — | — | 20 | 3245s | sshrun `outputs/h_qg/20260826T055113Z/` | Qwen propose → GPT-OSS repair. Pass: p01,p03,p06,putnam_2018_a1. run_id 8bb8c28a. |
| Mx-HGQ-Sdev | 2026-08-26 | 7baca49 | H-GQ | S_dev | 3/9 | 0.04444 | — | — | 23 | 3071s | sshrun `outputs/h_gq/20260826T064523Z/` | GPT-OSS propose → Qwen repair. Pass: p01,p03,putnam_2018_a1. run_id 981c4a7e. |

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
