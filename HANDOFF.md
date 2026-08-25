# HANDOFF

## Read first

1. `design/COORDINATION_PLAN.md` — frozen science plan
2. `PROJECT_STATE.md` (§13–16: Phase 0–1 done, Windows runtime pivot)
3. `experiments/RUNBOOK.md` + `experiments/BASELINE_SEMANTICS.md`
4. `SETUP_BLOCKERS.md` + `WINDOWS_RUNTIME.md` (native Windows path)
5. `re-takehome-main/docs/AGENT_API.md` + `RULES.md`
6. Baseline: `re-takehome-main/baselines/simple_agent.py`

Do not invent execution constraints. Do not paste API keys.

---

## Current phase (2026-08-25)

**Phase 0–1 DONE.** Science arms implemented. Twin calib green.  
**Next:** freeze `S_dev`/`S_eval` → S-Q/S-G on S_dev → R → H.  
**Runtime pivot:** move paid Lean/model runs to **Windows native** (Docker Desktop) to avoid WSL session kills; WSL remains fallback.

`submission/agent.py` still stub (no final adaptive scorer).

---

## What is true right now

### Code / science layer

| Path | Role |
|------|------|
| `experiments/` | REGISTRY, SPEND_PLAN, SPLIT (unset), BASELINE_SEMANTICS, master_matrix, RUNBOOK |
| `re-takehome-main/experiments_agents/` | Factories S-Q/S-G/R-Q/R-G/H-QG/H-GQ |
| `design/COORDINATION_PLAN.md` | Authority for arms S/R/H |
| `design/BUILDER_BRIEF.md` | Builder mission (done for Phase 0–1) |

**S** = kit `simple_agent` multi-turn Lean loop (baseline-faithful).  
**R** = explicit targeted repair (same model).  
**H** = R with other model on repair only.

### Calibrations (paid, local recipe 8g + 900s)

| id | arm | pass | usd | wall | path |
|----|-----|------|-----|------|------|
| CAL-Q-p01 | S-Q kit | 1/1 | $0.00017719 | ~192s | WSL `outputs/baseline/20260824T040147Z/` |
| CAL-G-p01 | S-G factory | 1/1 | $0.00007538 | ~193s | `outputs/s_g/20260825T041102Z/` (WSL + Windows copy) |

Spend logged ~$0.00025 of ~$50. Split **not frozen**.

### Environment

| | Status |
|--|--------|
| Git SoT | Windows `D:\Mis documentos\Documentos\Verified Mechanism` → `github.com/ayrtonporto/verified-mechanism` |
| WSL runtime | Still works; session/tooling flaky for long jobs when launcher disconnects |
| **Target runtime** | **Windows native** + Docker Desktop (see `WINDOWS_RUNTIME.md`) — smoke pending |
| Key | Prefer gitignored `.env` next to kit; **never commit**. Historically WSL-only; copy carefully for Windows |
| Lean local | `LEAN_CONTAINER_MEMORY=8g`, `COMPARATOR_TIMEOUT_S=900` |

### Kit local touch (before submit)

- `re-takehome-main/src/re_harness/lean.py`: env `LEAN_CONTAINER_MEMORY` (default still `5g`)

---

## How to run arms

```text
# After Windows runtime is green (preferred):
cd <kit>
set LEAN_CONTAINER_MEMORY=8g
set COMPARATOR_TIMEOUT_S=900
set PYTHONPATH=%CD%
.venv\Scripts\python run.py --problems <set_with_manifest> --out outputs --agent experiments_agents.s_g:create_agent
```

Factories: `experiments_agents.{s_q,s_g,r_q,r_g,h_qg,h_gq}:create_agent`  
Detail: `experiments/RUNBOOK.md`

WSL fallback (keep session alive full job):

```bash
wsl.exe -d Ubuntu-22.04 -- bash /home/ayrton/verified-mechanism/run_p01_sg_calib.sh
```

---

## Immediate next actions

1. **Windows runtime smoke:** Docker Desktop + kit venv + `.env` + Lean image + one p01 run (prove native path).
2. Freeze `S_dev` / `S_eval` (`design/SPLIT_AGENT_BRIEF.md`).
3. With spend OK: S-Q + S-G on S_dev (pilot caps e.g. turns=8).
4. R-Q/R-G then H-QG/H-GQ matched.
5. No blackboard / debate / final adaptive agent until core matrix exists.

---

## Do not do yet

- Full 16×6 matrix without SPEND_PLAN line + OK
- Blackboard / multi-agent debate / RAG
- Claiming cross-model wins without R controls
- Pasting API keys
- Silent kit default changes before grade submit

---

## Thesis

Small Lean-gated repair is the coordination object.  
Separate **base skill (S)** vs **repair method (R)** vs **cross-model handoff (H)**.  
Solo Union = derived, not a run.
