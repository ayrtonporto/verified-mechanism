# HANDOFF

## Read first

1. `design/COORDINATION_PLAN.md` — frozen science plan  
2. `PROJECT_STATE.md` (§13–16)  
3. `WINDOWS_RUNTIME.md` — **read status carefully** (partial)  
4. `experiments/RUNBOOK.md` + `BASELINE_SEMANTICS.md`  
5. `SETUP_BLOCKERS.md`  
6. Baseline: `re-takehome-main/baselines/simple_agent.py`

Do not paste API keys. Prefer installs on **D:** only.

---

## Current phase (2026-08-25)

**Phase 0–1 science layer: DONE** (arms + registry + twin calib WSL).  
**Windows runtime: PARTIAL** — toolchains on D:; Lean path via Windows `docker.exe` **not green**.  
**Production runs:** keep **WSL attached** until Docker Desktop can install to D: (needs free space on **C:** for installer check).

`submission/agent.py` still stub.

---

## Runtime truth

| Path | Lean/comparator | Notes |
|------|-----------------|-------|
| **WSL full** (`wsl … bash script`, session alive) | **Green** | CAL-Q + CAL-G p01 |
| Windows Python + `D:\Docker\bin\docker.exe` + WSL TCP :2375 | **Red** | LLM OK; REPL `WinError 10038`; comparator TCP timeout (`20260825T051130Z`) |
| Docker Desktop native | **Not installed** | Installer: need 3459 MiB, C: has ~3230 MiB |

On D: already: uv Python 3.11, kit `.venv`, `.env`, `docker.exe`, WSL/docker data.

---

## Calibrations

| id | result | usd | path |
|----|--------|-----|------|
| CAL-Q-p01 | pass | 0.000177 | WSL baseline `20260824T040147Z` |
| CAL-G-p01 | pass | 0.000075 | WSL/Windows copy `s_g/20260825T041102Z` |
| CAL-G-p01-win | **harness_error** | 0.00009 | `s_g/20260825T051130Z` |

---

## Immediate next actions

1. Free **≥4 GB on C:** (or user moves TEMP) → install Docker Desktop under **`D:\Docker\DockerDesktop`**.  
2. Re-smoke S-G p01 with Desktop engine (no socat).  
3. Freeze `S_dev`/`S_eval`; run solos under spend OK.  
4. Until 1–2: use WSL attached for all paid Lean batches.

---

## Commands that work today

```bash
# WSL production calib / batches
wsl.exe -d Ubuntu-22.04 -- bash /home/ayrton/verified-mechanism/run_p01_sg_calib.sh
```

```powershell
# Windows preflight only (no Lean guarantee)
$env:PATH = "D:\Docker\bin;$env:PATH"
cd "D:\Mis documentos\Documentos\Verified Mechanism\re-takehome-main"
.\.venv\Scripts\python.exe -c "from experiments_agents.s_g import create_agent; print(create_agent().arm)"
```

---

## Kit Windows patches (local)

- `runner.py`: skip missing signals (SIGHUP)  
- `artifacts.py`: `fchmod` fallback on Windows  

---

## Thesis

S / R / H science unchanged. Measure under matched budgets; Solo Union derived.
