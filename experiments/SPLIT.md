# Problem split (frozen)

**Status:** proposed  
**Date:** 2026-08-25  
**Agent/session:** Codex split-agent session; local statement/Lean inspection only  
**Authority:** `design/COORDINATION_PLAN.md` §7, `design/SPLIT_AGENT_BRIEF.md`

The membership below is frozen against empirical reshuffling. Change `Status` to
`accepted` only after user review and before substantial `S_dev` matrices begin.

## Rule

- Tune only on `S_dev`.
- Freeze prompts, caps, routing, and arm code before `S_eval`.
- Run each frozen scientific arm on `S_eval` once.
- Never move ids after scientific arm results or transcripts are seen.
- Calib = `p01_linear` only (cost/runtime sanity); it is also a member of `S_dev`.

## Calib

- `p01_linear`

## S_dev (n=9)

- `p01_linear`
- `p03_sq_ge_two_ab`
- `p05_gcd_mersenne`
- `p06_pow_mod`
- `p09_imo1964`
- `p10_factorial_pow`
- `rmo_2000_2`
- `rmo_2000_3`
- `putnam_2018_a1`

## S_eval (n=7)

- `p02_frac_cancel`
- `p04_sum_sq`
- `p07_least_divisible`
- `p08_sum_products`
- `rmo_2000_6`
- `rmo_2001_2`
- `putnam_2020_a2`

## Stratum counts

Difficulty is judged from the mathematical statement and Lean target only, not
from solver outcomes. `dioph/contest` counts named IMO/RMO/Putnam items or an
explicit Diophantine classification.

| Stratum | S_dev | S_eval |
|---------|------:|-------:|
| E | 2 | 2 |
| M | 2 | 2 |
| H | 5 | 3 |
| answer-* | 3 | 2 |
| alg-eq | 1 | 2 |
| ineq | 1 | 1 |
| nt-div | 3 | 3 |
| dioph/contest | 4 | 3 |
| F-high | 5 | 4 |

## Per-problem inventory and tags

Confidence refers to the E/M/H judgment. `F-*` is formalization load.

| id | set | one-line math summary | diff (confidence) | tags | targets / special catch |
|----|-----|-----------------------|-------------------|------|-------------------------|
| `p01_linear` | dev | Solve one real linear equation. | E (high) | alg-eq, F-low | 1 theorem; calib anchor. |
| `p02_frac_cancel` | eval | Simplify a fixed rational expression over the reals. | E (high) | alg-eq, F-low | 1 theorem; concrete arithmetic. |
| `p03_sq_ge_two_ab` | dev | Prove `a² + b² ≥ 2ab`. | E (high) | ineq, F-low | 1 theorem; standard square inequality. |
| `p04_sum_sq` | eval | Derive `x² + y²` from `x+y` and `xy`. | E (high) | alg-eq, F-low | 1 theorem; elementary identity. |
| `p05_gcd_mersenne` | dev | Compute a gcd of two fixed Mersenne numbers. | M (medium) | nt-div, F-mid | 1 theorem; large powers inside `Nat.gcd`. |
| `p06_pow_mod` | dev | Compute the last two digits of `7^2026`. | M (high) | nt-div, answer-num, F-mid | 1 theorem + numeric answer definition. |
| `p07_least_divisible` | eval | Find the least positive `n` satisfying a divisibility condition. | M (medium) | nt-div, answer-num, F-high | 1 theorem + numeric answer; `IsLeast` requires witness and global lower bound. |
| `p08_sum_products` | eval | Bound `ab+bc+ca` under a positive fixed sum. | M (high) | ineq, F-mid | 1 theorem; symmetric real inequality. |
| `p09_imo1964` | dev | Characterize powers of two modulo 7 and rule out the `+1` case. | H (high) | nt-div, multi-thm, F-high | 2 theorems must pass. |
| `p10_factorial_pow` | dev | Find the greatest `n` with `n! < 3^n`. | H (high) | answer-num, F-high | 1 theorem + numeric answer; `IsGreatest` needs a universal upper-bound proof. |
| `rmo_2000_2` | dev | Solve a cubic equation in positive naturals. | H (high) | dioph, F-high | 1 theorem; natural subtraction makes the encoding delicate. |
| `rmo_2000_3` | dev | Bound harmonic-weighted sums of a decreasing positive sequence. | H (high) | analysis-seq, F-high | 1 theorem; quantified hypotheses and conclusion over finite sums. |
| `rmo_2000_6` | eval | Minimize `ab` under two different power-divisibility constraints. | H (high) | nt-div, multi-part, F-high | 1 theorem containing 2 `IsLeast` conjuncts. |
| `rmo_2001_2` | eval | Classify prime pairs making a quadratic form a square. | H (high) | dioph, nt-div, F-high | 1 iff theorem with three solution branches. |
| `putnam_2018_a1` | dev | Classify positive integer pairs in a reciprocal equation. | H (high) | answer-obj, dioph, F-high | 1 theorem + solution-set definition; integer/rational casts. |
| `putnam_2020_a2` | eval | Evaluate a parameterized binomial sum. | H (high) | answer-obj, comb-sum, F-high | 1 theorem + solution-function definition. |

## Why this split

- A 9/7 split leaves enough development cases to iterate while preserving a
  seven-problem holdout with a meaningful denominator.
- Each set has exactly two E and two M problems; the eight H problems divide
  5/3, close to the set-size ratio.
- Answer filling is present on both sides (3/2), including one `answer-obj`
  problem and at least one numeric-answer problem in each set.
- Pure inequalities split 1/1, and evaluation also has two elementary algebra
  identities; neither side is only number theory or only contest-hard work.
- `nt-div` splits 3/3. Named contest/Diophantine items split 4/3, and the two
  Putnam problems are separated.
- High formalization load splits 5/4, so both sets can expose unique solo wins,
  repair wins, handoff gains, and hard failures.
- `p01_linear` stays in `S_dev` as the reusable calib anchor, while calib runs
  remain separately labelled in `REGISTRY.md`.

Main judgment call: `p07_least_divisible` is tagged M but borderline M/H because
its `IsLeast` proof is formally demanding. That label may be debated before any
arm results are inspected; its set membership must not be changed afterward.

## Rejected alternative (B — smaller, harder eval)

Candidate B used a 10/6 split:

- `S_dev`: `p01_linear`, `p02_frac_cancel`, `p03_sq_ge_two_ab`,
  `p05_gcd_mersenne`, `p06_pow_mod`, `p09_imo1964`, `p10_factorial_pow`,
  `rmo_2000_2`, `rmo_2001_2`, `putnam_2020_a2`.
- `S_eval`: `p04_sum_sq`, `p07_least_divisible`, `p08_sum_products`,
  `rmo_2000_3`, `rmo_2000_6`, `putnam_2018_a1`.

| B stratum | S_dev | S_eval |
|------------|------:|-------:|
| E / M / H | 3 / 2 / 5 | 1 / 2 / 3 |
| answer-* | 3 | 2 |
| ineq | 1 | 1 |
| nt-div | 4 | 2 |
| dioph/contest | 4 | 3 |

B gives a diverse and relatively hard holdout, but it loses because `S_eval`
has only six items, only one easy anchor, and a 4/2 number-theory imbalance. Its
score would be more sensitive to a few high-formalization failures than A's.

## Non-goals

- Not a difficulty leaderboard from model runs.
- Not the final holdout used by the lab (private).
- Not a license to tune on `S_eval`.
