# Coordination plan

**Status:** experimental protocol agreed 2026-08-25 — begin construction from this document  
**Audience:** coding/research sessions  
**Related:** `PROJECT_STATE.md`, `HANDOFF.md`, `design/SOTA_MULTI_MODEL_MATH_MEMO.md`

Write simply. Prefer measuring over inventing. Prefer a small system graders can read in one sitting.

**Freeze the experimental protocol before optimizing the final submission architecture.**

---

## 1. Objective

### Part One — score

Maximize the number of problems whose final Lean proof is accepted by the comparator.

Per problem:

\[
\text{primary objective}=\mathbf{1}\{\text{comparator accepts}\}
\]

subject to:

\[
\text{OpenRouter cost}\le \$1
\]

and the 8-hour wall-clock cap.

Among systems with similar solve rates, prefer the cheaper and simpler one.

Allowed runtime models:

- Qwen: `qwen/qwen3.5-flash-02-23`
- GPT-OSS: `openai/gpt-oss-120b`

### Part Two — science

Separate three effects:

1. **Base model capability** — what does each model solve alone?
2. **Repair-method benefit** — does targeted Lean-guided repair help when the same model proposes and repairs?
3. **Cross-model benefit** — does switching models at repair time add anything beyond self-repair?

Core question:

> When Lean-gated repair succeeds, is the gain caused by the repair protocol itself, by the second model, or merely by the union of what the two solo models already solve?

### Metric hierarchy

1. **Primary:** comparator pass/fail.
2. **Hard constraint:** cost ≤ $1/problem.
3. **Secondary:** USD, calls, tokens, Lean checks, wall time.
4. Between methods with similar success, prefer lower cost and lower complexity.

---

## 2. What “good” looks like

### Must have

- Working submission agent.
- Solo results for Qwen and GPT-OSS.
- Same-model targeted-repair controls.
- Both handoff directions if budget allows:
  - Qwen → GPT-OSS
  - GPT-OSS → Qwen
- Per-problem success matrix.
- Actual USD cost.
- Call counts and Lean check counts.
- Clear separation between:
  - experimental arms used for scientific claims;
  - final adaptive agent used to maximize score.
- Honest writeup, including a negative cross-model result if that is what the data show.

### Nice to have — only after core experiments

- Small error router.
- One strong transcript/case study.
- Small lemma decomposition after repeated stalls.
- Dual-draft final-agent optimization if it adds accepted problems under budget.

### Do not chase yet

- Multi-agent debate.
- Big blackboard.
- RAG / web tools.
- Training.
- Huge search.
- Back-translation.
- Custom anti-cheat machinery duplicating the comparator.

---

## 3. Working hypothesis

Primary hypothesis:

> Lean diagnostics can serve as a compact, objective coordination signal for targeted proof repair without free-form multi-agent debate.

This is a hypothesis, not a conclusion.

We test it by comparing:

- solo behavior;
- same-model targeted repair;
- cross-model targeted repair.

A useful scientific result is possible even if cross-model handoff does **not** beat self-repair.

---

## 4. Core mechanism — Lean-gated repair

```text
1. Proposer writes a full Lean proof.
2. Lean checks it.
3. If accepted → stop.
4. If rejected → capture:
   - failed proof
   - exact Lean diagnostics
5. Repairer receives the failure context.
6. Repairer produces a corrected proof.
7. Lean checks again.
8. Stop on:
   - success
   - repeated no-progress failure
   - hard call/turn limit
   - budget
```

### Repair-prompt invariant

Every repair prompt should explicitly state:

- do not use `sorry`;
- do not use `admit`;
- do not introduce new axioms or equivalent proof bypasses;
- do not alter the theorem statement to make the problem easier;
- repair the actual proof obligation;
- when the diagnostic is local, prefer a minimal correction.

This is **not** a replacement for the comparator.

It is a cheap behavioral guardrail so the models do not waste calls on solutions we already know cannot be accepted.

### No separate trivial-proof filter for now

Do not build a custom anti-cheat parser unless repository inspection exposes a real gap.

The comparator remains the formal authority.

