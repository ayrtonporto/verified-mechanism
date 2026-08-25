# Builder brief — experimental arms (science layer)

**Status:** ready to hand to a coding agent  
**Authority:** `design/COORDINATION_PLAN.md` (2026-08-25)  
**Do not redesign the science.** Implement and freeze infrastructure + arms.

---

## Mission

Build the **scientific experiment layer** for the Verified Mechanisms RE take-home:

1. Freeze what solo baseline actually is.
2. Create experiment logging files.
3. Implement six arms with matched budgets:
   - `S-Q`, `S-G` — solo baselines
   - `R-Q`, `R-G` — same-model targeted repair
   - `H-QG`, `H-GQ` — cross-model handoff
4. Calibrate cheaply on `p01_linear`.
5. Stop before final adaptive submission agent / blackboard / dual-draft product.

**Success = runnable arms + honest docs + cheap calib evidence.**  
Not a high score on all 16 problems.

---

## Read first (in order)

1. `design/COORDINATION_PLAN.md` — full protocol
2. `HANDOFF.md`
3. `PROJECT_STATE.md` (§13.11–15, D011–D015)
4. `SETUP_BLOCKERS.md` if touching Lean/WSL runtime
5. `re-takehome-main/docs/AGENT_API.md`
6. `re-takehome-main/docs/OUTPUTS.md`
7. `re-takehome-main/RULES.md`
8. `re-takehome-main/baselines/simple_agent.py` ← **critical for S vs R**

Optional: `design/SOTA_MULTI_MODEL_MATH_MEMO.md`

---

## Hard constraints

### Models (only these)

- Qwen: `qwen/qwen3.5-flash-02-23`
- GPT-OSS: `openai/gpt-oss-120b`

No `:free`, `:online`, plugins, extra models.

### Trees

| Role | Path |
|------|------|
| Git source of truth | `D:\Mis documentos\Documentos\Verified Mechanism` (Windows) |
| Runtime | WSL `~/verified-mechanism` |

Sync before editing on both sides. Prefer implementing on Windows tree, then sync to WSL for runs.

### Secrets

- API key only in WSL: `~/verified-mechanism/re-takehome-main/.env` (gitignored)
- **Never** paste keys in chat, commits, logs, or this brief

### Git

- Local commits OK when a **finished block** is done
- **No `git push`** unless user says explicitly (“pusheá” / “hacé push”)
- Do not commit incomplete half-features mid-block if user said wait

### Spend

- Lab key ~$50 hard stop
- **No large matrix** without `experiments/SPEND_PLAN.md` line + user OK
- Default this brief: **Phase 0–1 only** unless user expands scope
  - $0 docs/registry
  - calibration ≤ ~$0.05 unless user raises cap
- Prefer user-owned long runs when expensive; give exact commands

### Runtime recipe (every Lean/model run on this laptop)

```bash
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900
# Chrome closed; host free RAM comfortable
cd ~/verified-mechanism/re-takehome-main
```

- `run.py --problems` needs a **set** with `manifest.json`, not a single problem folder
- One Lean worker on this RAM; do not parallelize Mathlib containers
- Helper reference: `bash /home/ayrton/verified-mechanism/run_p01_e2e_clean.sh`
- Canonical prior calib: `outputs/baseline/20260824T040147Z/` — Qwen × p01 **passed**, ~$0.00018

### Language / style

- Code and experiment docs: clear English
- User comms: simple Spanish if talking to Ayrton; little jargon
- Prefer small readable code over frameworks

---

## Critical design fact (do not miss)

`baselines/simple_agent.py` is **already** a multi-turn Lean repair loop:

```text
propose → lean.check_file → feedback in next prompt → repeat
```

Defaults: `DEFAULT_MAX_TURNS = 25`, model via `BASELINE_MODEL`, factory `baselines.simple_agent:create_agent`.

Therefore:

| Arm | Meaning |
|-----|---------|
| **S-Q / S-G** | Kit baseline behavior as faithfully as practical (same loop/prompts), only model changes |
| **R-Q / R-G** | Explicit two-role targeted repair: clearer repair prompt + repair invariants + structured failure context. **Same model** for propose and repair |
| **H-QG / H-GQ** | **Identical** to R in turns/caps/prompts structure; only the **repair model id** changes |

**Do not silently redefine S to mean R.**  
Document the exact S semantics in `experiments/BASELINE_SEMANTICS.md` before large runs.

If R is only a stronger repair prompt on top of the same outer loop, say so. That is fine scientifically.

---

## Arms to implement

