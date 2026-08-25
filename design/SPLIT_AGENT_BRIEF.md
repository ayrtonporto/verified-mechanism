# Split agent brief — freeze `S_dev` / `S_eval`

**Status:** ready to hand to a planning agent  
**Authority:** `design/COORDINATION_PLAN.md` §7 + §11–12  
**Spend:** **$0** — no model runs, no Lean batches, no OpenRouter calls  
**Output of record:** `experiments/SPLIT.md` (create/update; do not leave the split only in chat)

---

## Mission

Propose and freeze a **train/dev vs held-out eval split** of the 16 sample problems so we can:

1. **Tune** prompts, caps, and small implementation details on a development set.
2. **Evaluate** the frozen scientific configuration on a held-out set **once**.
3. Avoid the failure mode: tune on all 16, then report the same 16 as “results”.

This agent does **not** implement arms, does **not** run baselines, and does **not** choose the final submission architecture.

---

## Three different “sets” (do not conflate)

| Name | Role | Size (guidance) | When used |
|------|------|-----------------|-----------|
| **Calib** | Machine + cost sanity only | 1 problem (`p01_linear`) | Builder Phase 1 (Qwen already done; GPT-OSS twin only) |
| **`S_dev`** | Tune + iterate + read failures | ~8–10 problems | After calib; all core arms while developing |
| **`S_eval`** | Frozen scientific report numbers | ~6–8 problems | After config freeze; **one** clean pass per arm |

Rules from the coordination plan:

- Tune on `S_dev` only.
- Freeze config **before** `S_eval`.
- **Do not move problems between sets after seeing arm results.**
- Record the split in the repo (`experiments/SPLIT.md`).
- The exact membership is **this agent’s job**; the coordination plan deliberately left it open.

**Calib is not a third scientific stratum.**  
`p01_linear` may also sit in `S_dev` (recommended) so the easy anchor appears in matrices; calib runs are still logged separately in REGISTRY.

---

## Hard constraints

1. **Universe:** exactly the 16 ids in `re-takehome-main/sample-problems/manifest.json`.
2. **Partition:** every problem in **exactly one** of `S_dev` or `S_eval` (calib may reuse a dev id; it is not a separate exclusive bucket).
3. **No leakage protocol:**
   - Do not use future arm outcomes to re-split.
   - Do not peek at model transcripts from scientific arms to reshuffle.
   - You **may** read `problem.md`, `challenge.lean`, and manifest metadata (theorem/answer names).
4. **No paid work.** Classification is by inspection + stratified rules, not by running solvers.
5. **Stratify, don’t randomize blindly.** With n=16, a pure coin-flip can put both Putnams in eval and all easy algebra in dev.
6. **Both sets must support the science questions:**
   - base capability (S-Q vs S-G)
   - repair-method (R vs S)
   - cross-model handoff (H vs R)
   - chance of **unique solo wins** and **hard failures** in each set
7. **Prefer interpretable strata labels** over opaque hashes.
8. **Write simply.** Ayrton should be able to accept/reject the split in one screen.

---

## What “good split” means here

Not ML accuracy. The split is good if:

1. **`S_dev` is large enough to iterate** without burning the whole key on eval reruns.
2. **`S_eval` is large enough to be a real check** (not 2 toy problems).
3. **Difficulty mix is similar** in both sets (easy / mid / hard present in each).
4. **Problem-type mix is similar** in both sets (see strata below).
5. **Answer-style problems** (fill `*_answer` / solution definition) appear in **both** sets.
6. **Multi-goal / contest-hard** items are not all dumped into one side.
7. **Default bias:** slightly larger `S_dev` than `S_eval` (tune more, evaluate cleaner), unless you justify 50/50.

Suggested target (not mandatory if you justify otherwise):

```text
S_dev  : 9 or 10 problems
S_eval : 7 or 6 problems
Calib  : p01_linear (also in S_dev)
```

---

## Strata to balance (use these labels)

Inspect each problem and assign tags. Minimum tag set:

### A. Difficulty (ordinal, your judgment from statement + Lean shape — not from solver runs)