---

## 5. Experimental conditions

Use names that describe the actual flow.

### 5.1 Solo baselines

| ID | Name | Flow | Purpose |
|---|---|---|---|
| **S-Q** | Qwen Solo | Qwen only | Base Qwen capability |
| **S-G** | GPT-OSS Solo | GPT-OSS only | Base GPT-OSS capability |

Important:

`S-Q` and `S-G` should preserve the supplied single-model baseline behavior as closely as practical.

They are **not** silently redefined to use the new explicit two-role targeted-repair protocol.

Before large runs, inspect and freeze the exact solo-baseline semantics.

---

### 5.2 Same-model repair controls

| ID | Name | Flow | Purpose |
|---|---|---|---|
| **R-Q** | Qwen Self-Repair | Qwen → Lean → Qwen | Measure repair-method benefit without model diversity |
| **R-G** | GPT-OSS Self-Repair | GPT-OSS → Lean → GPT-OSS | Same for GPT-OSS |

Repair stage receives:

- original problem/context;
- previous failed proof;
- exact Lean diagnostics;
- explicit correction instructions.

Primary questions:

\[
R_Q \text{ vs } S_Q
\]

\[
R_G \text{ vs } S_G
\]

Does explicit Lean-conditioned targeted repair improve the corresponding solo behavior?

---

### 5.3 Cross-model handoff

| ID | Name | Flow | Purpose |
|---|---|---|---|
| **H-QG** | Qwen→GPT Handoff | Qwen → Lean → GPT-OSS | Does GPT improve on Qwen self-repair? |
| **H-GQ** | GPT→Qwen Handoff | GPT-OSS → Lean → Qwen | Does Qwen improve on GPT self-repair? |

Primary comparisons:

\[
H_{QG} \text{ vs } R_Q
\]

\[
H_{GQ} \text{ vs } R_G
\]

These comparisons isolate the value of **changing the repair model while keeping the proposer fixed**.

Both directions matter because complementarity may be asymmetric.

---

### 5.4 Derived statistic — Solo Union

Do **not** run a separate best-of-two science condition merely to measure coverage.

Derive per problem:

\[
U(p)=S_Q(p)\lor S_G(p).
\]

`Solo Union` is the union of the independently observed solo successes.

It is useful as a reference, but it is **not evidence of collaboration**.

If later the final agent actually uses two independent drafts under a shared $1 budget, that becomes a separate engineering mechanism to evaluate for submission score.

---

## 6. How to read the results

### Base capability

Compare:

\[
S_Q,\quad S_G.
\]

Ask:

- Which model solves more?
- Which problems are unique wins?
- What is `Solo Union`?

### Repair-method effect

Compare:

\[
R_Q-S_Q
\]

and:

\[
R_G-S_G.
\]

Interpretation:

> Does the explicit targeted-repair protocol help even without model diversity?

### Cross-model effect

Compare:

\[
H_{QG}-R_Q
\]

and:

\[
H_{GQ}-R_G.
\]

Interpretation:

> Holding the proposer fixed, does replacing self-repair with the other model improve the result?

### Candidate collaboration-only wins

Interesting cases satisfy:

\[
U(p)=0
\]

but:

\[
H_{QG}(p)=1
\quad\text{or}\quad
H_{GQ}(p)=1.
\]

These are candidate cases where handoff creates a success not observed in either solo trajectory.

Because sampling may be stochastic, rerun the strongest case-study candidates if budget permits.

---

## 7. Development vs evaluation

Do not tune indefinitely on all sixteen sample problems.

Create and freeze:

```text
S_dev
S_eval
```

Rules:

- tune prompts, routing, call caps, and implementation details on `S_dev`;
- freeze the configuration before evaluating on `S_eval`;
- do not move problems between sets after seeing results;
- record the split in the repo.

The exact split is **not decided in this document**.

Choosing it is a separate task for another agent/session.

---

## 8. Science vs final submission agent

This distinction is essential.

### Experimental arms

```text
S-Q
S-G
R-Q
R-G
H-QG
H-GQ
```

exist to make interpretable scientific comparisons.