| ID | Proposer | Repairer | Notes |
|----|----------|----------|-------|
| **S-Q** | Qwen | (baseline loop, same model) | wrap/call baseline; `BASELINE_MODEL=qwen/...` |
| **S-G** | GPT-OSS | (baseline loop) | same with GPT-OSS |
| **R-Q** | Qwen | Qwen | explicit repair protocol |
| **R-G** | GPT-OSS | GPT-OSS | explicit repair protocol |
| **H-QG** | Qwen | GPT-OSS | match R budget; change repair model only |
| **H-GQ** | GPT-OSS | Qwen | match R budget; change repair model only |

### Matched compute (required)

For fair `H vs R` and readable `R vs S`:

- Same `max_propose_turns` / `max_repair_turns` (or equivalent) within R/H family
- Same `max_tokens`, temperature policy
- Same stop rules (success, no-progress, cap, budget)
- Always log: USD, calls_q, calls_g, lean_checks, wall

Suggested **exploratory** caps (freeze after calib; do not invent permanent numbers before cost data):

- Solo S: start from baseline but consider lower `BASELINE_MAX_TURNS` for pilot (e.g. 3–8) while probing — record whatever you freeze
- R/H: e.g. 1 propose + up to N repairs with early stop (N small until calib)

### Repair-prompt invariant (all R/H repair calls)

Explicitly instruct:

- no `sorry` / `admit`
- no new axioms or unsafe escapes
- do not alter theorem statements to weaken the problem
- repair the actual proof obligation
- prefer minimal correction when diagnostic is local
- return a complete Lean file

This does **not** replace the comparator.

### Core R/H loop

```text
1. Proposer writes full proof
2. Lean check
3. If OK → checkpoint + stop
4. Else → repairer gets: problem, failed proof, exact Lean diagnostics, invariants
5. Lean check
6. Stop on success / repeated no-progress / turn cap / budget
```

Optional later (NOT this brief): error router, dual draft, lemmas.

### Solo Union

Do **not** implement a separate best-of-two science arm.  
Derive per problem: `U = S-Q OR S-G` in the matrix.

---

## Deliverables (this construction block)

### A. Docs / experiment layer ($0)

Create:

```text
experiments/
  REGISTRY.md
  SPEND_PLAN.md
  SPLIT.md                 # placeholder OK if split not chosen yet; say "unset"
  BASELINE_SEMANTICS.md    # freeze S behavior after inspecting simple_agent
  tables/
    master_matrix.md       # empty skeleton with arm columns
```

**REGISTRY** columns (minimum):

```text
id | date | git | arm | set | pass_count | usd | calls_q | calls_g | lean_checks | wall | output_path | note
```

**master_matrix** columns:

```text
| Problem | S-Q | S-G | Union | R-Q | R-G | H-QG | H-GQ |
```

**SPEND_PLAN**: ~$50 cap, reserve 20–30% final, Phase 0–1 near-zero, no full matrix without OK.

**SPLIT.md**: mark `S_dev` / `S_eval` as **not frozen yet** unless user already chose; choosing the split may be a separate task.

### B. Code

Implement arms so they are invokable via harness `--agent module:factory` (preferred for experiments) **without** turning `submission/agent.py` into the final adaptive scorer yet.

Recommended layout (adapt if cleaner):

```text
re-takehome-main/
  submission/
    agent.py                 # leave stub OR thin dispatcher behind env flag — do not ship final adaptive logic
  experiments_agents/        # or submission/arms/ — pick one place, document it
    __init__.py
    common.py                # extract_lean, format diagnostics, stop rules, invariants
    solo.py                  # S-Q / S-G factories (baseline wrapper)
    repair.py                # shared R/H loop; model pair config
    factories.py             # create_agent_s_q, create_agent_r_q, create_agent_h_qg, ...
```

Each arm factory must be loadable, e.g.:

```bash
uv run python -m re_harness.runner \
  --agent experiments_agents.factories:create_agent_s_q \
  --problems <set_with_manifest> \
  ...
```

(Use the project’s actual runner entrypoint; inspect `run.py` / docs — do not invent CLI flags.)

**Reuse** baseline extraction/feedback helpers where possible; do not fork the kit needlessly.

### C. Baseline semantics freeze

In `experiments/BASELINE_SEMANTICS.md` write:

- exact module path
- default turns/tokens/temperature
- that S is multi-turn Lean feedback already
- how R differs (prompt structure, role split, caps)
- how H differs from R (repair model only)
- env vars used (`BASELINE_MODEL`, arm-specific vars, etc.)

### D. Cost logging verification

