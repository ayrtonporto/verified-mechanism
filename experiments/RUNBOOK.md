# How to run science arms (WSL runtime)

**Runtime root:** `~/verified-mechanism/re-takehome-main`  
**Recipe (every Lean/model run):**

```bash
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900
export PYTHONPATH="$HOME/verified-mechanism/re-takehome-main${PYTHONPATH:+:$PYTHONPATH}"
cd ~/verified-mechanism/re-takehome-main
```

`--problems` must be a **set** with `manifest.json` (not a single problem folder).

## Factories

| Arm | `--agent` |
|-----|-----------|
| S-Q | `experiments_agents.s_q:create_agent` |
| S-G | `experiments_agents.s_g:create_agent` |
| R-Q | `experiments_agents.r_q:create_agent` |
| R-G | `experiments_agents.r_g:create_agent` |
| H-QG | `experiments_agents.h_qg:create_agent` |
| H-GQ | `experiments_agents.h_gq:create_agent` |

Outputs land under `outputs/<module_tail>/<timestamp>/`  
(e.g. `outputs/s_g/2026...Z/`).

**Preferred runtime (2026-08-25):** Windows native — see `WINDOWS_RUNTIME.md` (smoke pending).  
**Fallback:** WSL with session kept alive for full wall time (`run_p01_sg_calib.sh`).

## Env knobs

| Arm family | Vars |
|------------|------|
| S | `BASELINE_MAX_TURNS` (default 25), `BASELINE_MAX_TOKENS`, `BASELINE_TEMPERATURE` |
| R/H | `REPAIR_MAX_PROPOSE_TURNS` (1), `REPAIR_MAX_REPAIR_TURNS` (3), `REPAIR_MAX_TOKENS`, `REPAIR_TEMPERATURE` |

## Example: S-G calib on p01

```bash
bash /home/ayrton/verified-mechanism/run_p01_sg_calib.sh
# from Windows:
# wsl.exe -d Ubuntu-22.04 -- bash /home/ayrton/verified-mechanism/run_p01_sg_calib.sh
```

## Example: generic one-arm run on a set

```bash
export BASELINE_MAX_TURNS=8   # pilot
.venv/bin/python run.py \
  --problems /path/to/set_with_manifest \
  --out outputs \
  --agent experiments_agents.s_q:create_agent
```

## Materialized split sets (frozen membership; SPLIT.md still `proposed`)

Built from `experiments/SPLIT.md` by copying member problem folders + a filtered
manifest. Validated with `re_harness.manifest.load_problem_set`. Use **relative**
paths from the runtime root (`re-takehome-main/`) so they work on any host:

| Set | Path (`--problems`) | n |
|-----|---------------------|--:|
| Calib | `sets/calib` | 1 |
| S_dev | `sets/S_dev` | 9 |
| S_eval | `sets/S_eval` | 7 |

```bash
# example: S-Q over S_dev (from runtime root), one arm at a time
.venv/bin/python run.py \
  --problems sets/S_dev \
  --out outputs \
  --agent experiments_agents.s_q:create_agent
```

Membership is frozen against reshuffling (SPLIT.md rule); do not run `S_eval`
until S→R→H on `S_dev` is measured and the split is `accepted`.

## submission/agent.py

Still a stub. Science arms are **not** wired as the default submission agent.
