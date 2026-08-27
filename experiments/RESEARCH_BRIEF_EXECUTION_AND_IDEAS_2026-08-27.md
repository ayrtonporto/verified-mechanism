# Research brief — improve execution, or find the idea that cracks the cruxes

**Date:** 2026-08-27
**For:** two independent research agents.
**We want to be ambitious and we want *results* (a new solve), not another survey.**

You are given a mature, well-instrumented Lean-4 theorem-proving system that is
**stuck at 6/9 on the dev set** with three unsolved problems. Everything cheap and
obvious has been tried and logged. Read the situation, then answer the two questions
in §8. Ground every proposal in what already exists — proposing an
already-implemented mechanism as "new" is the failure mode we most want to avoid.

---

## 1. The task and hard constraints (any idea must respect ALL)

Lean 4 / Mathlib theorem proving. Per problem: a `challenge.lean` (theorem with
`sorry`) + an NL description. Return a Lean file a **private comparator** accepts as
a proof of the **exact** statement. Score = comparator-accepted proofs on a private
holdout.

- **Two fixed models only**, via OpenRouter: **Q = `qwen/qwen3.5-flash-02-23`**,
  **G = `openai/gpt-oss-120b`**. No other models, **no fine-tuning**.
- **Universal mechanisms only.** The holdout is unseen; anything keyed to a specific
  problem — or a *category* seen in dev ("modular ⇒ ZMod", "Diophantine ⇒
  interval_cases") — is overfitting and will not transfer. Identical behaviour on
  every input.
- **Lean/Mathlib is the only verifier and the only runtime tool.** No web, Loogle,
  LeanSearch, external retrieval. Lean's *own* local tactics/queries
  (`exact?`, `apply?`, `simp?`, `aesop?`, `grind?`, `#find`, `#check`) ARE allowed.
- No weakening statements/names; no `sorry`/`admit`/new axioms in a returned file.
- Budget: **≤ $1 and ≤ 8 h per problem.** Cost is a non-issue (~$1.5 total spent).
  Wall time is the real limit, but see §6 — we now have a ~10× parallel driver.

### Runtime facts (verified)
- Image: **Lean v4.32.0**, Mathlib commit `81a5d257c8e410db227a6665ed08f64fea08e997`.
  → **`grind` is available** (kernel-verified automation). Confirmed working.
- Harness `llm.complete` supports **`tools` / `tool_choice`** and **`seed`** →
  tool-calling and seeded sampling are buildable with no harness change.
- Box: 2 CPUs, 14 GB RAM. One Lean container needs ~8 GB → effectively **one Lean
  check at a time**. A G call ≈ 70 s; warm Lean checks are sub-second to a few s;
  `apply?` ≈ 70 s; a fresh container pays ~100 s Mathlib import.

---

## 2. The three unsolved problems and their EXACT cruxes

Solvable frontier = 6/9 `{p01, p03, p05, p06, p10, putnam_2018_a1}` — unchanged
across every mechanism. The three walls:

### p09_imo1964 — two theorems in one file
```lean
theorem p09_a (n : ℕ) (hn : 0 < n) : 7 ∣ 2 ^ n - 1 ↔ 3 ∣ n := by sorry
theorem p09_b (n : ℕ) (hn : 0 < n) : ¬7 ∣ 2 ^ n + 1 := by sorry
```
Both need periodicity of `2^n mod 7` (cycle `2,4,1`, period 3).
- **p09_b is NEARLY solved**: our best stored attempt reaches an **8/11 verified
  prefix** — it sets up the periodicity facts and reduces to `⊢ False` in fixed
  residues `n % 3 ∈ {0,1,2}`. The remaining step is: substitute the residue, compute
  `2^residue % 7`, contradict `7 ∣ 2^n + 1`. The tactic battery (incl. `grind`) does
  **not** finish it as one shot; a short targeted finish likely would.
- **p09_a is the wall**: max **2/4** verified steps. The clean route is `ZMod 7` +
  `orderOf (2 : ZMod 7) = 3` and `orderOf_dvd_iff_pow_eq_one`, but the truncated-ℕ
  `2^n - 1` ↔ `7 ∣` bridge and the missing lemma name defeat the models.
- **p09 passes only if BOTH `p09_a` and `p09_b` are proved.** So p09_a is the gate.

### rmo_2000_2 — cubic Diophantine
```lean
theorem rmo_2000_2 (x y : ℕ) (hx : 0 < x) (hy : 0 < y)
  (h : y ^ 3 = x ^ 3 + 8 * x ^ 2 - 6 * x + 8) : x = 9 ∧ y = 11 := by sorry
```
Human proof: squeeze `y` between consecutive cubes (`(x+1)^3 < y^3 < (x+3)^3` for
large `x`), so `y ∈ {x+2}` region, substitute, solve a finite residue. Needs
`nlinarith` with the right auxiliary cube terms + a bounded case check. Models reach
max **2/4** steps (a bare case split `x≤2 / x≥3`); the remaining goal is the whole
`⊢ x=9 ∧ y=11`. Note the ℕ truncated subtraction `- 6*x` is a real trap.

### rmo_2000_3 — harmonic-weighted sums (hardest; likely true ceiling)
```lean
theorem rmo_2000_3 (x : ℕ → ℝ) (hpos : ∀ n, 0 < x n) (hmono : ∀ n, x n ≥ x (n+1))
  (hsq : ∀ N, (Ico 1 (N+1)).sum (fun i => x (i*i) / i) ≤ 1) :
  ∀ k, (Ico 1 (k+1)).sum (fun i => x i / i) ≤ 3 := by sorry
```
Needs Abel summation / grouping `i` into blocks `[k², (k+1)²)` and bounding each
block by the `x(i²)` terms. Models reach max **4/5** steps but that is only setup
(deriving monotonicity); the remaining goal is the full `∑ ≤ 3`. Real analysis over
`Finset` — the crux is entirely unaddressed.

---

## 3. Everything already tried (do NOT re-propose these as new)

Full record: `experiments/IDEAS_AND_RESULTS.md`. Summary of mechanisms and best
S_dev score (all universal, Lean-gated):

| Mechanism | Arm | Best | Notes |
|---|---|:--:|---|
| solo multi-turn loop | S-Q/S-G | 4/9 | baseline |
| propose→repair (same model) | R-Q/R-G | 5/9 | adds only p10 |
| cross-model repair (handoff) | H-QG/H-GQ | 4/9 | handoff not free (lost p05) |
| deterministic tactic sweep + menu | AT-G | 4/9 | free wins p01/p05; **kept as stage 0** |
| skeleton sorry-first | SK-G | 5/9 | |
| best-of-N whole-file (diverse) | BON-G | 5/9 | N=8; cap now 512 but 512×70s > 8h |
| plan→formalize (NL then Lean) | PF-GQ | 4/9 | "think→translate" already done |
| verified proof-state tree (COPRA) | ST-G/ST-GQ | 5/9 | harvests `exact?`/`apply?` premises; **0 native closes**, depth ≤2 wall |
| **split independent theorems** | MT-G | p09=0 | per-theorem solving; p09_a still walled |
| **verified `have`-decomposition** | SF-G/MT-SF-G | 0/3 hard | compose-check + in-place hole fill; failed the 3 |
| **grind added to battery** | — | — | works; closes nothing new, incl. p09 periodicity subgoal |
| **×4 parallel sampling of MT-SF-G** | — | 0/3 | brute force does not crack the cruxes |

Also **measured** (offline, zero model cost):
- **MaxPrefix**: failed whole-file attempts DO contain deep verified prefixes
  (p09_b 8/11, rmo_2000_3 4/5) — but the **resume probe** shows those are mostly
  easy scaffolding; the remaining goal after the prefix is still the crux, and the
  battery (incl. grind) finishes none.

---

## 4. The sharpened diagnosis (the crux, literally)

Across a properly-built verified search AND structured decomposition AND sampling,
Q and G **build the easy structure** (case splits, helper `have`s, monotonicity) and
**stall precisely at the ONE hard mathematical step** of each problem (periodicity
contradiction / cube squeeze / Abel summation). It is **not** an action-*validity*
problem and **not** a chaining-depth problem — it is that neither model produces the
crux argument, and no single Mathlib tactic (`grind`/`nlinarith`/`omega`/`decide`)
discharges it. Depth ≠ progress on the crux.

The honest open question: is this a **true capability ceiling** for Q+G on these
three cruxes, or is there a harness that lets them contribute the crux **without
per-problem hinting**?

---

## 5. Levers NOT yet tried (with a real mechanistic reason), for you to judge

Not endorsements — evaluate, improve, or replace them. The bar is: universal, and a
concrete reason it attacks the *crux*, not the scaffolding.
- **Premise search by TYPE** (`#find` / `find` on a lemma *shape*, distinct from the
  `exact?`/`apply?`-by-goal that ST already harvests). Motivation: on p09_a the model
  knows the shape (`... ↔ orderOf ... ∣ n`) but not the name; Lean can find it.
- **MenuTree**: Lean pre-builds a menu of Lean-*validated* candidate actions at a
  state; the model only **selects IDs** via tool-calling. Separates "can't write
  valid Lean" from "can't rank" — makes the bottleneck causally observable.
- **PortfolioCut**: fix sketch-fill's two defects — (a) compose-check verifies
  sufficiency but NOT non-triviality (a `have h:=<goal>; exact h` skeleton passes and
  reduces nothing); (b) score each cut's *fillability* (does automation find progress
  in its holes) before spending model calls; fill holes with a grind/menu cascade,
  not 5 free strings.