Each arm should differ from its control by as little as practical.

### Final adaptive agent

The final submission agent has a different objective:

\[
\text{maximize comparator passes under } \$1.
\]

It may combine mechanisms that the experiments show are useful, for example:

```text
propose
→ Lean
→ self-repair on local error
→ handoff on stall
→ Lean
→ stop
```

or, if data justify it:

```text
two drafts
→ Lean
→ continue from the more viable branch
→ targeted repair
```

The final agent does **not** need to be a clean causal experiment.

It needs to be:

- legal;
- simple;
- reproducible;
- effective.

Do not infer causal claims from the integrated final agent alone.

---

## 9. Optional error routing — only after core data

Do not build a rich router before `S/R/H` results exist.

If routing becomes useful, keep it tiny and operational.

| Bucket | Observable signal | Candidate action |
|---|---|---|
| Local syntax/name/type issue | parse error, unknown name, localized type mismatch | same-model minimal repair |
| Tactic failure | tactic failed / timeout | tactic-focused repair |
| Open goals | proof elaborates but goals remain | gap-focused repair |
| Repeated stall | normalized error/goals remain effectively unchanged | cross-model handoff |
| Unknown | everything else | one generic repair then stop |

`Strategy stall` is a trajectory property, not something to guess from one Lean error.

Kill routing if it does not add accepted problems or useful efficiency.

---

## 10. Spend discipline

Development key hard cap: approximately **$50**.

Rules:

- No large matrix without a line in `experiments/SPEND_PLAN.md`.
- Calibrate actual model costs before full batches.
- Reserve roughly 20–30% for:
  - final clean reruns;
  - important case-study reruns;
  - submission validation.
- Core science has priority over optional architecture ideas.
- Exact exploratory soft caps are chosen only after calibration.

If budget becomes tight, prioritize:

```text
S-Q
S-G
R-Q
R-G
H-QG
H-GQ
```

before:

- blackboard;
- lemma splitting;
- dual-draft optimization;
- richer routing.

---

## 11. Logging

Create:

```text
experiments/
  REGISTRY.md
  SPEND_PLAN.md
  SPLIT.md
  tables/
    master_matrix.md
```

Suggested registry row:

```text
id | date | git | arm | set | pass_count | usd | calls_q | calls_g | lean_checks | wall | output_path | note
```

Suggested master matrix:

| Problem | S-Q | S-G | Union | R-Q | R-G | H-QG | H-GQ |
|---|---:|---:|---:|---:|---:|---:|---:|

Also record per run:

- actual OpenRouter USD;
- token usage if available;
- Lean checks;
- wall-clock time;
- final proof path;
- transcript path;
- git commit;
- configuration;
- short failure note/category.

Never leave Part Two evidence only in chat history.

---

## 12. Execution order

### Phase 0 — freeze infrastructure facts

1. Inspect exact single-model baseline behavior.
2. Verify comparator/judge path.
3. Verify logging.
4. Verify `usage.cost`.
5. Create experiment registry/spend/split/table files.

### Phase 1 — calibration

1. Run one small Qwen calibration.
2. Run the equivalent GPT-OSS calibration.
3. Estimate realistic cost per attempt.
4. Freeze provisional call/turn caps.

### Phase 2 — dev/eval split

Delegate and freeze:

```text
S_dev
S_eval
```

before substantial tuning.

### Phase 3 — solo baselines

Run on `S_dev`:

```text
S-Q
S-G
```

Then derive:

```text
Solo Union = S-Q OR S-G
```

### Phase 4 — same-model targeted repair

Implement and run:

```text
R-Q
R-G
```

### Phase 5 — cross-model handoff

Implement and run:

```text
H-QG
H-GQ
```

Compare:

```text
H-QG vs R-Q
H-GQ vs R-G
```

### Phase 6 — freeze scientific configuration

Once the core behavior is understood:

- freeze prompts;
- freeze caps;
- freeze routing if any;
- freeze handoff rules.

Then evaluate on `S_eval`.

### Phase 7 — build final adaptive agent

Use the evidence to create the simplest high-scoring system.

