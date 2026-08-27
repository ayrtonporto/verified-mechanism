# Big-changer recommendations after the S_dev iteration

**Date:** 2026-08-26  
**Status:** design recommendation; no `S_eval` results inspected  
**Inputs:** [`EXPERIMENT_S_DEV_ITERATION_RESULTS.md`](EXPERIMENT_S_DEV_ITERATION_RESULTS.md), [`EXPERIMENT_S_dev_matrix.md`](EXPERIMENT_S_dev_matrix.md), and [`SOTA_MULTI_MODEL_MATH_MEMO.md`](../design/SOTA_MULTI_MODEL_MATH_MEMO.md)  
**Constraints honored:** exactly Q and G; Lean/Mathlib only at runtime; no external retrieval; no problem- or category-specific routing; exact challenge statements; no `sorry`/`admit`/new axioms in final submissions; at most $1 and eight hours per problem.

---

## 0. Executive decision

The new results falsify the idea that another whole-file wrapper will move the frontier. Repair, eight-way sampling, a prose planner, and a nominal skeleton all rearrange the same six solved problems; none unlocks the three persistent failures. The next agent should therefore change the **search object**, not the prompt persona:

> Build a bounded best-first/backtracking tree whose nodes are **Lean-verified tactic prefixes plus their exact remaining proof states**. At each node, use local Mathlib search to expose real applicable premises, ask Q and G for several short next actions, retain only actions that elaborate, and share only kernel-verified lemmas between trajectories.

This is qualitatively different from the failed mechanisms:

- `BON-G` samples independent complete files; the proposed tree accumulates verified progress and backtracks.
- `R-*` rewrites a failing complete artifact; the tree asks for a small action against an exact current goal.
- `SK-G` asks one model to invent an unverified `sorry` skeleton and then repairs the entire file; the proposed workspace accepts and shares only independently verified lemma artifacts.
- `PF-GQ` communicates through unverifiable prose; the proposed collaboration object is a Lean proof state and a set of kernel-accepted declarations.

The recommended build is, in order:

1. **Correct the latency measurement.** The implementation is a warm Lean REPL, so the claim that every check pays a cold Mathlib import is probably wrong.
2. **Build `StateTree`**, a bounded verified proof-state search. This is the only next idea likely to change the ceiling by itself.
3. **Add `LocalPremise`**, using `exact?`, `apply?`, `simp?`, `aesop?`, `find`, and bounded `#check` probes inside the installed Mathlib.
4. **Add `VerifiedLemmaExchange` only on search stagnation.** This is the genuinely useful version of decomposition.
5. Keep the deterministic tactic floor and a very short whole-proof fast path; retire the current BON, PF, and SK mechanisms from the serious matrix.

My probability ranking, before running the experiments:

| Modification | Chance of unlocking at least one of the three persistent failures | Engineering risk | Recommendation |
|---|---:|---:|---|
| Verified proof-state search | Medium-high | Medium | Build first |
| Local Mathlib premise discovery | Medium; higher when coupled to proof-state search | Low-medium | Build with or immediately after StateTree |
| Verified lemma exchange | Medium, especially for long proofs | High | Build after StateTree demonstrates valid partial progress |
| More whole-file samples/repair turns | Low | Low | Stop investing |
| More prose planning/debate/personas | Very low | Low | Drop |

---

## 1. What the iteration actually tells us

The strongest fact is not that the best arm scored 5/9. It is that the union remained exactly 6/9 after adding four substantially different prompt-level wrappers. The three hard problems received zero hits from every arm, while R-G itself varied from 5/9 to 2/9. The conclusions should be:

