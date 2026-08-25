# Baseline semantics freeze (S vs R vs H)

**Frozen:** 2026-08-25 (Phase 0 builder)  
**Authority:** `design/COORDINATION_PLAN.md`, `design/BUILDER_BRIEF.md`  
**Source of S:** `re-takehome-main/baselines/simple_agent.py`

---

## Critical fact

The kit baseline is **already** a multi-turn Lean repair loop:

```text
propose full Lean file
→ lean.check_file
→ append compiler feedback to next prompt
→ repeat until accepted or max_turns
```

It is **not** a single-shot propose. Therefore **S must stay baseline-faithful**.  
**R is not “add repair to solo”** — it is an **explicit two-role targeted-repair protocol** with structured failure context and repair invariants.  
**H = R** with only the **repair model id** changed.

---

## Models (only these)

| Short | OpenRouter id |
|-------|-----------------|
| Qwen | `qwen/qwen3.5-flash-02-23` (`MODEL_A`) |
| GPT-OSS | `openai/gpt-oss-120b` (`MODEL_B`) |

---

## S — Solo baseline (kit-faithful)

| Field | Value |
|-------|--------|
| Module | `baselines.simple_agent.SimpleBaselineAgent` |
| Factories (science) | `experiments_agents.s_q:create_agent`, `experiments_agents.s_g:create_agent` |
| Kit factory | `baselines.simple_agent:create_agent` (same class; model via env) |
| Loop | Single model; chronological feedback; no role split |
| Default `max_turns` | `DEFAULT_MAX_TURNS = 25` (`BASELINE_MAX_TURNS`, clamp 1–25) |
| Default `max_tokens` | `DEFAULT_MAX_TOKENS = 12000` (`BASELINE_MAX_TOKENS`, 1000–32000) |
| Default temperature | `0.2` (`BASELINE_TEMPERATURE`, 0.0–2.0) |
| Model env | `BASELINE_MODEL` (must be in `ALLOWED_MODELS`) |
| Prompt shape | System: write complete Lean 4 + Mathlib; no sorry/admit/axioms; preserve theorem names. User: problem id, turn k/N, description, challenge file, optional previous Lean messages. |
| Feedback | `_format_messages(check.messages)` — severity/pos/data strings, last 6000 chars. **No** separate “failed proof” block beyond rewriting from challenge + feedback. |
| Extraction | Last ```lean fence, else from first `import `, else previous candidate |
| Stop | accepted by REPL, or turns exhausted |
| Metadata | `baseline: simple`, model, turns, attempts[] |

### S-Q / S-G

| Arm | Model | Notes |
|-----|-------|--------|
| **S-Q** | Qwen | Factory pins model; ignores `BASELINE_MODEL` override for the pin |
| **S-G** | GPT-OSS | Same |

Pilot calibration historically used `BASELINE_MAX_TURNS=3` on p01 (still kit loop semantics).

---

## R — Same-model targeted repair

| Field | Value |
|-------|--------|
| Module | `experiments_agents.repair.TargetedRepairAgent` |
| Factories | `experiments_agents.r_q:create_agent`, `experiments_agents.r_g:create_agent` |
| Proposer | Same model as repairer |
| Loop | Explicit propose stage then repair stage (see below) |
| Propose turns | `REPAIR_MAX_PROPOSE_TURNS` default **1** (clamp 1–5) |
| Repair turns | `REPAIR_MAX_REPAIR_TURNS` default **3** (clamp 0–24) |
| max_tokens | `REPAIR_MAX_TOKENS` default **12000** (same ceiling family as baseline) |
| temperature | `REPAIR_TEMPERATURE` default **0.2** |
| Repair input | problem + **previous failed proof** + **exact Lean diagnostics** + **repair invariants** |
| Stop | success / no-progress (identical normalized diagnostics twice) / turn caps / LLM errors left to harness budget |

### Repair-prompt invariants (every R/H repair call)

- no `sorry` / `admit`
- no new axioms or unsafe escapes
- do not alter theorem statements to weaken the problem
- repair the actual proof obligation
- prefer minimal correction when the diagnostic is local
- return a complete Lean file

### How R differs from S (honest)

| | S (baseline) | R (targeted repair) |
|--|--------------|---------------------|
| Roles | One monolithic prompt every turn | Separate **propose** vs **repair** prompts |
| Failure context | Compiler messages only (no explicit failed-source block) | Failed proof source + diagnostics + invariants |
| Caps | `BASELINE_MAX_TURNS` total | Propose + repair budgets (matched across R/H) |
| Intent | Kit reference behavior | Isolate **method** benefit of structured repair |

R may still use a similar outer “try Lean, then call model again” shape. The scientific difference is **prompt/role structure and failure packaging**, not “Lean feedback exists.”

---

## H — Cross-model handoff

| Arm | Propose | Repair |
|-----|---------|--------|
| **H-QG** | Qwen | GPT-OSS |
| **H-GQ** | GPT-OSS | Qwen |

**Identical code path and caps to R.** Only `repair_model` changes.  
Factories: `experiments_agents.h_qg:create_agent`, `experiments_agents.h_gq:create_agent`.

Comparisons:

- `H-QG` vs `R-Q` (proposer fixed = Qwen)
- `H-GQ` vs `R-G` (proposer fixed = GPT-OSS)

---

## Matched compute (R/H family)

Within R and H:

- same `REPAIR_MAX_PROPOSE_TURNS`, `REPAIR_MAX_REPAIR_TURNS`
- same `REPAIR_MAX_TOKENS`, `REPAIR_TEMPERATURE`
- same stop rules (success, repeated identical diagnostics, caps)
- always log in agent metadata: `arm`, models, propose/repair turn counts, `lean_checks`, per-model call counts

Harness additionally records authoritative **USD** via OpenRouter `usage.cost` → budget → `result.json` / `summary.json`.

S is **not** force-matched to R turn structure (S is baseline-faithful). When comparing R vs S, report turn/call/Lean mismatch explicitly.

---

## Env var cheat sheet

| Var | Applies | Default |
|-----|---------|---------|
| `BASELINE_MODEL` | kit S only | `MODEL_A` (Qwen) |
| `BASELINE_MAX_TURNS` | S | 25 |
| `BASELINE_MAX_TOKENS` | S | 12000 |
| `BASELINE_TEMPERATURE` | S | 0.2 |
| `REPAIR_MAX_PROPOSE_TURNS` | R/H | 1 |
| `REPAIR_MAX_REPAIR_TURNS` | R/H | 3 |
| `REPAIR_MAX_TOKENS` | R/H | 12000 |
| `REPAIR_TEMPERATURE` | R/H | 0.2 |

Science arm factories **pin models in code**; do not rely on `BASELINE_MODEL` for S-Q/S-G when using `experiments_agents.s_*`.

---

## Cost logging path (verified in kit source)

1. OpenRouter success body must include numeric `usage.cost` (`re_harness/llm.py`).
2. `BudgetLedger.settle` → event `llm_response` with `actual_cost_usd`.
3. Worker `result.json`: `budget.spent_usd` (authoritative per problem).
4. `summary.json`: `actual_cost_usd` aggregate; per-problem rows include `actual_cost_usd`.
5. `transcript.json` / `events.jsonl`: per-call costs.

**REGISTRY `usd` column:** prefer `summary.json` → `actual_cost_usd` (or problem row).  
Do not reimplement accounting.

**calls_q / calls_g:** count `llm_request` events by model, or read `agent_metadata.calls_q` / `calls_g` from science arms.  
**lean_checks:** `agent_metadata.lean_checks` (science arms) or count `lean_*` events.

---

## Solo Union

Derived only: `U(p) = S-Q(p) OR S-G(p)`.  
No separate best-of-two science arm.
