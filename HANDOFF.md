# HANDOFF

## Read first

Before doing anything:

1. Read `PROJECT_STATE.md`.
2. Read `docs/AGENT_API.md`.
3. Read `RULES.md`.
4. Inspect the existing baseline implementation.
5. Do not infer missing execution constraints.

---

## Current phase

**Phase 0 — Repository understanding**

We have not yet selected a final multi-model architecture.

The immediate goal is to understand the supplied infrastructure and establish a clean baseline.

---

## Current project thesis

We are investigating whether coordination between the fixed Qwen and GPT-OSS models can increase the probability of producing Lean-accepted proofs relative to either model alone.

The main scientific question is:

> When collaboration changes a problem from failure to success, what information or capability passed between the models caused the improvement?

Lean compiler feedback is considered a potentially important coordination signal.

---

## Current architectural candidates

### Candidate A — Minimal compiler-feedback loop

```text
Model A
  ↓
candidate Lean proof
  ↓
Lean
  ↓
compiler result
  ↓
Model B diagnoses/repairs
  ↓
Lean
```

This should be implemented/tested before more complex architectures.

### Candidate B — Structured lemma blackboard

Models collaborate over explicit intermediate lemmas and their Lean verification state.

Status:

**Hypothesis only. Do not implement until simpler baselines exist unless new evidence strongly justifies it.**

---

## Immediate tasks

Perform these in order:

1. Inspect repository structure.
2. Read `docs/AGENT_API.md`.
3. Read `RULES.md`.
4. Inspect `submission/agent.py` or supplied baseline.
5. Inspect several representative `sample-problems/`.
6. Determine exactly how Lean is invoked.
7. Determine exactly how model calls are invoked and metered.
8. Run the supplied baseline unchanged.
9. Run `scripts/judge_check.sh`.
10. Record every discovered constraint in `PROJECT_STATE.md`.

---

## Do not do yet

Do not:

- build a complicated multi-agent framework;
- assume Qwen or GPT-OSS is better at a particular role;
- optimize prompts before establishing measurements;
- change evaluator-facing interfaces;
- run large experiment matrices before logging is reliable;
- silently modify global architecture decisions.

---

## After repository inspection

The next engineering milestone is:

**structured experiment instrumentation**

We need to record per run:

```text
experiment_id
problem_id
condition
model_calls
models_used
cost
wall_time
lean_attempts
lean_results
success
final_proof
transcript/log path
git_commit
configuration
```

Then run:

1. Qwen solo baseline.
2. GPT-OSS solo baseline.
3. Minimal collaboration.

---

## Before ending this session

Update this file with:

- what was inspected;
- what was learned;
- commands that successfully ran;
- commands that failed;
- files changed;
- unresolved questions;
- exact next action.

Replace stale information rather than indefinitely appending history.

Long-term knowledge belongs in `PROJECT_STATE.md` or experiment logs.

---

## Next action

**Read `docs/AGENT_API.md` and `RULES.md`, then report the concrete runtime contract before modifying the agent.**
