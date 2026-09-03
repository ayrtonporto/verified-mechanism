# Verified Mechanisms Take-Home Harness

This repository contains the infrastructure for the Verified Mechanisms
research engineer take-home assignment. The applicant is responsible for
implementing an agent in Python. The harness provides the surrounding runtime:
OpenRouter access, per-problem budget accounting, durable logs, concurrent
problem scheduling, Dockerized Lean checking, and final Comparator scoring.

Lean, Mathlib, compiled Mathlib artifacts, the JSON REPL, `lean4export`, and
Comparator are supplied through a pinned Docker image. Applicants do not need a
host Lean, Lake, or Mathlib installation.

## This submission (applicant)

**Attribution.** This repository builds on the provided Verified Mechanisms
take-home kit (`VerifiedMechanisms/re-takehome`): the harness, runner, Lean
container, sample problems, `RULES.md`, and Comparator scoring are the kit's.
The **two-model coordination layer is my own work**.

**Entrypoint.** The graded agent is `submission/agent.py` (`create_agent`),
implementing the interface in `docs/AGENT_API.md`.

**Design in one paragraph.** The agent is a finite, Lean-gated escalation
ladder that treats Lean as a coordination signal at every step, not only as the
final judge: each candidate is compiled, its structured diagnostics drive a
repair, and any cross-model handoff is seeded with the exact compiler message.
Rungs run cheapest-first — a zero-model tactic sweep, then same-model repair
champions (Qwen, then GPT-OSS), then a seeded cross-model handoff, then an
independent slot/combine fallback, then bounded program/bridge and residual
lemma-banking stages. A strict integrity and anti-tautology guard admits only
substantive proofs. The accompanying PDF write-up explains the method and the
empirical study.

**Graded execution path.** The judged entrypoint reaches only these modules:

- `submission/agent.py` — the finite ladder (entrypoint).
- `experiments_agents/`: `common`, `repair`, `hintedprover`, `nearmiss`,
  `nm_pf`, `multitheorem`, `bridgeportfolio`, `programportfolio`,
  `verified_progress`, `error_router`, `residual_hygiene`, `candidate_guard`.
- `src/re_harness/` (kit runtime; only `worker.py` is modified, to inject a
  reserved `__manifest__` used by the acceptance guard).

Everything else under `experiments_agents/` (the six Part-Two science arms and
exploratory prototypes) and the extra `tests/` are **development scaffolding not
executed by the graded entrypoint**, kept for reproducibility of the Part-Two
study.

**LLM tools.** Coding assistants (Claude Code / Codex-class) were used for
scaffolding, debugging, and drafting; runtime solving uses only the two mandated
OpenRouter models. This is also disclosed in the submission form.

## Requirements

- Docker Engine or Docker Desktop
- Python 3.11 or newer
- Approximately 20 GB of free disk space
- At least 8 GB of RAM for one worker

Each additional worker may require roughly 5 GB of additional memory. Linux,
WSL2, Intel Macs, and Apple Silicon Macs are supported.

## Setup

Run the setup script from the repository root:

```bash
bash scripts/setup.sh
```

Create a local environment file and add the OpenRouter API key:

```bash
cp .env.example .env
```

The `.env` file is ignored by Git. During judging, exported environment
variables take precedence over values in `.env`.

## Implementing the Agent

Applicants implement `SubmissionAgent.solve` in `submission/agent.py`.

```python
async def solve(problem: Problem, services: Services) -> AgentResult:
    ...
```

The harness supplies three services:

- `await services.llm.complete(...)` for restricted, budgeted, logged
  OpenRouter calls
- `await services.lean.check_file(source)` for checking a complete Lean file in
  the networkless Lean container
- `services.checkpoint(source)` for preserving a candidate solution during a
  long run

The agent may use any internal design that remains problem-agnostic and follows
the assignment rules. See `docs/AGENT_API.md` for the full interface.

## Running the Harness

Run the default submission agent with:

```bash
.venv/bin/python run.py --problems sample-problems --out outputs
```

Each invocation creates a fresh run directory:

```text
outputs/submission/<run-name>/
```

The run name is generated from the current UTC timestamp.

To resume a previous run for the selected agent:

```bash
.venv/bin/python run.py \
  --problems sample-problems \
  --out outputs \
  --resume latest
```

You may also resume a specific run name:

```bash
.venv/bin/python run.py \
  --problems sample-problems \
  --out outputs \
  --resume 20260819T120000Z
```

## Reference Baseline

A minimal reference agent is available in `baselines/simple_agent.py`. It uses a
single model-driven repair loop with Lean feedback and stops when a candidate
passes the Lean REPL check.

