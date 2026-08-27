# Continuation brief — propose where to go next

**To each agent:** you are one of three being asked, independently, to **propose
concrete paths to continue** this project from the state below. We have real
signal (verified proof-search that *advances but does not finish*) and do **not**
want to stop. Read everything, then propose directions that could break the
current ceiling. Be specific and constraint-honest; diverse proposals are wanted.

Date: 2026-08-27. Deadline to submit: **2026-08-30** (repo link + PDF writeup).

---

## 1. The task

A Lean 4 / Mathlib theorem-proving take-home. For each problem the agent receives
a `challenge.lean` with a theorem (statement fixed, proof = `sorry`) and a natural-
language description. The agent must return a complete Lean file that a **private
comparator** accepts as a proof of the **exact** original statement. Score = number
of comparator-accepted proofs on a private holdout.

### Hard constraints (any proposal MUST respect all)
- **Two fixed models only**, via OpenRouter: **Q = `qwen/qwen3.5-flash-02-23`**,
  **G = `openai/gpt-oss-120b`**. No other models, no fine-tuning.
- **Universal mechanisms only.** The eval holdout is unseen; anything keyed to a
  specific problem — or to a *category* seen in our dev set (e.g. "modular ⇒ ZMod",
  "Diophantine ⇒ interval_cases") — is overfitting and will not transfer. The agent
  must behave identically on every input.
- **Lean/Mathlib is the only verifier and the only runtime tool.** No external
  retrieval/services (no web, Loogle, LeanSearch, `#leansearch`). Lean's *own*
  local tactics (`exact?`, `apply?`, `simp?`, `aesop?`, `find`, `#check`) are allowed.
- **No weakening**: never alter the theorem statement/name, never `sorry`/`admit`/
  new axioms in a returned file. The comparator on the original statement is the
  sole authority.
- **Budgets: ≤ $1 and ≤ 8 h per problem.** Cost is a non-issue (~$1 total spent so
  far). The 8 h/problem wall is largely **unused** on the hard problems — there is
  huge unspent time/compute headroom.