Confirm harness records OpenRouter `usage.cost` → `actual_cost_usd` in outputs (`result.json` / summary / events).  
Document where to read USD per run in REGISTRY instructions.  
No need to reimplement accounting.

### E. Calibration (only with spend OK; default small)

1. Ensure Qwen S-Q × `p01_linear` still green (or cite existing `20260824T040147Z` if identical recipe).
2. Run **S-G × p01** twin calibration.
3. Optional smoke: one R-Q turn-capped run on p01 if budget allows.
4. Record rows in REGISTRY + update SPEND_PLAN spent.

Use temp 1-problem set pattern from `run_p01_e2e_clean.sh`.

### F. Out of scope for this brief

Do **not**:

- final adaptive submission agent (Phase 7)
- blackboard / debate / RAG / back-translation
- rich error router
- dual-draft product path
- lemma decomposition
- full 16 × 6 matrix
- choose and freeze `S_dev`/`S_eval` unless explicitly asked in the same task
- `git push`
- install toolchains without asking
- paste API keys

---

## Implementation order (mandatory)

### Phase 0 — $0 / near $0

1. Read plan + baseline + API.
2. Write `BASELINE_SEMANTICS.md` draft from code inspection.
3. Create REGISTRY, SPEND_PLAN, SPLIT placeholder, master_matrix skeleton.
4. Verify cost fields in harness docs/code paths.
5. Scaffold arm factories (can be thin wrappers first).

### Phase 1 — calib

1. WSL recipe + sync code.
2. S-G × p01 (and S-Q if needed).
3. Log REGISTRY + costs.
4. Propose freeze of exploratory turn caps based on real $.

### Stop and report

After Phase 0–1, report and wait before S_dev batches / full R/H matrix.

---

## Done when

- [ ] `experiments/` files exist and are usable
- [ ] `BASELINE_SEMANTICS.md` honestly describes S vs R vs H
- [ ] Six factories load (or clear single factory + env arm id — document one pattern)
- [ ] R and H share one code path; H only swaps repair model
- [ ] S uses baseline path, not a silent R clone
- [ ] Cost logging path documented
- [ ] At least S-G p01 calib attempted/recorded (or blocked with hard evidence)
- [ ] REGISTRY has rows for any paid runs
- [ ] No final adaptive agent claimed “done”
- [ ] Short handoff note: how to run each arm (exact commands)

---

## Report format (end of session)

1. What was implemented (paths).
2. S vs R distinction in one paragraph.
3. How to run each arm (commands).
4. Calib results table (pass, $, calls, wall, path).
5. Spend used vs plan.
6. Blockers.
7. Exact next step for the following agent (e.g. freeze split, run S-Q/S-G on S_dev).

---

## Copy-paste prompt for the other agent

```text
You are the BUILDER agent for Verified Mechanisms RE take-home.

Authority: design/COORDINATION_PLAN.md (2026-08-25) and design/BUILDER_BRIEF.md.
Do not redesign the science. Do not build blackboard/debate/final adaptive scorer.

Goal:
1) Freeze solo baseline semantics from re-takehome-main/baselines/simple_agent.py
   (NOTE: it is ALREADY multi-turn Lean repair — S must stay baseline-faithful;
    R is explicit targeted-repair protocol; H = R with other model on repair only).
2) Create experiments/REGISTRY.md, SPEND_PLAN.md, SPLIT.md (placeholder OK),
   BASELINE_SEMANTICS.md, tables/master_matrix.md.
3) Implement invokable arms S-Q, S-G, R-Q, R-G, H-QG, H-GQ via harness
   --agent module:factory (prefer experiments_agents/ or similar; keep
   submission/agent.py stub or thin only).
4) Match R/H compute; log usd, calls_q, calls_g, lean_checks, wall.
5) Verify usage.cost → actual_cost_usd logging path.
6) Calibrate: GPT-OSS solo × p01_linear with WSL recipe
   PATH+LEAN_CONTAINER_MEMORY=8g+COMPARATOR_TIMEOUT_S=900;
   record REGISTRY. Cite existing Qwen p01 calib if still valid.
7) Stop after Phase 0–1 unless user expands. No push. No API keys in chat.
8) Sync Windows git SoT and WSL ~/verified-mechanism before dual edits.

Windows SoT: D:\Mis documentos\Documentos\Verified Mechanism
WSL runtime: ~/verified-mechanism/re-takehome-main
Key: WSL .env only.

Deliver report: paths, S vs R paragraph, run commands, calib table, spend, blockers, next step.
```

---

## One-line north star

**Measure S / R / H cleanly under matched budgets; derive Solo Union; only later build the scorer.**