| Tag | Heuristic |
|-----|-----------|
| **E** easy | short calculation / standard one-liner inequality; few moving parts |
| **M** medium | needs a real idea or multi-step algebra/number theory; still contest-entry |
| **H** hard | IMO/RMO/Putnam flavor, multi-part, search for structure, or heavy formalization |

### B. Family / type

| Tag | Examples in this corpus |
|-----|-------------------------|
| **alg-eq** | linear/frac identities, sum of squares from elementary relations |
| **ineq** | AM-GM style, symmetric inequalities |
| **nt-div** | gcd/Mersenne, modular order, divisibility |
| **answer-num** | must fill numeric `*_answer` literal + prove |
| **answer-obj** | must fill a solution definition (pairs/sum closed form), not only a scalar |
| **dioph** | integer/prime solutions of equations |
| **analysis-seq** | sequences / infinite-feeling bounds |
| **multi-thm** | more than one theorem must pass (e.g. p09 a+b) |

### C. Formalization load (optional but useful)

| Tag | Heuristic |
|-----|-----------|
| **F-low** | statement close to a few Mathlib tactics |
| **F-mid** | needs care with types/casts/induction but standard |
| **F-high** | long statement, multiple claims, or awkward encoding |

---

## Corpus catalog (starting point for the agent)

Use this as a **scratch prior**. You must still open each `problem.md` / `challenge.lean` and may correct tags.

| id | Prior difficulty | Prior type tags | Notes |
|----|------------------|-----------------|-------|
| `p01_linear` | E | alg-eq | **Calib anchor**; keep in `S_dev` |
| `p02_frac_cancel` | E | alg-eq | easy algebraic simplification |
| `p03_sq_ge_two_ab` | E–M | ineq | classic rearrangement/AM-GM |
| `p04_sum_sq` | E–M | alg-eq | elementary identity |
| `p05_gcd_mersenne` | M | nt-div | gcd of Mersenne numbers |
| `p06_pow_mod` | M | nt-div, answer-num | last two digits; fill answer |
| `p07_least_divisible` | M–H | nt-div, answer-num | least n + optimality |
| `p08_sum_products` | M | ineq | symmetric ineq under a+b+c=3 |
| `p09_imo1964` | H | nt-div, multi-thm | two theorems required |
| `p10_factorial_pow` | M–H | answer-num | largest n with n! < 3^n; universal bound |
| `rmo_2000_2` | H | dioph | positive integer solutions |
| `rmo_2000_3` | H | analysis-seq | sequence inequality |
| `rmo_2000_6` | H | nt-div, multi-thm? | two minimization parts (check Lean) |
| `rmo_2001_2` | H | dioph, nt-div | primes + quadratic form square |
| `putnam_2018_a1` | H | answer-obj, dioph | all positive pairs |
| `putnam_2020_a2` | H | answer-obj | binomial sum closed form |

**Balance checklist (both sets should roughly satisfy):**

- ≥1 easy (E)
- ≥2 medium (M)
- ≥2 hard (H) — if eval is smaller, ≥1–2 hard still required
- ≥1 `answer-num` or `answer-obj`
- ≥1 pure inequality **or** pure algebra identity
- ≥1 number-theory / divisibility
- Not all Putnams+IMOs on the same side if the other side is only p01–p04

---

## Method the agent must follow

### Step 1 — Inventory ($0)

For each of the 16 problems, record in a working table:

- id  
- 1-line math summary  
- difficulty E/M/H + confidence  
- type tags  
- `# theorems` / has numeric answer? / has solution def? (from manifest + Lean)  
- any special catch (multi-part, IsLeast/IsGreatest, etc.)

### Step 2 — Propose 2 candidate splits

Produce **two** alternatives:

| Candidate | Intent |
|-----------|--------|
| **A — Stratified 10/6 or 9/7** | Default recommended shape |
| **B — More conservative eval** | Slightly harder or more diverse `S_eval` if A looks dev-heavy |

For each candidate: list ids, stratum counts, and risks.

### Step 3 — Pick one and freeze

Choose A or B (or a named hybrid) with a short justification.

Write **`experiments/SPLIT.md`** as the freeze document (template below).

