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

## Current phase (2026-08-26)

**S_dev matrix DONE** (all 6 arms, fixed kit, 0 rate-limit errors). Split **accepted**.
Results in `experiments/tables/master_matrix.md` + REGISTRY `Mx-*-Sdev`:
S-Q 3 · S-G 4 · Union(S) 5 · R-Q 4 · R-G 5 · H-QG 4 · H-GQ 3 (of 9). Spend ≈ $0.41.

**Kit updated:** adopted upstream rate-limit fix `8739a10` (our `7baca49`) —
`provider.allow_fallbacks` now True so a busy provider (429) reroutes to another
provider of the same model. Our Windows/memory kit patches preserved. See §18.

**Reading:** proposer model dominates outcomes; structured repair adds a thin,
**same-model** margin (unlocks `p10` for R-Q/R-G in 1+3 turns that S's 8 don't);
handoff (cross-model repair) is not free — `H-GQ` lost `p05`. Model
complementarity (Union(S)=5) is the biggest lever → argues for adaptive
model choice in the final agent. Hard floor unsolved by any arm: `p09_imo1964`,
`rmo_2000_2`, `rmo_2000_3`.

**`submission/agent.py` still stub** (no final adaptive scorer yet).

**Next:** freeze prompts/caps/arm code, then run each arm once on the `S_eval`
holdout (Phase 6). Then build the adaptive `submission/agent.py`.

**RUNTIME RESOLVED — unchanged since 2026-08-25:**

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

**S_dev matrix is DONE (fixed kit).** Split accepted. Now entering iteration/repair
of the arms, then the frozen `S_eval` pass. Concretely:

1. **Iterate on S_dev only** (allowed). Use the per-problem matrix to target the
   thin repair margin and model-choice lever; do NOT touch `S_eval`.
2. Before any `S_eval` run: **freeze** prompts, caps, routing, and arm code
   (SPLIT.md rule), and record the frozen turn budgets (note the S=8 vs R/H=1+3
   turn confounder — decide whether to align).
3. Run each frozen arm **once** on `S_eval` (Phase 6); log `Ev-*-Seval` rows.
4. Build the adaptive `submission/agent.py` (still a stub) — the data argues for
   **model choice / union**, not more repair depth.
5. sshrun can't `git fetch` (no creds) → push from Windows SoT, then `scp`
   changed files over. Kit already carries the rate-limit fix (§18).

Runtime/scripts on sshrun: `run_matrix_sdev.sh` (6-arm driver) + `check.sh`
(status) under `~/Documentos/verified-mechanism/`.

---

## Arms

`re-takehome-main/experiments_agents/` → `s_q` `s_g` `r_q` `r_g` `h_qg` `h_gq`
(via `run.py --agent module:factory`). S = kit `simple_agent` multi-turn Lean loop;
R = explicit propose/repair with diagnostics; H = R with the other repair model. See §15 / plan.

---

## Thesis

S / R / H science unchanged. Measure under matched budgets; Solo Union derived; log confounders.