- **BridgeSearch**: bidirectional — prove forward facts from hypotheses AND back-cut
  from the goal, connect the frontiers. Only if PortfolioCut yields valid-but-unclosed
  cuts.
- **Targeted finish for near-misses** (p09_b specifically): its remaining `⊢ False`
  residue goals look one or two tactics from done — is there a *universal* finisher
  (e.g. `interval_cases` on the residue then `decide`/`norm_num`) that closes them?

---

## 6. What execution improvements are already in place (build on these)

- **`fastdrive.py`** — parallel dev driver. The memory limit is the Lean check (one
  8 GB container), NOT model calls (HTTP, parallel, the real wall-time hog). It runs
  every problem/repeat agent concurrently on one event loop sharing one `LeanClient`
  (its lock serialises checks through a warm container) + one `LLMClient`; model calls
  overlap, Lean checks queue, comparator runs sequentially. Measured **~10×**: 12
  MT-SF-G runs in 48 min vs ~8 h sequential. `--repeat N` gives ×N variance cheaply.
- **Code substrate**: `experiments_agents/leanprobe.py` (extract goal state, harvest
  premises, classify a prefix), `statetree.py` (verified best-first search),
  `sketchfill.py` (compose-check + in-place hole fill), `multitheorem.py` (per-theorem
  split), `common.py` (tactic battery incl. `grind`, integrity gate). Probes:
  `probe_grind.py`, `maxprefix_offline.py`, `resume_probe.py`.