### Step 4 — Stop

Do not implement agents. Do not run models. Do not edit coordination science arms.

If user rejection is likely on one controversial placement (e.g. both Putnams), call it out explicitly.

---

## Deliverable: `experiments/SPLIT.md` template

The agent must create/update this file:

```markdown
# Problem split (frozen)

**Status:** proposed | accepted  
**Date:** YYYY-MM-DD  
**Agent/session:** …  
**Authority:** design/COORDINATION_PLAN.md §7, design/SPLIT_AGENT_BRIEF.md

## Rule

- Tune only on `S_dev`.
- Freeze prompts/caps/arm code before `S_eval`.
- Never move ids after scientific arm results are seen.
- Calib = `p01_linear` only (cost/runtime sanity); also member of `S_dev`.

## Calib

- `p01_linear`

## S_dev (n=…)

- id
- …

## S_eval (n=…)

- id
- …

## Stratum counts

| Stratum | S_dev | S_eval |
|---------|------:|-------:|
| E | | |
| M | | |
| H | | |
| answer-* | | |
| ineq | | |
| nt-div | | |
| dioph/contest | | |

## Per-problem tags

| id | set | diff | tags | note |
|----|-----|------|------|------|
| … | dev/eval | E/M/H | … | … |

## Why this split

3–8 bullets. Mention what each set is for and the main balance tradeoff.

## Rejected alternative (short)

What was candidate B and why it lost.

## Non-goals

- Not a difficulty leaderboard from model runs
- Not the final holdout used by the lab (private)
- Not a license to tune on S_eval
```

Also append a one-screen summary in the agent’s final chat report.

---

## Explicit non-goals

- Running S-Q/S-G/R/H to “see which are hard” before splitting  
- Using external contest ratings as ground truth without reading the Lean file  
- Creating more than two scientific sets (no nested cross-validation with n=16)  
- Leaving hard problems only in dev “to practice” and easy-only eval  
- Changing `design/COORDINATION_PLAN.md` science definitions  
- Spend > $0  

---

## Relationship to the builder

| Agent | Job | Spend |
|-------|-----|-------|
| **Builder** (`design/BUILDER_BRIEF.md`) | arms + registry + **only** GPT-OSS×p01 calib | ~calib only |
| **Split agent** (this brief) | freeze `S_dev` / `S_eval` in `experiments/SPLIT.md` | **$0** |

Order preference:

```text
1) Split agent freezes SPLIT.md          ($0)
2) Builder Phase 0 docs + arm code       ($0)
3) Builder Phase 1 GPT-OSS × p01 calib   (small $)
4) Later: run arms on S_dev, then freeze config, then S_eval
```

If builder already created an empty `SPLIT.md` placeholder, **overwrite** it with the freeze (or mark Status: proposed pending user accept).

User should **accept** the split (Status → accepted) before large `S_dev` matrices.

---

## Copy-paste prompt for the split agent

```text
You are the SPLIT agent for the Verified Mechanisms RE take-home.

Authority:
- design/COORDINATION_PLAN.md §7 (S_dev / S_eval)
- design/SPLIT_AGENT_BRIEF.md

Spend: $0. No OpenRouter, no Lean experiment batches, no arm runs.

Goal:
1) Inventory all 16 problems under re-takehome-main/sample-problems/
   (read problem.md, challenge.lean, manifest.json).
2) Tag each with difficulty E/M/H and type strata from the brief.
3) Propose two stratified splits (dev-heavy vs alternative).
4) Pick one and write experiments/SPLIT.md using the template in the brief.
5) Put p01_linear in calib AND in S_dev.
6) Balance easy/mid/hard and answer-style vs proof-only across both sets.
7) Do not move problems based on model results (there should be none).
8) Do not implement agents. Do not edit submission/agent.py.

Windows SoT: D:\Mis documentos\Documentos\Verified Mechanism

Deliver:
- experiments/SPLIT.md frozen as Status: proposed
- chat summary: n_dev, n_eval, lists, stratum table, risks, why not the other candidate
```

---

## One-line north star

**Hold out a stratified `S_eval` before you fall in love with prompts on the full sample set.**
