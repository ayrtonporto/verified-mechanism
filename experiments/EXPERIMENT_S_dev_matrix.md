# Experiment context — S_dev science matrix (S/R/H)

**Purpose of this file:** a self-contained handoff so another agent can understand
*this experiment* (the 6-arm matrix on `S_dev`), its result, and how to continue —
without re-reading the whole repo. Dated **2026-08-26**. Focused on the experiment;
broader project context is summarized where needed.

---

## 0. TL;DR

- **Task:** a Lean-4 / Mathlib theorem-proving take-home ("Verified Mechanisms RE
  kit"). An agent must emit a complete Lean file that the kit's comparator accepts,
  under a per-problem **$1 budget** and an **8 h wall cap**. Score = # comparator-
  accepted proofs.
- **Science question:** does structured **repair** (propose → Lean diagnostics →
  targeted repair) and **cross-model handoff** beat plain multi-turn baselines,
  under matched budget? Arms = **S** (solo baseline), **R** (same-model repair),
  **H** (handoff = other model repairs), each × two models **Q**/**G**.
- **This experiment:** ran all **6 arms once on the 9-problem `S_dev`** development
  set on the production runtime (`sshrun`), under the **rate-limit-fixed kit**.
- **Result (pass/9):** S-Q **3** · S-G **4** · Union(S) **5** · R-Q **4** · R-G **5**
  · H-QG **4** · H-GQ **3**. Any-arm union **6/9**. Cost ≈ **$0.33**. **0 rate-limit
  errors.**
- **Reading:** the **proposer model dominates**; repair adds a **thin, same-model**
  margin (only `p10`); **handoff can hurt** (H-GQ lost `p05`); **model
  complementarity** (Union=5) is the biggest lever → the final agent should favor
  adaptive **model choice / union**, not deeper repair.

---

## 1. Project background (minimum needed)

- Provider models are called **only** through OpenRouter, restricted to two:
  - **Q = `qwen/qwen3.5-flash-02-23`** (MODEL_A)
  - **G = `openai/gpt-oss-120b`** (MODEL_B)
- The harness (`re-takehome-main/src/re_harness/`) runs each problem: the agent
  produces a Lean file; a **Dockerized Lean+comparator** (`ghcr.io/verified
  mechanisms/re-takehome-lean@sha256:ee48287…`, digest-pinned) checks it. A problem
  **passes** only if the comparator accepts **and** budget/wall/answer-shape hold.
- Repo layout: the **kit is vendored** under `re-takehome-main/` (not a submodule);
  our science code + docs live alongside.
- **Source of truth = the git repo on Windows.** The Linux box `sshrun` runs the
  paid jobs but **cannot `git fetch`** (no GitHub creds) → we push from Windows and
  `scp` changed files to sshrun.

---

## 2. The six arms

All in `re-takehome-main/experiments_agents/`. Invoked via
`run.py --agent experiments_agents.<arm>:create_agent`.

| Arm | Factory | Mechanism |
|-----|---------|-----------|
| **S-Q** | `s_q` | Solo: kit baseline multi-turn Lean loop, Qwen. |
| **S-G** | `s_g` | Solo baseline, GPT-OSS. |
| **R-Q** | `r_q` | Propose (Qwen) → Lean diagnostics → **Qwen** targeted repair. |
| **R-G** | `r_g` | Propose (GPT-OSS) → **GPT-OSS** repair. |
| **H-QG** | `h_qg` | Propose **Qwen** → **GPT-OSS** repair (handoff). |
| **H-GQ** | `h_gq` | Propose **GPT-OSS** → **Qwen** repair (handoff). |

- **S** prompt = the **kit's own baseline** (`baselines/simple_agent.py`), unmodified;
  we only pin the model. Turn cap `BASELINE_MAX_TURNS=8`.
- **R/H** propose+repair prompts are **ours** (`repair.py`). Caps: `propose=1`,
  `repair=3` (so 4 attempts). The propose system prompt mirrors the kit baseline on
  purpose, so S vs R differs mainly in the **structured diagnostic-driven repair**,
  not the opening prompt. Repair enforces `REPAIR_INVARIANTS` (no `sorry`/`admit`/
  axioms, don't weaken the theorem, prefer minimal local fixes).
- **Union** is *derived*, not a run: `Union(S) = S-Q OR S-G` per problem.
- **Budget matched axis = $** (all under a `VM_BUDGET_USD=0.15/problem` guard).
  **Confounder:** S uses 8 turns; R/H use 1+3=4. Turns are **not** matched — decide
  whether to align before `S_eval`.

---

## 3. Runtime & how to run (`sshrun`)

- **Where:** `ssh usuario@sshrun` (Tailscale, key auth). Repo at
  `~/Documentos/verified-mechanism`; runtime root `re-takehome-main`; `.venv` py3.12.
- **Why sshrun:** jobs survive client disconnect (run inside `tmux`). WSL was
  abandoned (session-kill); Windows Docker Desktop crashed on the big image. Cloud
  not used. sshrun is slow but the 8 h/problem cap ≫ wall, so no false timeouts.
- **Env recipe:** `LEAN_CONTAINER_MEMORY=8g COMPARATOR_TIMEOUT_S=900
  LEAN_CHECK_TIMEOUT_S=300 N_WORKERS=1 VM_BUDGET_USD=0.15`.
- **Problem sets** (materialized, each a dir with `manifest.json` + member problem
  folders): `re-takehome-main/sets/{calib,S_dev,S_eval}`. Use **relative** paths:
  `--problems sets/S_dev`.
- **Run one arm:**
  ```bash
  cd ~/Documentos/verified-mechanism/re-takehome-main
  .venv/bin/python run.py --problems sets/S_dev --out outputs \
      --agent experiments_agents.s_q:create_agent
  ```
- **Full matrix (unattended):** `~/Documentos/verified-mechanism/run_matrix_sdev.sh`
  runs all 6 arms sequentially; launch in tmux; `check.sh <arm>` prints status.
- **Outputs:** `outputs/<arm>/<timestamp>Z/` with per-problem `result.json`,
  `solution.lean`, `events.jsonl`, and a run-level `summary.json`
  (`total_points`, `actual_cost_usd`, `wall_s_sum`, per-problem rows).

---

## 4. The frozen split (`experiments/SPLIT.md`, **accepted**)

- **Calib:** `p01_linear` (cost/runtime sanity; also a member of S_dev).
- **S_dev (n=9, development — tune here):** `p01_linear`, `p03_sq_ge_two_ab`,
  `p05_gcd_mersenne`, `p06_pow_mod`, `p09_imo1964`, `p10_factorial_pow`,
  `rmo_2000_2`, `rmo_2000_3`, `putnam_2018_a1`.
- **S_eval (n=7, HOLDOUT — do not touch until arms are frozen):** `p02_frac_cancel`,
  `p04_sum_sq`, `p07_least_divisible`, `p08_sum_products`, `rmo_2000_6`,
  `rmo_2001_2`, `putnam_2020_a2`.
- **Rules:** tune only on S_dev; freeze prompts/caps/routing/arm-code before S_eval;
  run each frozen arm once on S_eval; never move ids after seeing results.

---

## 5. Rate-limit incident + kit fix (why this experiment was re-run)

**Symptom:** the first S-G launch got **HTTP 429** on `openai/gpt-oss-120b` — the
OpenRouter shared pool (provider **AkashML**) was rate-limited. The kit pinned
`provider.allow_fallbacks: False` and **did not retry**, so a busy provider made the
problem score **0 through no fault of the agent**. (Qwen was on a different provider,
so the earlier S-Q run never saw it.)

**Fix (maintainer, upstream `VerifiedMechanisms/re-takehome` commit `8739a10`; our
adoption `7baca49`):** in `src/re_harness/llm.py`
1. `provider.allow_fallbacks` **False → True** — OpenRouter may reroute to another
   provider of the **same** model when the primary is busy (model fallback still off;
   `require_parameters` + `max_price` ceiling unchanged). Verified: rerouted AkashML
   → **CoreWeave**, 0 errors.
2. A **429 no longer poisons the budget ledger** (was marked "unknown"); it releases
   the reservation or settles the reported cost.

We copied only the 4 touched kit files (pristine at upstream `f7109de`) and
**preserved our two local kit patches**: `artifacts.py` `os.fchmod` Windows guard,
`lean.py` `LEAN_CONTAINER_MEMORY` override (both no-ops/safe on Linux). sshrun's kit
was updated by `scp` (can't git fetch). **All results below are under the fixed kit.**

> Any pre-fix numbers (e.g. old `SQ-Sdev` = 2/9) are **superseded**.

---

## 6. Results — the experiment (fixed kit, S_dev, 2026-08-26, 0×429)

### Per-arm totals

| Arm | pass/9 | cost (USD) | wall (s) | REGISTRY id |
|-----|:-----:|-----------:|---------:|-------------|
| S-Q | 3 | 0.06814 | 2629 | Mx-SQ-Sdev |
| S-G | 4 | 0.08868 | 9730 | Mx-SG-Sdev |
| **Union(S)** | **5** | — | — | (derived) |
| R-Q | 4 | 0.05630 | 2265 | Mx-RQ-Sdev |
| R-G | 5 | 0.05023 | 4877 | Mx-RG-Sdev |
| H-QG | 4 | 0.02537 | 3245 | Mx-HQG-Sdev |
| H-GQ | 3 | 0.04444 | 3071 | Mx-HGQ-Sdev |

Matrix spend ≈ **$0.333**; cumulative project ≈ **$0.41** (of ~$50 lab cap / $10
session limit).

### Per-problem grid (1 = comparator-accepted)

| Problem | Diff | S-Q | S-G | R-Q | R-G | H-QG | H-GQ | Union(S) |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| p01_linear | E | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| p03_sq_ge_two_ab | E | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| p05_gcd_mersenne | M | 0 | 1 | 0 | 1 | 0 | 0 | 1 |
| p06_pow_mod | M | 1 | 0 | 1 | 0 | 1 | 0 | 1 |
| p09_imo1964 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| p10_factorial_pow | H | 0 | 0 | **1** | **1** | 0 | 0 | 0 |
| rmo_2000_2 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rmo_2000_3 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| putnam_2018_a1 | H | 0 | 1 | 0 | 1 | 1 | 1 | 1 |
| **TOTAL** | | **3** | **4** | **4** | **5** | **4** | **3** | **5** |

Never solved by any arm: `p09_imo1964`, `rmo_2000_2`, `rmo_2000_3` (hardest H).
Any-arm union = **6/9**.

---

## 7. Reading / analysis

1. **Proposer model dominates the outcome.** `p06_pow_mod` is solved only by
   Qwen-proposing arms (S-Q, R-Q, H-QG); `p05_gcd_mersenne` only by GPT-OSS-involved
   arms (S-G, R-G). The opening model mostly decides success; repair is a thin margin.
2. **Repair helps, but narrowly and same-model.** The *only* problem repair unlocks
   that no baseline solves is `p10_factorial_pow`, and only for **R-Q and R-G**
   (same model repairing its own attempt). It does so in **1+3 turns** where the
   baseline's **8** turns fail → structured diagnostic repair is more turn-efficient.
3. **Handoff (cross-model repair) is not free — it can hurt.** **H-GQ lost `p05`**
   that same-model R-G keeps: Qwen repairing a GPT-OSS attempt failed where GPT-OSS
   repairing its own succeeded. The repairer works best on its **own** model's
   failure mode. (H-QG matched R-Q's count but with different coverage.)
4. **Model complementarity is the biggest lever.** `Union(S) = 5` ≥ every single arm
   (only R-G ties it). Qwen and GPT-OSS solve **different** problems (p06 vs p05) →
   combining models beats stacking repair.
5. **Design implication:** the final `submission/agent.py` (still a stub) should
   prioritize **adaptive model choice / union / routing**, using repair as a cheap
   same-model booster — not deeper repair or handoff.
6. **Ceiling:** 3 of 9 are unsolved by everyone → real headroom; iteration targets.

---

## 8. How to continue (next agent starts here)

**Allowed now:** iterate on **S_dev only**. **Do not run or inspect `S_eval`** until
arms are frozen.

1. Target the two levers the data highlights:
   - **Model choice / union** (biggest ceiling) — e.g., route by problem features,
     or run both and take the union in the final agent.
   - The **same-model repair** margin (cheap, works) — keep; consider more repair
     turns *only* if turn-budget is re-matched vs S.
2. **Decide the turn-budget confounder** (S=8 vs R/H=1+3) and record it before
   freezing.
3. **Freeze** prompts, caps, routing, arm code → then run **each arm once on
   `S_eval`** (`--problems sets/S_eval`), log `Ev-*-Seval` rows in
   `experiments/REGISTRY.md`. This is a one-shot holdout; no tuning after.
4. Build the adaptive `submission/agent.py`.
5. **Deadline:** the take-home is due **Aug 30** (submit repo link + PDF writeup).

---

## 9. Gotchas & durable facts

- **Lean image looks "missing" but isn't:** it's **digest-pinned with a `<none>`
  tag**, so `docker images | grep lean` shows nothing. Verify with
  `docker images -a --digests | grep verified` or inspect the full `@sha256` ref.
- **sshrun can't `git fetch`** (no GitHub creds). Push from Windows SoT, then `scp`
  changed files. Key-auth SSH works.
- **Budget guard:** `VM_BUDGET_USD` is **per problem**. We used 0.15 as a safety cap
  (~1000× observed cost) so no single problem can run away; it never causes false
  fails at real costs (~1e-4–1e-2/problem).
- **Failure strings:** `build failed` = the model's Lean solution didn't compile (a
  real solve failure). `temporarily rate-limited` / HTTP 429 = provider issue (should
  no longer fail a run post-fix; if seen, treat as re-run, not a real failure).
- **"NOT REAL LANDRUN" warnings** in logs are just the sandbox-enforcement notice —
  harmless.

---

## 10. Key files & commits (branch `claude/setup-calibration-evaluation-…`)

| Path | What |
|------|------|
| `experiments/SPLIT.md` | Frozen split (**accepted**). |
| `experiments/tables/master_matrix.md` | Per-problem grid + totals (this experiment). |
| `experiments/REGISTRY.md` | One row per run; `Mx-*-Sdev` = this matrix. |
| `experiments/SPEND_PLAN.md` | Phases + $ ledger (~$0.41). |
| `experiments/RUNBOOK.md` | How to run arms; set paths. |
| `PROJECT_STATE.md` §18 | Full narrative of this experiment + kit fix. |
| `HANDOFF.md` | Top-level status + next actions. |
| `re-takehome-main/experiments_agents/` | The 6 arm factories + `repair.py`, `common.py`. |
| `re-takehome-main/sets/` | calib / S_dev / S_eval runnable sets. |
| `re-takehome-main/src/re_harness/llm.py` | Kit LLM client (carries the rate-limit fix). |

**Relevant commits:** `f5d84e8` (materialize sets) · `7baca49` (adopt kit rate-limit
fix) · `3d578a9` (log full S_dev matrix) · `0459d08` (accept split + docs current).