### Runtime (the machine is small — this shapes what's feasible)
- Runs on one always-on Linux box (`sshrun`) over SSH+tmux. **2 CPUs, 14 GB RAM,
  one Lean worker** (`N_WORKERS=1`). Parallelism is not viable (2 cores; two 8 GB
  Lean containers don't fit).
- Timings observed: a **model call ≈ 70 s** (G); Lean checks are **warm and cheap**
  after a ~10 s per-problem Mathlib load (later checks sub-second to a few seconds);
  `apply?` ≈ 70 s (expensive), `exact?` variable, `decide`/`nlinarith` on big terms
  can hit the timeout. A whole arm over the 9-problem dev set ≈ 40–120 min.

---

## 2. Problem set (frozen split)

We develop on **S_dev (9 problems)**; **S_eval (7)** is an untouched holdout.
S_dev: `p01_linear`(E), `p03_sq_ge_two_ab`(E), `p05_gcd_mersenne`(M),
`p06_pow_mod`(M), `p09_imo1964`(H, two theorems), `p10_factorial_pow`(H),
`rmo_2000_2`(H, cubic Diophantine in ℕ), `rmo_2000_3`(H, harmonic-weighted sums
over a decreasing sequence), `putnam_2018_a1`(H).

**Never solved by ANY mechanism (the target):** `p09_imo1964`, `rmo_2000_2`,
`rmo_2000_3`.

---

## 3. Everything tried, with results (all on S_dev, fixed kit)

`1*` = solved by the **deterministic tactic sweep** (no model call, variance-proof).

| Problem | S-Q | S-G | R-Q | R-G | H-QG | H-GQ | AT-G | SK-G | BON-G | PF-GQ | ST-G | ST-GQ |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| p01_linear | 1 | 1 | 1 | 1 | 1 | 1 | 1* | 1* | 1* | 1* | 1* | 1* |
| p03_sq_ge_two_ab | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 0 | 1 | 1 |
| p05_gcd_mersenne | 0 | 1 | 0 | 1 | 0 | 0 | 1* | 1* | 1* | 1* | 1* | 1* |
| p06_pow_mod | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| p09_imo1964 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| p10_factorial_pow | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 1 |
| rmo_2000_2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rmo_2000_3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| putnam_2018_a1 | 0 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 0 |
| **TOTAL** | 3 | 4 | 4 | 5 | 4 | 3 | 4 | 5 | 5 | 4 | 5 | 4 |

**Any-arm union = 6/9** `{p01,p03,p05,p06,p10,putnam_2018_a1}` — unchanged across
every mechanism. Best single arm = 5/9.

### Mechanisms (what each is)
- **S** (solo): kit baseline multi-turn whole-file loop. **R** (repair): propose →
  Lean diagnostics → same-model targeted repair. **H** (handoff): other model repairs.
- **AT** (auto-tactics): deterministic Mathlib tactic sweep + tactic menu in prompts.
- **SK** (skeleton): `have … := by sorry` skeleton then fill. **BON** (best-of-N):
  8 independent proposals w/ rotating strategy menu. **PF** (planner→formalizer):
  G writes NL plan, Q formalizes.
- **ST** (StateTree): verified proof-**state** search (see §4). ST-G = G proposes
  actions; ST-GQ = G and Q both propose from the same state.

### Two robust facts
1. **Deterministic sweep floor**: `p01` (`nlinarith`) and `p05` (`simp_all`) are
   solved for free, no model, every run — variance-proof. `p05` was model-dependent
   before; now guaranteed.
2. **High run-to-run variance**: the same R-G config scored 5/9 then 2/9; single-run
   ±1 differences are inside the noise. Nothing here is seeded/repeated ×3 yet.

---

## 4. The live signal to build on: verified proof-state search (StateTree)

We stopped wrapping whole-file generation and built a **verified proof-state tree**
(COPRA-style): nodes are Lean-verified tactic prefixes + their exact remaining goal
state. At each node we harvest real Mathlib premises (`apply?`), ask the model(s)
for a few short next tactic actions (batched JSON), let **Lean** check every child,
keep only novel verified states, and expand best-first with backtracking. Everything
works through the existing `check_file` (no harness change); confirmed live that we
can extract exact goal states (`trace_state`) and real premises (`apply?`).

**Result: the tree ADVANCES but never CLOSES.** Across 3 runs, **zero** problems were
closed natively by the tree (`state_tree_solved` = 0). All solves came from the
sweep or a whole-file fallback. But the search makes real verified progress, and
**adding the second model helped generation** (the key bottleneck):

| Problem | ST-G verified progress | ST-GQ (both models) verified progress |
|---------|---|---|
| rmo_2000_3 | depth 0–1 | **depth 3, 3 valid children** |
| p10_factorial_pow | depth 0 | depth 2, 2 valid children |
| p06_pow_mod | depth 3, 7 valid children (a run) | depth 0–1 |
| rmo_2000_2 | depth 1 | depth 1 |

**Diagnosis (the crux for you):** the search *architecture* works and is safe
(fallback guarantees ≥ baseline). The bottleneck is the **action policy**: Q and G
are general chat models, not trained tactic-proposal/value policies, so they produce
**too few valid, progress-making next steps**, the frontier collapses, and the tree
never reaches the depth needed to finish a hard proof. Two proposers help but not
enough. The tree also **under-uses budget** (exhausts early, spends ~$0.03 of the
$1). Multi-theorem challenges (`p09`) currently bypass the tree (v1 handles single-
theorem only).

---

## 5. What exists to build on (code inventory)

Under `re-takehome-main/experiments_agents/` (all universal, Lean-gated):
- `common.py` — model ids, tactic sweep + battery, integrity check, root-diagnostic
  formatting, candidate ranking, provenance hashing.
- `repair.py` — hardened propose/repair loop (best-so-far return, integrity gate,
  stall detection, seed-latest).
- `tactics.py` — sweep + tactic-menu agent (the strong fast-path / fallback).
- `skeleton.py`, `bestofn.py`, `planformalize.py` — the retired iteration arms.
- **`leanprobe.py`** — reusable Lean interaction: extract goal state, harvest
  premises (`apply?`/`exact?`), classify a prefix invalid/solved/partial in one
  probe, state hashing. **This is the proof-search substrate.**
- **`statetree.py`** — the best-first verified search (beam, depth, premise probes,
  batched model actions, backtracking, sweep stage-0, strong fallback). Budgets are
  env-configurable (`ST_BEAM`, `ST_MAX_DEPTH`, `ST_MAX_MODEL_CALLS`,
  `ST_MAX_LEAN_CHECKS`, `ST_ACTIONS_PER_CALL`, `ST_PREMISE_MAX_DEPTH`, …).
- Run: `run.py --problems sets/S_dev --agent experiments_agents.<arm>:create_agent`.

Prior analysis docs (context): `EXPERIMENT_S_dev_matrix.md`,
`EXPERIMENT_S_DEV_ITERATION_RESULTS.md`,
`EXPERIMENT_S_DEV_BIG_CHANGER_RECOMMENDATIONS.md` (proposed StateTree/LocalPremise/
VerifiedLemmaExchange; the first two are built).

---

## 6. What we want from you

**Propose concrete, universal paths to continue** — ideally ones that could crack
`p09_imo1964`, `rmo_2000_2`, `rmo_2000_3`, or otherwise push past the 6/9 union —
**building on the verified-progress signal** (the tree advances; the models are the
bottleneck). For each proposal give: the mechanism, why it plausibly breaks the
ceiling, how it stays universal, its cost/wall footprint on the small box, a
concrete first experiment, and a kill criterion.

Open threads worth your judgment (not a menu — propose your own):
- The action policy is the bottleneck. How do you get **more/better valid tactic
  actions** from Q/G against a raw goal state? (Better prompting? Feeding `apply?`
  suggestions *as* actions without a model call? Type-directed `#check` filtering of
  model-named lemmas? Forcing structured `have`/`refine ?_` decomposition?)
- The tree under-uses the huge time budget. What productive search would spend 8 h
  well (deeper/wider search, verified lemma blackboard on stagnation, iterative
  deepening, portfolio of independent search seeds)?
- Is the second model best used to **propose** (adds branches), to **advise when
  stuck** (inject a key lemma/approach), or is there a genuinely useful **verified**
  role for it that Lean can't already do?
- Are `p09`/`rmo_2000_2`/`rmo_2000_3` reachable at all with Q+G, or is this a true
  capability ceiling? What observable would settle it?
- Multi-theorem challenges bypass the tree — worth handling per-theorem?

Also fair game: argue that the honest, defensible submission is the robust
sweep-first + repair agent (~5–6/9) plus a strong writeup of the StateTree finding,
and that further ceiling-chasing is negative-EV before the deadline. If so, say why.

Constraints recap: **Q and G only; universal; Lean-only; no statement weakening;
$1 and 8 h per problem; deadline 2026-08-30.**