Run it with:

```bash
.venv/bin/python run.py \
  --problems sample-problems \
  --out outputs \
  --agent baselines.simple_agent:create_agent
```

Baseline runs are written under:

```text
outputs/baseline/<run-name>/
```

## Bridge-first hard-goal stage

The submission agent keeps the cheap tactic/direct stages, then escalates unresolved
single-theorem goals through `experiments_agents.bridgeportfolio`. This stage:

1. samples several short portfolios of strategic lemma statements;
2. checks a strict, `sorry`-free bridge from each portfolio to the locked original goal;
3. ranks only bridge-verified routes;
4. proves each immutable lemma with Qwen first and GPT-OSS repairs second; and
5. recursively applies the same procedure to the first blocked lemma, to a bounded depth.

The model only supplies proof bodies. The agent reconstructs every candidate under a
machine-owned theorem header, so repairs cannot weaken or rename a goal. Internal lemma
files are never checkpointed; only a strict proof of the original challenge is preserved.

For challenges containing answer definitions or several dependent declarations,
`experiments_agents.programportfolio` now coordinates the same theorem solver at program
level. It first proposes a small portfolio for each locked definition hole, accepts only
replacements that elaborate in Lean, and then proves downstream theorems with those
definitions present. Wrong-but-well-typed answers are rejected when their dependent
theorems fail, and a solved sibling theorem is available on a bounded retry pass. The
submission agent runs this dependency-aware stage before its older independent-slot
fallback.

The defaults are tuned for the eight-hour, one-dollar problem budget and can be adjusted
for controlled experiments with `BP_MAX_DEPTH`, `BP_PORTFOLIO_CALLS`,
`BP_ROUTES_PER_CALL`, `BP_MAX_ROUTES_CHECKED`, `BP_MAX_ROUTES_TRIED`, `BP_MAX_LEMMAS`,
`BP_Q_ATTEMPTS`, `BP_G_ATTEMPTS`, `BP_CHECK_TIMEOUT_S`, and `BP_MIN_TIME_S`.

An earlier homogeneous closure test scored 4/7 by the comparator but only 3/7
substantive, because a Putnam answer-set definition made the downstream theorem
tautological. Definition non-circularity and preservation of the previous solver's
time budget are therefore treated as required acceptance gates, not optional
scoring refinements — enforced by the guard in
`experiments_agents/candidate_guard.py`.

The baseline can be configured with:

- `BASELINE_MODEL`
- `BASELINE_MAX_TURNS`
- `BASELINE_MAX_TOKENS`
- `BASELINE_TEMPERATURE`

## Parallel Execution

Use `--n-workers` to run independent problems concurrently:

```bash
.venv/bin/python run.py \
  --problems sample-problems \
  --out outputs \
  --n-workers 2
```

Each worker receives its own process, budget ledger, deadline, output
directory, and Lean container. The value of `--n-workers` does not create
additional model calls within a single problem.

## Checks

Run the no-key smoke test:

```bash
bash scripts/smoke_test.sh
```

Before submitting, run the judging contract check:

```bash
bash scripts/judge_check.sh
```

## Output Artifacts

For each problem, the runner writes:

- `solution.lean`
- `result.json`
- `transcript.json`
- `events.jsonl`
- `checkpoint.json`
- `worker-config.json`

The run directory also contains:

- `run.json`
- `summary.json`

The `events.jsonl` file is append-only and flushed incrementally. The
`transcript.json` file is derived from those events and contains the full LLM
requests, responses, token usage, costs, timings, and errors with secrets
redacted.

To rescore saved solutions, pass the concrete run directory:

```bash
bash scripts/rescore.sh outputs/submission/20260819T120000Z
```

## Scoring

A problem receives one point when all of the following conditions hold:

- Comparator accepts every required declaration.
- Numeric answer declarations, when present, have valid literal bodies.
- Actual OpenRouter spend is at most `$1.00`.
- The problem finishes within its deadline.

Model participation is reported in `result.json`. It is reviewed separately
from the mechanical one-point score.

See `RULES.md` for the complete assignment rules.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `RULES.md` | Assignment rules, budgets, and judging behavior |
| `submission/agent.py` | Applicant implementation |
| `baselines/` | Reference agent implementations |
| `src/re_harness/` | Runner, services, accounting, logs, and evaluator |
| `sample-problems/` | Public problems and versioned manifest |
| `docker/` | Source for the Lean runtime image |
| `docs/` | Agent API, setup, artifacts, and security model |
| `scripts/` | Setup, smoke test, rescore, and judging checks |
