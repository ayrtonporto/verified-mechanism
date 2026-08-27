# New-ideas brief — the bottleneck is now precise

**Purpose:** we built a proper verified proof-search system and it sharpened the
problem to a single, concrete bottleneck. We want **new ideas** to attack it (or a
reframing we're missing). Read the situation, then propose directions.

---

## 1. The task

Lean 4 / Mathlib theorem proving. For each problem: a `challenge.lean` with a
theorem (statement fixed, proof = `sorry`) + an NL description. Return a complete
Lean file a **private comparator** accepts as a proof of the **exact** statement.
Score = number of comparator-accepted proofs on a private holdout.

### Hard constraints (any idea must respect all)
- **Two fixed models only**, via OpenRouter: **Q = `qwen/qwen3.5-flash-02-23`**,
  **G = `openai/gpt-oss-120b`**. No other models, **no fine-tuning**.
- **Universal mechanisms only.** The holdout is unseen; anything keyed to a specific
  problem — or to a *category* seen in dev (e.g. "modular ⇒ ZMod", "Diophantine ⇒
  interval_cases") — is overfitting and won't transfer. Same behavior on every input.
- **Lean/Mathlib is the only verifier and the only runtime tool.** No web, Loogle,
  LeanSearch, `#leansearch`, external retrieval. Lean's *own* local tactics
  (`exact?`, `apply?`, `simp?`, `aesop?`, `find`, `#check`) are allowed.
- No weakening statements/names; no `sorry`/`admit`/new axioms in a returned file.
- Budget: **≤ $1 and ≤ 8 h per problem.** Cost is a non-issue (~$1 total spent so
  far). **The 8 h/problem wall is largely unused** — huge unspent compute headroom.

### Runtime (small box; shapes feasibility)
One Linux box: **2 CPUs, 14 GB RAM, one Lean worker** (no parallelism). A model call
≈ 70 s (G); Lean checks are warm/cheap after a ~10 s per-problem Mathlib load
(later checks sub-second to a few seconds); `apply?` ≈ 70 s.

---

## 2. The problem set

Dev set **S_dev** (9): `p01_linear`(E), `p03_sq_ge_two_ab`(E), `p05_gcd_mersenne`(M),
`p06_pow_mod`(M), `p09_imo1964`(H, two theorems: 7∣2^n−1 ↔ 3∣n, and no n has
7∣2^n+1), `p10_factorial_pow`(H), `rmo_2000_2`(H, cubic Diophantine in ℕ),
`rmo_2000_3`(H, harmonic-weighted sums over a decreasing sequence),
`putnam_2018_a1`(H). Holdout S_eval (7) untouched.

**Solvable frontier = 6/9** `{p01,p03,p05,p06,p10,putnam_2018_a1}` — unchanged across
every mechanism tried. **Never solved by anything:** `p09_imo1964`, `rmo_2000_2`,
`rmo_2000_3`. Best single arm = 5/9.

---

## 3. What was built and what it showed

### 3.1 Whole-file mechanisms (all universal, Lean-gated) → plateau at 6/9
- Baselines S (kit loop), hardened repair R (propose→diagnostics→same-model repair),
  handoff H (other model repairs).
- **AT** deterministic Mathlib tactic sweep + tactic menu; **SK** `have…:=by sorry`
  skeleton then fill; **BON** best-of-8 with a strategy menu; **PF** planner→formalizer.
- Result: frontier never moved past 6/9. Two durable facts:
  - **Deterministic sweep is the only variance-proof win**: `p01` (`nlinarith`),
    `p05` (`simp_all`) solved with zero model calls, every run.
  - **High run-to-run variance**: same config scored 5/9 then 2/9.

### 3.2 Verified proof-state search (StateTree) — built properly, incl. the fixes
COPRA-style search (no harness change): nodes are **Lean-verified tactic prefixes +
their exact remaining goal state**. Per node: harvest real Mathlib premises
(`apply?`/`exact?`), ask model(s) for a few short next tactic actions (batched JSON),
**Lean checks every child**, keep novel verified states, expand best-first with
backtracking. v2 added: **per-node retry rounds**, **action-level repair from the
exact Lean error**, a fixed already-tried list fed to the model, and a
**stratified/Pareto frontier** (never prune a valid decomposition on goal count).
Deterministic sweep is stage 0; a full repair loop is a fallback so the tree never
scores below baseline. We verified live that we can extract goal states and real
premises, and that warm Lean checks are cheap (so many small checks are affordable).

**Result (4 configurations: G-only, G+Q, v2 G/G, v2 G-propose/Q-repair):**
- Score 4–5/9, **all from the sweep or the fallback**. **Zero problems closed
  natively by the tree** in any configuration.
- With full budget, the search *does* explore, but on the hard problems it hits a
  **hard wall at max depth ≤ 2** and a **very high invalid-action rate** — the
  models proposed and Lean rejected **18 / 33 / 39** actions on `p03 / rmo_2000_2 /
  p10` respectively, yielding only 2–7 valid children and never chaining past 2
  verified steps.

---

## 4. The sharpened bottleneck (this is the crux)

The verification and search machinery works and is well-built. The limiting factor is
now precise: **the action policy.** Q and G are general chat models, not trained
tactic/value policies, so against a raw Lean goal state they emit a **low-hit-rate
stream of tactic proposals** (mostly rejected by the compiler) and cannot build a
verified trajectory more than ~2 steps deep on a hard goal. Neither error-guided
repair, nor a second model, nor Lean's own premise suggestions changed this.

So the open problem is essentially: **how do you get a general chat model (Q or G),
with no fine-tuning, to emit tactic-level actions that Lean actually accepts and that
make real progress — universally, at depth?** Everything else (search, verification,
premises, budget) is available and cheap.

---

## 5. What we want from you — new ideas

Propose concrete, universal directions. For each: the mechanism, why it plausibly
raises the valid-action rate or otherwise breaks the 6/9 frontier, how it stays
universal (no per-problem/category rules), and a first experiment + a kill signal.

Threads we find genuinely open (propose your own, too):
- **Action generation.** How to make Q/G propose Lean-valid tactics far more often?
  E.g. constrain the action space to a small typed grammar; force `refine ?_`/`have`
  skeletons whose subgoals are then searched; feed `apply?`/`exact?` candidates *as*
  actions and have the model only *choose/compose* among Lean-verified options rather
  than free-form generate; type-check every model-named lemma via `#check` before use;
  round-trip each proposed tactic through a cheap "does it parse / elaborate" pre-filter.
- **Using the huge unused time budget** (8 h/problem, essentially free) productively:
  massive breadth search, iterative deepening, many independent search seeds, or
  enumerating Lean automation combinations the models merely *assemble*.
- **The right division of labor** between Q and G, or between the models and Lean's
  automation, when the models are weak proposers but Lean is a strong checker.
- **Reframing:** is whole-proof-by-`have`-decomposition-then-`sorry`-fill (with each
  hole verified independently and frozen) actually a better object than a tactic tree,
  given weak per-step proposers? Is there a universal way to exploit that most of the
  6/9 wins are single automation tactics (i.e. lean harder on Lean, less on the LLM)?
- **Diagnosis:** what observable would distinguish "these two models fundamentally
  cannot do tactic-level proving" from "we haven't found the right harness for them"?
  `p09` (two theorems) has not yet been run through per-theorem search — is that worth
  it, and how universal can multi-theorem support be made?
- Fair to argue the honest read is a real capability limit for Q+G and that the value
  is a robust sweep-first + repair agent plus a rigorous writeup of *why*. If so, make
  the strongest version of that case and say what evidence clinches it.

## 6. Code substrate that already exists
`experiments_agents/leanprobe.py` (extract goal state, harvest premises, classify a
prefix invalid/solved/partial in one probe) and `experiments_agents/statetree.py`
(the best-first verified search with retry/repair/stratified frontier). Anything you
propose can build on these without touching the grading harness.

**Constraints recap:** Q and G only; no fine-tuning; universal; Lean-only (no external
retrieval); no statement weakening; ≤ $1 and ≤ 8 h per problem; huge unused time budget.