1. **Whole-file generation has hit a strategy-and-library ceiling.** More samples change which already-solvable theorem is hit, but not the frontier.
2. **Lean diagnostics are currently used too late and too coarsely.** A complete file can contain dozens of independent errors. Repairing that object asks the model to preserve correct regions, infer the root error, and finish the mathematics simultaneously.
3. **The system discards almost all partial progress.** A failed 100-line proof with three correct intermediate facts is treated as a failed string, not as a set of proved objects.
4. **The current “skeleton” is not a verified workspace.** Its implementation asks for a full `have ... := by sorry` structure, then feeds the whole file back to the same repair loop. No hole is isolated, solved, frozen, or shared as a certified artifact.
5. **The current collaboration object is weak.** Handoffs share failed code; PF shares prose. Neither provides the other model with a compact, exact, verifier-grounded state.
6. **Static tactic hints help the floor, not the ceiling.** The deterministic `nlinarith`/`simp_all` wins are real and should remain, but a menu in a prompt does not tell the model which theorem names actually exist in this Mathlib version.

The correct hypothesis for the next round is:

> The models contain enough local tactic and mathematical capability to make progress, but whole-file generation prevents the harness from preserving, composing, and exploring that progress.

The next experiment should test that hypothesis directly.

---

## 2. Correct the wall-time diagnosis before redesigning around it

The results memo says each Lean check pays an approximately 100-second cold Mathlib import. The current harness does not appear to do that:

- [`lean.py`](../re-takehome-main/src/re_harness/lean.py) starts one Docker Lean REPL.
- `start()` sends `import Mathlib` once and stores the returned environment as `_base_env`.
- Each later `check_file()` strips import lines and sends the proof body to that still-running REPL using `_base_env`.
- `LeanCheck` already records both `duration_ms` and `container_restarted`.

Therefore, treat the “cold import per check” explanation as unverified and probably false. It may be that expensive tactics hit the 45/120-second timeout, that the container is repeatedly dying, or that total arm time is dominated by approximately 70-second G calls. Those imply different optimizations.

### Required measurement patch

Before another full arm, aggregate these fields per problem and stage:

| Metric | Why it matters |
|---|---|
| first Lean check duration | Captures the actual import/start cost |
| median/p90 later Lean duration | Captures warm-check cost |
| `container_restarted` count | Detects accidental cold starts |
| timed-out tactic and source hash | Identifies the real sweep/search sink |
| model latency by Q/G | Determines useful expansion count |
| Lean checks per model call | Makes batching gains visible |

**Decision rule:** if later checks are warm, spend the budget on many small verifier queries. If containers really restart, fix that before search. Do not reduce verifier interaction based on the current prose claim alone.

---

## 3. Big changer #1 — `StateTree`: verified proof-state search

### 3.1 The mechanism

Turn every theorem hole into a search tree:

```text
original theorem
      |
      v
Lean extracts exact goal state S0
      |
      +--> G proposes 3 short tactic fragments --+
      |                                          |
      +--> Q proposes 3 short tactic fragments --+--> Lean checks every child
                                                       |
                           discard errors/timeouts <---+
                                                       |
                           retain novel verified states
                                  /       |       \
                                S1        S2       S3
                                 \        |       /
                              bounded best-first expansion
                                         |
                                   zero remaining goals
                                         |
                            strict final comparator check
```

A node is not “a plausible proof.” It is:

```text
Node = {
  immutable challenge hash,
  declaration/hole index,
  verified tactic prefix,
  exact normalized remaining goals,
  state hash,
  parent hash,
  last action,
  depth,
  Lean duration/diagnostics,
  local search suggestions already tried
}
```

