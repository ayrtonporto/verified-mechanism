# S_dev iteration results — RESULTS ARE POOR, WE NEED NEW IDEAS

**To the next agent:** you already have the project context (see
`EXPERIMENT_S_dev_matrix.md`). This file is **only the results** of the first
iteration round. Bottom line up front: **the results are bad.** The set of
solvable problems did not grow, the three hard problems are unsolved by *every*
mechanism, and the best arm is stuck at 5/9. **We need genuinely new ideas.**

Date: 2026-08-26. All runs on `S_dev` (9 problems), fixed kit, one run each
(high variance — see caveat).

---

## What was tried this round

1. **Hardening** of the repair loop (universal): best-so-far return, integrity
   gate (a REPL-accepted candidate that altered the challenge doesn't count),
   tolerant stall, root-diagnostic preservation, provenance. (A first version
   regressed by re-seeding repair from the best instead of the latest candidate —
   fixed to seed-latest / return-best.)
2. Four **new universal mechanisms** (same behavior for every problem — no
   per-problem or per-category routing):
   - **AT-G** — auto-tactics: a zero-model-cost sweep that tries a fixed Mathlib
     tactic battery (`simp_all, omega, norm_num, decide, nlinarith, positivity,
     aesop, …`) before/around the model, plus a tactic menu in the prompts.
   - **SK-G** — skeleton / sorry-first: propose a `have … := by sorry` skeleton
     whose structure elaborates, then fill the holes (extra repair turns).
   - **BON-G** — best-of-N: 8 independent proposals with a rotating fixed
     strategy menu at higher temperature; first Lean-accepted wins.
   - **PF-GQ** — planner→formalizer: GPT-OSS writes a natural-language proof
     plan, Qwen formalizes it, then hardened repair.

Models are fixed: **Q = qwen/qwen3.5-flash-02-23**, **G = openai/gpt-oss-120b**.

---

## Full results (S_dev, per problem)

`1` = comparator-accepted. `1*` = solved by the **deterministic tactic sweep**
(zero model calls, variance-proof).

| Problem | Diff | S-Q | S-G | R-Q | R-G | H-QG | H-GQ | AT-G | SK-G | BON-G | PF-GQ |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| p01_linear | E | 1 | 1 | 1 | 1 | 1 | 1 | 1* | 1* | 1* | 1* |
| p03_sq_ge_two_ab | E | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 0 |
| p05_gcd_mersenne | M | 0 | 1 | 0 | 1 | 0 | 0 | 1* | 1* | 1* | 1* |
| p06_pow_mod | M | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| p09_imo1964 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| p10_factorial_pow | H | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 1 |
| rmo_2000_2 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rmo_2000_3 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| putnam_2018_a1 | H | 0 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| **TOTAL** | | **3** | **4** | **4** | **5** | **4** | **3** | **4** | **5** | **5** | **4** |

Costs per new arm: AT-G $0.039 · SK-G $0.043 · BON-G $0.058 · PF-GQ $0.056.
Cost is NOT a constraint (~$0.7 total spent). Wall time is the constraint: the
runner box is small (2 CPUs, 14 GB RAM, N_WORKERS=1); each Lean check pays a
~100 s cold Mathlib import; each GPT-OSS call ~70 s. An arm ≈ 80–120 min.

---

## Why the results are bad

1. **The frontier did not move.** Union over **all ten** arms (old + new) is still
   **6/9**: `{p01, p03, p05, p06, p10, putnam_2018_a1}` — identical to the
   baseline union. **No new problem was unlocked by any new mechanism.**
2. **The three hard problems are unsolved by everything:** `p09_imo1964`
   (powers of two mod 7, ∀n), `rmo_2000_2` (a cubic Diophantine in ℕ),
   `rmo_2000_3` (harmonic-weighted sums over a decreasing sequence). Zero hits
   across all arms, all mechanisms.
3. **Best single arm is stuck at 5/9** (R-G, SK-G, BON-G). Skeleton, best-of-N,
   and planner→formalizer only re-shuffle or match existing solves; none beats R-G.
4. **High run-to-run variance.** The same R-G config scored 5/9 then 2/9 on two
   runs — single-run numbers above are noisy (±). Any claimed +1 is inside the
   noise.

**The one durable, variance-proof win:** the deterministic tactic sweep solves
`p01` (`nlinarith`) and `p05` (`simp_all`) for free in every arm. That is a solid
floor for the final agent, but it is not progress on the hard problems.

---

## What we need from you

**New ideas — qualitatively different from repair / sampling / decomposition /
plan-then-formalize**, aimed at either (a) cracking `p09_imo1964`, `rmo_2000_2`,
`rmo_2000_3`, or (b) reliably pushing past 6/9 on the solvable set.

Hard constraints any idea must respect:
- **Universal only.** The private eval holdout is unseen; anything tied to a
  specific problem — or to a *category* observed in S_dev (e.g. "modular ⇒ ZMod",
  "Diophantine ⇒ interval_cases") — is overfitting and will not transfer. The
  mechanism must behave identically on every input.
- **Two fixed models** (Q, G) via OpenRouter; **no fine-tuning, no other models.**
- **Lean/Mathlib is the only verifier**; the comparator on the challenge's exact
  statement is the sole correctness authority (no weakening/altering statements,
  no `sorry`/`admit`/axioms).
- **Per-problem budget $1 and 8 h wall.** Cost is ample; wall time is tight but
  8 h/problem is a lot of unused headroom on the hard ones.

Open questions worth attacking: are the 3 hard problems reachable at all with
Q+G, or is this a true capability ceiling? If reachable, what mechanism gets
there **generally** (not by hardcoding)? What would use the large unused
time/compute budget productively (deeper search, tool use inside Lean, retrieval
of Mathlib lemmas done in a problem-agnostic way, verified lemma libraries built
on the fly, etc.)?
