# HANDOFF

## Read first

1. **`PROJECT_STATE.md` §17** — RUNTIME RESOLVED: where to run and why (the important part).
2. `PROJECT_STATE.md` §14–16 — status, frozen plan, science arms.
3. `design/COORDINATION_PLAN.md` — frozen science plan (S / R / H).
4. `experiments/RUNBOOK.md` + `BASELINE_SEMANTICS.md` + `REGISTRY.md`.
5. `SETUP_BLOCKERS.md` — note: its "Production path: WSL" is **superseded** by §17 (see below).
6. Baseline: `re-takehome-main/baselines/simple_agent.py`.

Do not paste API keys in chat. The key lives only in gitignored `.env` files.

---

## Current phase (2026-08-25)

**Phase 0–1 science layer: DONE** (coordination plan frozen; six arms invokable; twin calib green).
**`submission/agent.py` still stub** (no final adaptive scorer yet).

**RUNTIME RESOLVED — this is the change since the last handoff:**

> Run all paid Lean jobs on **`sshrun` (always-on Linux) over SSH, inside `tmux`.**
> WSL is abandoned for runs (session-kill); Windows-native Desktop rejected (engine crash). No cloud.

Full detail + evidence: **`PROJECT_STATE.md` §17.**

---

## Where to run and WHY (one screen)

| Runtime | Verdict | Why |
|---|---|---|
| **`sshrun` + SSH + tmux** | ✅ **PRODUCTION** | Jobs survive client disconnect. p01 passed end-to-end. Reliable. |
| WSL Ubuntu (attached) | ❌ for agent-driven runs | **Session-kill**: VM tears down when the launching client exits → job dies mid-run with free RAM (not OOM). Exit 127 / `0x80072746`. |
| Windows Docker Desktop | ❌ | Engine crashes on the large Lean image (15 GB host). |

**`sshrun` is slow (2011 CPU, ~5 min/p01) but that is fine:** 8 h/problem cap ≫ wall time → no false
timeouts → results valid. Matrix = one overnight unattended tmux run.

---

## sshrun quickstart

```text
ssh usuario@sshrun            # Tailscale, key auth, passwordless sudo
repo:  ~/Documentos/verified-mechanism   (kit under re-takehome-main, .venv OK, py3.12, no pyshim)
image: re-takehome-lean pulled, health OK
.env:  key + N_WORKERS=1 + VM_BUDGET_USD=1.00 + VM_TIME_LIMIT_S=28800
tmux 3.4 installed ; disk freed (deleted 2 Timeshift btrfs snapshots — watch disk before big pulls)
```

Run pattern (survives disconnect):

```bash
# 1) sync repo (git pull needs a token — `gh auth token` on the Windows side)
# 2) adapt an arm script from WSL paths to sshrun paths:
#    /home/ayrton/verified-mechanism -> /home/usuario/Documentos/verified-mechanism
#    drop the "/home/ayrton/.pyshim:/home/ayrton/.local/bin:" PATH prefix
# 3) launch in tmux, poll the log for a DONE marker:
tmux new-session -d -s ARM "PYTHONUNBUFFERED=1 bash run_ARM_sshrun.sh; echo DONE_\$? >> run_ARM.log"
```

Env recipe (already baked into the arm scripts): `LEAN_CONTAINER_MEMORY=8g`,
`COMPARATOR_TIMEOUT_S=900`, `LEAN_CHECK_TIMEOUT_S=300`, `N_WORKERS=1`.

---

## Validated

| id | result | usd | wall | where |
|----|--------|-----|------|-------|
| p01 Qwen baseline (S-Q) | **pass 1/1** | 0.00017 | ~4.7 min | `sshrun` `outputs/baseline/<ts>/` (2026-08-25) |
| CAL-Q-p01 (prior, WSL) | pass | 0.000177 | — | `20260824T040147Z` |
| CAL-G-p01 (prior, WSL) | pass | 0.000075 | — | `s_g/20260825T041102Z` |

---

## Immediate next actions (a fresh chat starts here)

1. `git pull` on `sshrun` to sync latest arm scripts.
2. Freeze `S_dev` / `S_eval` (`experiments/SPLIT.md` still unset).
3. Adapt + run **S-Q** and **S-G** on `S_dev` on `sshrun`, in tmux, **one arm at a time**; log rows in
   `experiments/REGISTRY.md`. Then **R**, then **H**.
4. Respect `SPEND_PLAN.md`. No full matrix, no blackboard/debate, no final adaptive agent until the
   split is frozen and core S→R→H is measured.

---

## Arms

`re-takehome-main/experiments_agents/` → `s_q` `s_g` `r_q` `r_g` `h_qg` `h_gq`
(via `run.py --agent module:factory`). S = kit `simple_agent` multi-turn Lean loop;
R = explicit propose/repair with diagnostics; H = R with the other repair model. See §15 / plan.

---

## Thesis

S / R / H science unchanged. Measure under matched budgets; Solo Union derived; log confounders.
