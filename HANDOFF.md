# HANDOFF

## Read first

1. `PROJECT_STATE.md` (authoritative; includes §13.11 e2e calibration)
2. `SETUP_BLOCKERS.md` (WSL unblocked; local RAM/timeout overrides)
3. `re-takehome-main/docs/AGENT_API.md` + `RULES.md`
4. Baseline: `re-takehome-main/baselines/simple_agent.py`
5. Do not invent execution constraints

---

## Current phase

**Phase 0 closed for research start → Phase 1/2 + investigation.**

Env works. First paid e2e green. `submission/agent.py` still stub.

---

## What is true right now (2026-08-24)

### Environment

- WSL Ubuntu-22.04, Docker OK, Lean image pinned + health OK.
- OpenRouter key in **WSL only**: `~/verified-mechanism/re-takehome-main/.env` (gitignored).
- Local Lean must use **`LEAN_CONTAINER_MEMORY=8g`** (kit default 5g thrashs Mathlib here).
- Cold comparator: use **`COMPARATOR_TIMEOUT_S=900`** on this laptop.
- Host: close Chrome before heavy Lean; `.wslconfig` memory=10GB.
- Two trees: Windows `D:\...\Verified Mechanism` (git source of truth this machine) vs WSL
  `~/verified-mechanism` (runtime). Sync before dual edits.

### Proven paid run (canonical calibration)

```text
WSL: ~/verified-mechanism/re-takehome-main/outputs/baseline/20260824T040147Z/
```

| | |
|---|---|
| Agent | `baselines.simple_agent:create_agent` |
| Model | `qwen/qwen3.5-flash-02-23` |
| Problem | `p01_linear` only (temp set `tmp_p01_only`) |
| Result | **passed 1/1** (REPL + comparator) |
| Cost | **$0.00017719** (1 LLM call, 1 turn) |
| Wall | ~192 s |
| Script | `run_p01_e2e_clean.sh` |

### Failure mode that was *not* the repo

Earlier “almost” runs failed because of **PC/WSL** (5g container thrash, 180s comparator, killed
`wsl.exe` clients, Windows `$HOME` expansion). Same baseline + problem passes with 8g + 900s +
one attached script.

### Kit touch (local only — remember before submit)

- `re-takehome-main/src/re_harness/lean.py`: optional `LEAN_CONTAINER_MEMORY` (default still `5g`).
- Not an architecture decision. Revisit before grading submit (D011/D013 in PROJECT_STATE).

---

## Runtime recipe (copy every time)

```bash
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900
cd ~/verified-mechanism/re-takehome-main
```

One-problem e2e helper (already used successfully):

```bash
bash /home/ayrton/verified-mechanism/run_p01_e2e_clean.sh
# or from Windows:
# wsl.exe -d Ubuntu-22.04 -- bash /home/ayrton/verified-mechanism/run_p01_e2e_clean.sh
```

Note: `run.py --problems` needs a **set directory** with `manifest.json`, not `sample-problems/p01_linear`.

---

## Immediate next actions (investigation chat)

1. Twin calibration: **GPT-OSS** on `p01_linear` same recipe (cost/latency baseline).
2. Optional: one mid/hard problem single-model probe before full 16.
3. Phase 1 instrumentation if harness outputs are not enough for Part Two tables.
4. Phase 2 solo baselines (Qwen / GPT-OSS) under matched budgets.
5. Then minimal collaboration (Candidate A: propose → Lean → other model repairs).
6. Do **not** start blackboard / multi-agent frameworks yet.
7. No push without explicit user OK. No large matrices without a spend plan.

---

## Do not do yet

- Complex multi-agent / blackboard as first design
- Prompt spam without measurements
- Full 16-problem runs without budget plan
- Silent kit interface changes
- Pasting API keys into chat

---

## Thesis (unchanged)

Coordination layer so fixed Qwen + GPT-OSS produce Lean-accepted proofs; measure when
collaboration beats either solo. Lean compiler feedback is a coordination signal to test.

Primary candidate still: **propose → verify → diagnose/repair → verify**.

---

## Next action

**Start investigation: GPT-OSS p01 calibration twin, then solo/collaboration design from data.**
Read PROJECT_STATE §13.11–14 first.