This is the core pattern behind stateful proof search systems such as COPRA, which repeatedly proposes tactics inside a backtracking search rather than repeatedly asking for a full proof. COPRA is older than the preferred window but remains the clean conceptual root. Recent tactic-level systems also use best-first proof-state exploration, although their trained policies/critics and compute budgets do not transfer directly to this project. See [COPRA, arXiv:2310.04353](https://arxiv.org/abs/2310.04353) and [InternLM2.5-StepProver, arXiv:2410.15700](https://arxiv.org/abs/2410.15700).

### 3.2 How to extract a state with the existing Lean API

For an open node, check an internal probe of this form:

```lean
theorem original_statement := by
  -- verified prefix
  <prefix>

  -- internal instrumentation only
  all_goals trace_state
  all_goals sorry
```

Interpret the result as follows:

- no Lean error + `has_sorry = true`: a valid partial proof; parse the traced goals;
- `accepted = true`: all goals closed; run the ordinary strict whole-file/integrity/comparator path;
- any Lean error or timeout: invalid child;
- `sorry` is allowed only in these disposable internal probes, never in a checkpoint presented as a solution and never in the returned file.

This requires one small but important code distinction. `LeanCheck.accepted` deliberately rejects any message containing `sorry`; proof-state probing must instead use a new predicate such as:

```text
probe_valid = not timed_out and no severity=error messages
```

Final acceptance remains unchanged and strict.

### 3.3 What each model should output

Do not ask for a complete file. Give the model:

- the immutable theorem statement;
- the verified prefix;
- the exact current local context and goals from Lean;
- the locally discovered premises for that state;
- a short list of actions already tried from the same state.

Request a machine-parseable array of 3–4 tactic fragments:

```json
[
  {"tactic": "...", "intent": "..."},
  {"tactic": "...", "intent": "..."},
  {"tactic": "...", "intent": "..."}
]
```

Constraints on each action:

- at most two tactic commands or one structured `have`;
- at most 500 characters;
- no imports, theorem declarations, `sorry`, `admit`, `axiom`, or statement edits;
- may use a named lemma only if it is already in the context, returned by a local search probe, or passes a local `#check` probe;
- diversity is semantic: one direct finisher, one structural step, one lemma-driven step, not paraphrases.

Generate several actions in **one** model call. The observed 70-second G latency makes call batching far more valuable than saving cheap warm Lean checks.

### 3.4 Search policy without a trained critic

Do not add an LLM judge. Lean determines validity, and the remaining search order can be deterministic.

Recommended first policy:

- beam width: 4 states;
- maximum depth: 16 actions;
- maximum model calls after the fast path: 16;
- 3 actions from G and 3 from Q when both are scheduled;
- maximum Lean child checks: 72;
- per-child Lean timeout: 20 seconds initially, with one 60-second retry only for a novel state whose tactic timed out;
- deduplicate normalized goal-state hashes;
- never re-run the same action at the same state;
- retain at least one child from each live parent to avoid immediate beam collapse;
- among remaining children, prefer fewer goals and smaller normalized total goal text, with a penalty for depth and repeated tactic families;
- preserve the parent in the frontier when a child increases goal count, because `apply`/`induction` can make real progress by replacing one hard goal with several easier ones;
- backtrack when a state produces no novel valid child.

The score is only a scheduling heuristic. It must never decide correctness.

### 3.5 Multi-model coordination that is actually testable

Give Q and G the **same verified state**, not each other’s failed full files. Each independently proposes next actions; Lean merges their valid children into one frontier.

This has a clean coordination object and a clean control:

| Arm | Calls per expanded state | Purpose |
|---|---:|---|
| `ST-G` | one G batch | Single-model search baseline |
| `ST-GG` | two independent G batches | Matched-compute homogeneous control |
| `ST-GQ` | one G batch + one Q batch | Heterogeneous coordination |

Only `ST-GQ > ST-GG` at comparable calls/tokens/Lean checks supports a heterogeneity claim. If they tie, the result is still useful: the protocol, not model diversity, is doing the work.

An economical production schedule is G on every expansion and Q only after two consecutive G expansions produce no novel state. That schedule is universal because it reacts to verifier progress, not theorem identity or category. For the causal development experiment, use the fixed matched schedules above.

### 3.6 Why this could unlock the current hard problems

The existing transcripts show models reaching meaningful intermediate reasoning and then drowning in a large proof artifact. A proof-state tree changes the task from “repair 15 errors and finish the theorem” to “advance this one exact obligation.” It also makes backtracking possible when a mathematically attractive transformation creates an unmanageable Lean state.

This is most plausible for the two finite/arithmetic-flavored failures, where a sequence of casts, factorizations, bounds, and cases can be checked one at a time. The long finite-sum theorem may still exceed the models’ mathematical/formalization capability; that is why the verified lemma workspace is the third stage, not a promise that StateTree solves everything.

### 3.7 Kill criterion

Abandon or radically revise the tactic-tree policy if, over three runs:

- it never reaches a valid state deeper than two nontrivial actions on any persistent failure; or
- more than 80% of expansions are parse/unknown-identifier failures even after local premise support; or
- it fails to improve either union coverage or per-problem success frequency while consuming at least 4× the calls of R-G.

Do not kill it merely because the first run scores the same 6/9. Inspect **verified progress curves**: maximum valid depth, novel states, solved subgoals, and accepted lemmas. Those observables distinguish a weak action policy from an unreachable theorem.

---

## 4. Big changer #2 — `LocalPremise`: Lean as the library expert

### 4.1 The problem it solves

The current tactic menu contains generic names such as `omega`, `ring`, and `aesop`, but the hard proofs are likely bottlenecked by **which Mathlib lemmas exist and how their types are stated**. Hallucinated identifiers and near-miss theorem forms waste whole turns.

Premise retrieval is a documented bottleneck in Lean theorem proving. LeanSearch v2 reports a controlled downstream improvement from 4% without retrieval to 20% with its strongest retriever, but its external service is unavailable under this project’s runtime constraints. The transferable lesson is the importance of premise discovery, not the external retriever itself. See [LeanSearch v2, arXiv:2605.13137](https://arxiv.org/abs/2605.13137).

Mathlib already provides local, version-matched mechanisms:

- `exact?` searches imported declarations for a theorem that closes the goal;
- `apply?` searches for an applicable theorem even if it creates subgoals;
- `simp?` and `aesop?` emit proof suggestions;
- `find` lists declarations applicable to the current goal;
- `#find` searches declaration types by a pattern;
- `#check name` verifies that a model-suggested declaration exists and returns its type.

These are documented in the [Mathlib tactic reference](https://leanprover-community.github.io/mathlib4_docs/tactics.html), [Mathlib `#find`/`find` documentation](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Tactic/Find.html), and the Lean community’s [guide to searching for theorems in Mathlib](https://leanprover-community.github.io/blog/posts/searching-for-theorems-in-mathlib/).

### 4.2 Universal local-search protocol

At every newly retained proof state, run the same bounded protocol:

1. On disposable copies of the state, try `exact?`, `apply?`, `simp?`, `aesop?`, and `find`.
2. Parse information messages such as `Try this:` and declaration/type output.
3. Keep at most 12 unique suggestions and at most 4,000 characters, ordered with closing suggestions first.
4. Re-check every extracted tactic before adding its child to the search tree.
5. Let each model propose at most six additional lemma identifiers or one `#find` type pattern.
6. Batch those names in a single local `#check` probe; return only confirmed names and exact types to the action proposer.
7. Cache by `(Mathlib environment, normalized state hash, query)` so backtracking does not repeat work.

Never call `#leansearch`, Loogle, LeanSearch, the web, or any other external retrieval system at runtime. The entire protocol executes inside the installed Mathlib and therefore cannot drift to a different library version.

### 4.3 Use suggestions as actions, not decoration

The critical implementation point is to feed local search results directly into the child generator:

```text
Lean suggestion -> parsed tactic -> child check -> verified state
```

Do not merely paste a long theorem-name list into a whole-proof prompt. If a suggestion itself closes or advances the state, it should enter the tree without another LLM call. The models are used to combine and sequence confirmed ingredients that automation alone did not finish.

### 4.4 Ablation and kill criterion

Run:

| Arm | Proof-state search | Local premise probes | Purpose |
|---|---:|---:|---|
| `ST-G` | yes | no | Search-only baseline |
| `ST-G+L` | yes | yes | Incremental value of local library awareness |

Report both model calls and Lean queries. The premise layer is useful if it yields any of:

- a new accepted theorem;
- at least a 25% reduction in unknown-identifier failures;
- at least a 25% increase in novel valid children per model call;
- a lower model-call count to existing successes.

Kill `find` or any individual probe whose p90 runtime is high and whose suggestions never become valid children. Keep the layer modular; local search is not one monolithic feature.

---

## 5. Big changer #3 — `VerifiedLemmaExchange`: a real lemma blackboard

### 5.1 Why the current skeleton was not the relevant test

The failed `SK-G` arm did not test a verifier-grounded blackboard. It asked one model to invent a complete hierarchy of statements with `sorry`, then asked the same whole-file repairer to fill “a few per turn.” This creates three problems:

- a bad intermediate statement can poison every downstream step;
- the agent has no isolated success signal for a single lemma;
- already correct lemma proofs can be destroyed by later whole-file rewrites.

Recent high-compute systems show that decomposition is useful when subproblems are managed explicitly and checked iteratively. Delta Prover, for example, couples reflective decomposition to a Lean-based DSL for subproblem management; its large benchmark result should not be transferred numerically to this tiny two-model setting, but the architectural lesson is directly relevant. See [Delta Prover, arXiv:2507.15225](https://arxiv.org/abs/2507.15225).

### 5.2 The replacement mechanism

Activate this stage only after StateTree stalls for a fixed number of expansions. Ask Q and G independently for small lemma proposals tied to the current exact goal:

```json
[
  {
    "name": "aux_1",
    "statement": "... exact Lean proposition ...",
    "proof": "by ...",
    "use": "how this changes the current goal"
  }
]
```

Then:

1. Rename lemmas into an isolated generated namespace.
2. Check every lemma statement and proof independently against the immutable imports and currently accepted lemmas.
3. Reject any item with errors, timeout, forbidden tokens, or dependencies on unverified items.
4. Store only kernel-accepted declarations in the blackboard.
5. Give both models the exact names and types of accepted lemmas.
6. Restart/continue StateTree with those lemmas prepended to the original challenge.
7. At finalization, include only accepted lemmas actually referenced by the final proof.

The blackboard schema should be:

```text
VerifiedLemma = {
  name,
  exact statement,
  exact proof,
  source model,
  dependency hashes,
  Lean-accepted hash,
  originating state hash,
  used_by_final_proof
}
```

### 5.3 Bounded policy

- activation: three consecutive expansions with no novel state;
- proposals: at most two lemmas per model per activation;
- accepted pool: at most six live lemmas;
- dependency depth: at most two;
- failed lemma proof: at most four StateTree expansions as its own target;
- no cycles;
- no natural-language-only artifacts in the shared pool;
- evict unused lemmas that do not yield a novel target-state child within two expansions.

This is universal. Every theorem triggers the same stagnation condition and receives the same lemma budget; no category or problem name is inspected.

### 5.4 Scientific control

Compare:

- `ST-GQ+L`: shared exact proof states and local premise search;
- `ST-GQ+L+V`: same protocol plus verified lemma exchange on stagnation;
- optionally `ST-GG+L+V`: same-model matched-call control.

The blackboard earns its complexity only if at least one accepted auxiliary lemma is used in a final accepted proof or if it produces a clearly deeper verified trajectory on a persistent failure. A pile of accepted but unused trivial lemmas is not progress.

---

## 6. Big changer #4 — preserve verified progress across models

Cross-model repair currently means “model B edits model A’s failed string.” That invites anchoring and regression. The new collaboration rule should be:

> Models may share exact Lean states, confirmed premise names/types, and accepted lemmas. They do not inherit one another’s unverified prose or failed complete proofs.

This gives three useful interaction modes:

1. **Sibling expansion:** Q and G propose alternative actions from the same state; Lean selects.
2. **Verified continuation:** Q can extend a prefix whose every prior action came from G because the prefix has already elaborated.
3. **Lemma exchange:** a lemma proposed/proved by one model becomes an ordinary certified premise for the other.

Track provenance for analysis but do not make the runtime schedule depend on model stereotypes such as “G is the mathematician” or “Q is the syntax fixer.” Fixed-role stories are not supported by the current matrix.

The clean heterogeneity statistic is not only final solve count. Also report:

- accepted child rate by model on identical states;
- unique state coverage by model;
- percentage of final proof actions contributed by each model;
- cross-model lemma reuse count;
- `ST-GQ` success compared with equal-call `ST-GG` and, if affordable, `ST-QQ`.

---

## 7. Supporting change — keep the floor but batch it

The deterministic tactic sweep is the only variance-proof improvement in the latest round, so keep it. Its implementation currently performs one Lean check for every tactic variant. Replace that with one bounded candidate using a solver combinator or a single batched source containing isolated copies, while preserving the winning-tactic log.

A solver-combinator form must require each branch to close every goal; do not let a tactic that merely makes progress prevent later branches from running. If Lean syntax or diagnostics make a single combinator fragile, batch isolated theorem copies under generated names/namespaces and map messages back to the candidate index.

This is an efficiency change, not a ceiling claim. It should remain stage zero:

```text
deterministic finishers -> short whole-proof fast path -> StateTree -> VerifiedLemmaExchange
```

Recommended fast path after the deterministic sweep:

- one G complete proof and one source-aware G repair;
- if unresolved, one fresh Q complete proof and one source-aware Q repair;
- then stop whole-file rewriting and transfer the remaining budget to StateTree.

This retains the observed R-G/R-Q floor without spending eight or more calls repeating a mechanism whose union has plateaued.

---

## 8. Recommended final architecture

```text
INPUT: immutable challenge + description

0. Integrity setup
   - hash required declarations/statements
   - create one warm Lean session

1. Deterministic floor
   - bounded/batched closing tactics
   - strict acceptance + integrity check

2. Four-call fast path
   - G whole proof -> Lean
   - one G repair -> Lean
   - fresh Q whole proof -> Lean
   - one Q repair -> Lean
   - early stop on strict success

3. StateTree
   - extract exact goal state(s)
   - run local Mathlib suggestion probes
   - Q/G propose short action batches
   - Lean checks children
   - deduplicate, retain frontier, backtrack

4. VerifiedLemmaExchange on stagnation
   - Q/G propose small exact lemmas
   - isolate and verify
   - share accepted lemmas
   - resume StateTree

5. Finalization
   - remove instrumentation and unused lemmas
   - reject forbidden constructs
   - strict whole-file Lean check
   - immutable-declaration integrity gate
   - comparator is sole success authority
```

### Default budgets per problem

| Resource | Default cap | Hard cap |
|---|---:|---:|
| Whole-file model calls | 4 | 4 |
| StateTree model calls | 12 | 20 |
| Model actions returned per call | 3–4 | 6 |
| Lean child checks | 48 | 96 |
| Local search probe groups | 12 | 24 |
| Verified auxiliary lemmas | 4 | 6 |
| State depth | 12 | 20 |
| Wall time | 3 h soft stop | 8 h |
| API spend | $0.70 soft stop | $1.00 |

At the soft stop, continue only if the last quarter of the budget produced a novel verified state, closed a subgoal, or accepted a lemma that is connected to the target. This is a universal progress rule, not a problem router.

---

## 9. Next experiment matrix

Do not run another ten-arm zoo. Use a small causal sequence.

### Phase A — validate mechanics cheaply

1. Confirm warm Lean timings and restart counts.
2. Unit-test probe parsing on synthetic theorems with zero, one, and multiple goals.
3. Verify that a probe containing internal `sorry` can be classified as a valid partial state while final acceptance still rejects it.
4. Verify state hashing/deduplication, forbidden-action filtering, and final instrumentation removal.

### Phase B — isolate proof-state search

| Arm | Maximum model calls | Local premise probes | Purpose |
|---|---:|---:|---|
| `R-G4` | 4 | no | Current matched reference |
| `ST-G4` | 4 batched action calls | no | Does stateful search beat whole-file repair at equal calls? |
| `ST-G8` | 8 batched action calls | no | Test search scaling |
| `ST-G8+L` | 8 | yes | Test local premise contribution |

Run all nine S_dev problems once for plumbing, then repeat the shortlisted arms three times. It is acceptable during engineering to replay only currently failed artifacts for speed, provided the algorithm itself is unchanged and the final reported development comparison runs universally on all nine.

### Phase C — test heterogeneity, not extra compute

| Arm | Maximum calls | Difference |
|---|---:|---|
| `ST-GG8+L` | 8 | two independent G action batches/schedules |
| `ST-GQ8+L` | 8 | matched G+Q action batches/schedules |
| `ST-QQ8+L` | 8 | optional completeness control |

### Phase D — test the verified workspace

Only if Phase B reaches nontrivial verified states but stalls:

| Arm | Lemma workspace | Purpose |
|---|---:|---|
| `ST-GQ8+L` | no | Search baseline |
| `ST-GQ8+L+V` | yes | Incremental value of certified decomposition |

### Primary outcome

Comparator-accepted solve frequency per problem over repetitions.

### Secondary outcomes that matter for diagnosis

- union coverage;
- success by cumulative model call and dollar;
- novel valid states per call;
- maximum verified depth;
- goals closed per call;
- unknown-identifier rate;
- local suggestion acceptance/use rate;
- accepted/used auxiliary lemmas;
- warm Lean p50/p90 and restart count;
- wall time to first success.

---

## 10. What to stop doing

### Retire from the main path

- `BON-G` as implemented: eight independent full files did not move the union.
- `PF-GQ` as implemented: unverifiable prose created no durable advantage.
- `SK-G` as implemented: it is whole-file repair with more placeholders, not certified decomposition.
- long generic repair loops after two whole-file repairs.
- prompts that list mathematical categories or strategy stereotypes as a substitute for state/premise evidence.
- an LLM critic or debate round that cannot create a Lean-verified child.

### Preserve only as controls or floor

- R-G and R-Q as reference/fast-path protocols;
- the deterministic tactic sweep, preferably batched;
- same-model matched-compute controls;
- strict integrity and comparator checks;
- best-so-far artifacts for failure analysis, but not as the sole search state.

---

## 11. Risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Tactic-level actions from general chat models are too weak | Tree has no valid depth | Include one structured `have` option; add LocalPremise; use action batches; kill by the stated criterion |
| Simple state score rejects useful decompositions | Beam collapses to superficially small goals | Keep one child per parent; preserve parents; use novelty and backtracking; compare breadth/depth traces |
| Internal `sorry` leaks into a final artifact | Invalid submission | Separate probe-valid from final-accepted types/paths; run forbidden-token and comparator gates at finalization |
| `find`/`apply?` is slow or noisy | Wall-time loss/context flooding | Per-probe timeout, top-N truncation, caching, per-tool ablation |
| Model invents theorem names | Wasted expansions | Permit names only from context/local search or successful `#check` |
| Verified lemma pool fills with trivia | Complexity without progress | Require target-state impact; cap at six; evict unused lemmas |
| Multi-model result is really extra compute | Invalid scientific claim | `ST-GQ` vs equal-call `ST-GG`/`ST-QQ` |
| Search helps p09/rmo2 but not long analysis proof | Ceiling remains on rmo3 | Report honestly; success is still a frontier move, not a universal solver claim |

---

## 12. Opinionated priority and go/no-go decisions

### Rank 1 — Verified proof-state tree

| Field | Decision |
|---|---|
| Novelty versus current code | High |
| Expected ceiling impact | Highest |
| Implementation effort | Medium, roughly 1–2 focused days with tests |
| First experiment | `ST-G4` vs `R-G4`, then `ST-G8+L` |
| Go signal | deeper valid trajectories and/or one new solve |
| Kill signal | no nontrivial valid depth after local premise support |

### Rank 2 — Local Mathlib premise layer

| Field | Decision |
|---|---|
| Novelty versus current code | High in this harness |
| Expected ceiling impact | Medium-high in combination with Rank 1 |
| Implementation effort | Low-medium |
| First experiment | `ST-G8` vs `ST-G8+L` |
| Go signal | fewer identifier errors/more valid children/new solve |
| Kill signal | high latency and near-zero used suggestions |

### Rank 3 — Verified lemma exchange

| Field | Decision |
|---|---|
| Novelty versus current SK-G | High |
| Expected ceiling impact | Medium; strongest for long proofs |
| Implementation effort | High |
| First experiment | add only after observed StateTree stagnation |
| Go signal | an accepted shared lemma is used in a final proof or unlocks deeper states |
| Kill signal | accepted lemmas are trivial/unused or statements repeatedly poison downstream search |

### Rank 4 — Batched deterministic floor and probes

| Field | Decision |
|---|---|
| Novelty | Low |
| Expected ceiling impact | Low |
| Implementation effort | Low |
| Value | recovers time for the first three mechanisms |

### Rank 5 — More whole-file coordination

| Field | Decision |
|---|---|
| Recommendation | Do not build |
| Reason | The new experiment already tested repair, sampling, planning, and nominal decomposition without moving the 6/9 union |

---

## 13. Final recommendation in one paragraph

Freeze the exact statements, comparator, deterministic finishers, and four-call G-then-Q fast path. Spend the remaining engineering budget on one new coordination object: a compact shared blackboard of exact Lean goal states, verified tactic prefixes, locally confirmed Mathlib premises, and kernel-accepted auxiliary lemmas. Let both fixed models propose short actions from identical states and let Lean—not an LLM critic—build and select the search frontier. The decisive scientific comparisons are stateful versus whole-file search at matched calls, local-premise versus no-premise search, and G+Q versus G+G at matched compute. If that system cannot make nontrivial verified progress on the persistent failures, the evidence will finally support a real capability-ceiling conclusion; the current whole-file failures do not yet justify one.

---

## 14. Sources

- **READ:** COPRA — *An In-Context Learning Agent for Formal Theorem-Proving*. [arXiv:2310.04353](https://arxiv.org/abs/2310.04353). Conceptual root for stateful, backtracking, verifier-in-the-loop tactic search.
- **READ:** InternLM2.5-StepProver — *Advancing Automated Theorem Proving via Expert Iteration on Large-Scale Lean Problems*. [arXiv:2410.15700](https://arxiv.org/abs/2410.15700). Evidence for best-first tactic-state search; trained critic and compute are not transferable.
- **READ:** Delta Prover — *Solving Formal Math Problems by Decomposition and Iterative Reflection*. [arXiv:2507.15225](https://arxiv.org/abs/2507.15225). Evidence for explicit Lean-backed subproblem management rather than an unverified skeleton.
- **READ:** LeanSearch v2 — *Global Premise Retrieval for Lean 4 Theorem Proving*. [arXiv:2605.13137](https://arxiv.org/abs/2605.13137). Recent evidence that premise retrieval affects downstream proving; use only the lesson, not its external runtime service.
- **READ:** Mathlib tactic reference. [`exact?`, `apply?`, `simp?`, `aesop?`, and related tactics](https://leanprover-community.github.io/mathlib4_docs/tactics.html).
- **READ:** Mathlib `#find`/`find` documentation. [Mathlib.Tactic.Find](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Tactic/Find.html).
- **SKIM:** Lean community guide. [Searching for Theorems in Mathlib](https://leanprover-community.github.io/blog/posts/searching-for-theorems-in-mathlib/).

All recommendations above are inferences for this project under its constraints. Published headline scores are not used as expected performance estimates because their models, training, retrieval, and compute differ materially from Q/G and the local harness.