---

## 7. Execution questions worth your scrutiny (some may be low-hanging)

- Is **one Lean check at a time** actually forced? Could two ~6 GB containers fit in
  14 GB to double Lean throughput, or does Mathlib's footprint forbid it? Measure it.
- The sketch-fill hole-filler does a full `CLOSING_TACTICS` sweep per hole per
  skeleton — is that where the Lean budget goes? Should `grind`/`aesop?` run once per
  *state* and be cached by state-fingerprint across skeletons?
- Suggestion parsers currently take the first line of `apply?`/`exact?`. `aesop?` /
  `grind?` emit multi-line scripts — are we dropping usable suggestions?
- `invalid_actions` is one number. A **taxonomy** (empty / bad-JSON / syntax /
  unknown-ident / type-error / tactic-failed / timeout / valid-no-change /
  valid-dup / valid-novel / close) would tell us WHICH layer fails.
- Is per-hole/per-state work **deduplicated by goal fingerprint**, or are we
  re-checking identical states across samples?

---

## 8. What we need from you — two questions

**Q1 (execution).** Given §6–§7, where is wall time and Lean budget actually going,
and what concrete, universal changes would raise throughput or the valid-progress
rate per Lean check? Prioritise cheap, measurable wins. Give the first experiment and
a kill signal for each.

**Q2 (ideas).** Propose universal mechanisms that could plausibly contribute the
**crux** of at least one of the three problems (§2) with Q+G, no fine-tuning, no
per-problem/category rules, Lean-only. For each: the mechanism, *why it attacks the
crux and not the scaffolding*, how it stays universal, a first experiment, and a kill
signal. p09_b (near-miss) and p09_a (the gate) are the highest-EV single targets;
say if you think any of the three is genuinely out of reach for Q+G and what evidence
would clinch that.

**Discipline we hold you to:** verify against `experiments/IDEAS_AND_RESULTS.md`
before calling anything new; distinguish a *capability* limit from a *harness* limit
with a measurable observable; every proposal ships with a kill signal. Ambition is
welcome; unfalsifiable ambition is not.