Only now consider:

- error routing;
- selective self-repair;
- selective handoff;
- dual drafts;
- small lemma decomposition.

### Phase 8 — final run and writeup

Run the frozen final agent cleanly.

Produce:

- per-problem table;
- cost table;
- call counts;
- selected transcripts;
- scientific comparison;
- limitations;
- final `scripts/judge_check.sh`.

---

## 13. Engineering constraints

- Windows tree = git source of truth on this machine:  
  `D:\Mis documentos\Documentos\Verified Mechanism`
- WSL runtime: `~/verified-mechanism` — sync before dual edits.
- Key only in WSL `.env`; never paste it in chat.
- `run.py --problems` needs a set with `manifest.json`.
- Local `LEAN_CONTAINER_MEMORY` patch must be revisited before submission.
- No `git push` without explicit user approval.
- `submission/agent.py` remains provisional until implementation starts.
- Runtime network must remain within task rules.

---

## 14. Working thesis for the PDF

> We study a small Lean-gated repair protocol under a strict per-problem budget. First, we measure Qwen and GPT-OSS alone. Then we separate the effect of targeted Lean-conditioned repair from the effect of changing model at the repair stage. This lets us test whether cross-model handoff provides value beyond self-repair and beyond the observed union of solo capabilities.

If:

\[
R \approx H,
\]

the repair **method** matters more than model diversity.

If:

\[
H_{QG}>R_Q
\]

or:

\[
H_{GQ}>R_G,
\]

there is evidence that the other model contributes additional repair capability in that direction.

A result showing little or no cross-model gain is still scientifically valid.

---

## 15. Explicit non-goals until data force a rethink

- Blackboard as first architecture.
- Debate / society-of-mind.
- External retrieval.
- Back-translation.
- Custom anti-cheat/filter stack duplicating comparator logic.
- Always-on long natural-language plans.
- More than one major architecture upgrade before core results exist.

### Upgrade gate

Only after interpretable results exist for:

```text
S-Q
S-G
R-Q
R-G
H-QG
H-GQ
```

consider:

- ≤4 small verified lemmas;
- dual-draft final-agent optimization;
- richer routing.

Kill an upgrade if it spends budget without adding accepted problems or a clearly useful scientific result.

---

## 16. Immediate next actions

1. Read this file + `HANDOFF.md` + `PROJECT_STATE.md`.
2. Inspect and freeze exact solo-baseline semantics.
3. Create:
   - `experiments/REGISTRY.md`
   - `experiments/SPEND_PLAN.md`
   - `experiments/SPLIT.md`
   - `experiments/tables/master_matrix.md`
4. Verify actual OpenRouter `usage.cost` logging.
5. Run matched Qwen/GPT-OSS calibration.
6. Delegate and freeze `S_dev` / `S_eval`.
7. Run `S-Q` and `S-G`.
8. Implement/run `R-Q` and `R-G`.
9. Implement/run `H-QG` and `H-GQ`.
10. Do not build blackboard, debate, or back-translation.

---

## 17. One-figure summary

```text
SCIENCE

Base capability:
  S-Q   Qwen Solo
  S-G   GPT-OSS Solo
    └── Solo Union = S-Q OR S-G   (derived, not a new run)

Repair method:
  R-Q   Qwen → Lean → Qwen
  R-G   GPT  → Lean → GPT

Cross-model handoff:
  H-QG  Qwen → Lean → GPT
  H-GQ  GPT  → Lean → Qwen

Key comparisons:
  R-Q   vs S-Q       ← does targeted repair help Qwen?
  R-G   vs S-G       ← does targeted repair help GPT?
  H-QG  vs R-Q       ← does GPT add value after Qwen?
  H-GQ  vs R-G       ← does Qwen add value after GPT?

PRIMARY:
  comparator accepted? 0/1

HARD CONSTRAINT:
  cost <= $1/problem

SECONDARY:
  USD, calls, tokens, Lean checks, wall time


FINAL ENGINEERING

Use the scientific results to build the simplest adaptive agent
that maximizes accepted problems under the $1 cap.
```
