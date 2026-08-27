# Recommendations after the S_dev six-arm experiment

**Date:** 2026-08-26  
**Status:** development recommendations; no `S_eval` results inspected  
**Input:** [`EXPERIMENT_S_dev_matrix.md`](EXPERIMENT_S_dev_matrix.md)  
**Scope:** improve the two-fixed-model Lean agent and make the scientific comparison defensible under the $1/problem and eight-hour limits.

---

## 0. Executive decision

Do **not** freeze the current six-arm interpretation yet. The strongest next agent is not an unconditional cross-model repairer or a learned problem router. It is an executable, Lean-gated portfolio of **two model-local repair trajectories**:

```text
GPT-OSS proposal → GPT-OSS diagnostic repair(s) → Lean
                         |
                         | unresolved
                         v
Qwen fresh proposal → Qwen diagnostic repair(s) → Lean
```

Use GPT-OSS first because `R-G` is currently the best arm by both solves and observed API cost. If its trajectory fails, start Qwen from the original problem—not from GPT-OSS’s failed proof—and let Qwen repair its own candidate. Stop at the first comparator-safe Lean success.

This recommendation follows directly from the observed matrix:

- `R-G = 5/9` at $0.05023.
- `R-Q = 4/9` at $0.05630.
- `R-G ∪ R-Q = 6/9`, equal to the union of every observed arm.
- Running both complete trajectories would have cost $0.10653 across nine problems, approximately **$0.01184/problem**, before savings from sequential early stopping.
- Their combined reported wall time is 7,142 seconds across nine problems, approximately **13.2 minutes/problem** if both always run—far below the eight-hour limit, though per-problem tails still need checking.
- Cross-model repair provides no observed gain over model-local repair.

The best scientific story is:

> **Lean-gated portfolio of model-local repair trajectories.** Compiler diagnostics drive targeted repair; heterogeneous models contribute independent proposal diversity. Cross-model repair is included only if a paired candidate-replay experiment demonstrates a residual benefit.

This is simple, constraint-compatible, and more defensible than claiming that one model should repair the other because it has a different “persona.”

---

## 1. What the current experiment establishes

### 1.1 Strongest positive signal: source-aware same-model repair

The clearest result is `R-G`: 5/9, versus `S-G`: 4/9, with fewer maximum turns and lower realized cost. `R-Q` similarly improves from 3/9 to 4/9 relative to `S-Q`. Both repair arms solve `p10_factorial_pow`, which neither kit-baseline arm solves.

This is consistent with the formal-proof literature: a failed proof plus exact Lean diagnostics is a high-information state. The repair model can edit a concrete artifact instead of guessing what source produced a diagnostic.

The safe claim is:

> In one S_dev run, source-aware structured repair was more successful and more cost-efficient than the kit’s memoryless multi-turn baseline for both model IDs.

Do not yet claim a causal effect size. The comparison changes more than one factor, as explained in Section 2.

### 1.2 Strong model complementarity signal

The models have different observed coverage:

- `p05_gcd_mersenne` is covered by the GPT-OSS-side successful arms.
- `p06_pow_mod` is covered by the Qwen-proposer arms.
- `putnam_2018_a1` is covered by GPT-OSS solo/repair and both handoff configurations, but not by `R-Q`.
- `p10_factorial_pow` is unlocked by both same-model repair arms.

The union of the two same-model repair arms is therefore 6/9. That is the highest executable-looking combination suggested by the existing data, and it requires no cross-repair conversation.

The safe claim is:

> The single run shows complementary coverage between the two model-local trajectories, motivating an executable heterogeneous proposal portfolio.

Do not claim that static problem-feature routing has been learned. Nine development problems are too few, and a rule such as “use G for `Nat.gcd` and Q for `%`” would be development-set overfitting with uncomfortable proximity to problem-specific hardcoding.

### 1.3 Cross-model repair has no positive evidence yet

The handoff totals do not beat same-model repair:

- `H-QG = 4/9`, tied with `R-Q`.
- `H-GQ = 3/9`, below `R-G = 5/9`.

This supports dropping **unconditional** cross-repair from the default design. It does not prove that Qwen intrinsically harms GPT-OSS candidates, because the starting proposals differ between arms.

The safe claim is:

> Cross-model repair showed no advantage in the current independent-arm run; a paired replay is required before attributing the difference to repairer identity.

### 1.4 Real unsolved headroom

No arm solves:

- `p09_imo1964`
- `rmo_2000_2`
- `rmo_2000_3`

These are the only justified targets for one bounded “idea upgrade.” Easy and medium problems should not pay the decomposition cost. The upgrade should activate only after both direct model-local trajectories fail.

---

## 2. Claims that must be corrected before the writeup

### 2.1 The arms are budget-capped, not budget-matched

`VM_BUDGET_USD=0.15` is a common ceiling, but it never binds. Realized arm costs range from $0.02537 to $0.08868. Sharing a non-binding ceiling does not equalize compute.

Use this terminology:

- **Correct:** “All arms ran under the same $0.15/problem safety ceiling.”
- **Incorrect:** “All arms had matched dollar budgets.”

For causal comparisons, report:

1. equal maximum model calls;
2. equal maximum generated-token settings;
3. realized API dollars;
4. realized input/output tokens;
5. Lean-check count;
6. wall time;
7. cumulative success after call 1, 2, 3, …;
8. success versus cumulative dollar spend.

The final policy should still early-stop. Forced equal spending is useful only on `S_dev` when estimating a mechanism’s cumulative curve; it is wasteful in production.

### 2.2 The handoff comparison is not paired on the failed candidate

`R-G` and `H-GQ` independently call GPT-OSS for their proposal. Even with identical prompts and temperature, the returned proof can differ. Thus, `p05` may differ because of proposal randomness, not because Qwen is the repairer.

The clean repairer-identity experiment is:

```text
one frozen failed GPT-OSS candidate + its exact Lean diagnostics
                ├──> GPT-OSS one-step repair ──> Lean
                └──> Qwen one-step repair ─────> Lean
```

Repeat with frozen Qwen candidates. Record the candidate hash to prove both repairers saw identical source. This experiment is cheap and directly answers the heterogeneity question.

### 2.3 S versus R changes failure context and call count

The kit baseline in [`simple_agent.py`](../re-takehome-main/baselines/simple_agent.py) sends the original challenge and the previous diagnostics on later turns, but it does **not** send the previous failed source. The diagnostic can therefore refer to code the model cannot see.

The R/H implementation in [`repair.py`](../re-takehome-main/experiments_agents/repair.py) sends:

- original challenge;
- previous failed proof;
- exact diagnostics;
- repair invariants;
- explicit repair role.

It also caps at four attempts instead of S’s eight. Therefore, S versus R is a valid comparison of two operational protocols, but it does not isolate which R component matters.

Add a four-call independent-sampling control:

- `Fresh-G4`: four independent complete GPT-OSS proposals, each checked by Lean.
- `Repair-G4`: one GPT-OSS proposal plus three source-aware repairs.

Then repeat for Qwen only if time permits. This is the cleanest test of “repair trajectory versus best-of-four sampling.”

### 2.4 One stochastic run over nine problems is descriptive

The current run is excellent for selecting what to test next. It is not enough to establish:

- stable model specialization;
- cross-model harm;
- a precise repair effect;
- statistical superiority of 5/9 over 4/9.

Run three independent repetitions of the shortlisted development arms. If the API has no reliable seed parameter, record them as repeated stochastic trials rather than seeded replicas. Report per-problem solve frequency and the paired overlap table.

Do not repeatedly run `S_eval`. It remains a one-shot holdout after the code and protocol are frozen.

---

## 3. Recommended next-arm matrix

### 3.1 Minimum decisive matrix

| Arm | Maximum calls | Exact mechanism | Primary question |
|---|---:|---|---|
| `Fresh-G4` | 4 | Four independent G proposals; Lean accepts any | Does repair beat equal-call independent sampling? |
| `Repair-G4` | 4 | Existing `R-G`: G proposal + up to three G repairs | Strongest current single trajectory |
| `Portfolio-GQ8` | 8 | `Repair-G4`; if unresolved, fresh Q proposal + up to three Q repairs | Does heterogeneous proposal diversity improve the ceiling? |
| `Portfolio-GG8` | 8 | Two independent four-call G repair trajectories | Does heterogeneity beat a same-model portfolio? |
| `Portfolio-QQ8` | 8 | Two independent four-call Q repair trajectories | Completes the same-model portfolio controls |
| `Replay-G→G/Q` | 3 | One frozen G proposal, then one repair each by G and Q | Does cross-model repair help on identical failures? |
| `Replay-Q→Q/G` | 3 | One frozen Q proposal, then one repair each by Q and G | Reverse-direction repairer effect |

The most important comparison is `Portfolio-GQ8` versus `Portfolio-GG8`. Both have the same maximum eight calls and the same two-trajectory protocol. Only the identity of the second trajectory changes.

`Portfolio-QQ8` is scientifically useful but lower priority if deadline pressure is severe. `R-G` is currently stronger than `R-Q`, so G is the natural homogeneous reference.

### 3.2 How each portfolio trajectory must behave

Each second trajectory starts from scratch:

- original problem description;
- original Lean challenge;
- no previous model’s proof;
- no previous model’s diagnostics;
- same proposal prompt and configuration as its ordinary R arm.

This preserves proposal diversity and prevents the second model from anchoring on the first model’s strategy.

Within a trajectory, the same model receives its own last/best candidate plus exact diagnostics. That is source-aware repair.

### 3.3 Early stopping and research accounting

The production-like policy should stop immediately after a valid, integrity-preserving Lean candidate. For development analysis, log the planned maximum and realized usage separately.

If an arm stops early, it is still fair as a policy comparison. For a pure causal test of repair versus sampling, optionally force generation of all four development candidates and derive the cumulative pass curve afterward. Never do that on `S_eval` or in the final agent.

### 3.4 Recommended repetitions

Run each shortlisted arm three times on all nine `S_dev` problems:

1. `Fresh-G4` ×3
2. `Repair-G4` ×3, counting the existing run as one only if configuration/artifacts are fully comparable
3. `Portfolio-GQ8` ×3
4. `Portfolio-GG8` ×3
5. Candidate replay on at least three failed candidate instances from each proposer direction

Add `Portfolio-QQ8` ×3 only if time permits. The observed costs make these repetitions affordable within the laboratory budget.

---

## 4. Recommended final-agent architecture

### 4.1 Default eight-call portfolio

```text
INPUT: problem description + immutable Lean challenge

Trajectory 1: GPT-OSS
  call 1: independent complete proof
  Lean + integrity check
  calls 2–4: source-aware GPT-OSS repairs, subject to early stop

if accepted: RETURN

Trajectory 2: Qwen
  call 5: fresh independent complete proof
  Lean + integrity check
  calls 6–8: source-aware Qwen repairs, subject to early stop

if accepted: RETURN
otherwise: RETURN best integrity-preserving candidate as failure artifact
```

This design has the same maximum eight model calls as the current S arms. It is more scientifically interesting because it separates the two roles of test-time compute:

- local improvement inside a candidate trajectory;
- global diversity through a new proposer/model trajectory.

### 4.2 Why GPT-OSS should go first

Current evidence:

- higher solve count (`R-G 5` versus `R-Q 4`);
- lower aggregate API cost ($0.05023 versus $0.05630);
- unique coverage of `p05` and `putnam_2018_a1` relative to R-Q.

GPT-OSS is slower in aggregate, but the eight-hour per-problem cap makes solve rate and API efficiency more important than a modest average latency difference. If a final deployment values throughput more strongly, compare Q-first and G-first using replayed/frozen candidates; ordering should change realized cost/latency, not the underlying union.

### 4.3 Do not statically route by theorem vocabulary

Avoid rules such as:

- `%` or numeric answer → Qwen;
- `Nat.gcd` → GPT-OSS;
- Putnam → GPT-OSS.

They fit one or two observed development points and may fail immediately on holdout. Because both trajectories are cheap, execute both sequentially rather than guessing. If future data supports a router, it must use broad, predeclared structural features and be tested out of sample.

### 4.4 Diagnostic routing is safer than problem routing

A small deterministic diagnostic router is justified because it reacts to verifiable runtime state rather than problem identity.

| Lean/output category | Recommended next action |
|---|---|
| No extractable Lean file / repeated unchanged source | One same-model formatting correction; then abandon trajectory |
| Parse error | Same-model minimal syntax repair |
| Elaboration/type/unknown identifier | Same-model local library/type repair |
| Local tactic failure or unsolved goal with otherwise elaborating file | Same-model proof-gap repair |
| Same semantic/tactic failure after two non-improving repairs | End trajectory; start fresh other-model proposal |
| Timeout | One controlled simplification/new proposal; do not blindly repeat the same candidate |
| Both model-local trajectories fail semantically | Optional bounded plan/lemma upgrade, only if validated on S_dev |

Implement the router with deterministic message patterns and conservative fallback. Do not spend another model call asking an LLM to classify a Lean diagnostic.

---

## 5. One bounded upgrade for the three never-solved problems

### 5.1 Compact formal plan / lemma decomposition

After both model-local trajectories fail with semantic or persistent unsolved-goal errors, test this development-only upgrade:

```text
best failed proof + exact Lean diagnostics
        ↓
planner emits at most 3 exact Lean lemma statements and dependencies
        ↓
formalizer attempts the lemmas/final assembly
        ↓
Lean verifies every retained lemma and the final file
```

The workspace must contain only:

- exact lemma name;
- exact Lean statement;
- accepted proof;
- dependencies;
- remaining obligation.

Never put unverified prose claims into the trusted workspace. Never accept `sorry`, `admit`, a weakened theorem, or an altered numeric-answer definition.

### 5.2 Keep the total at eight calls

Do not silently turn the eight-call portfolio into a ten- or twelve-call system. First build a success-by-turn curve from the existing R logs.

If third repairs have little marginal value, compare:

| Design | Allocation |
|---|---|
| `Portfolio-GQ8` | G: 1+3, Q: 1+3 |
| `Routed-GQ-Plan8` | G: 1+2, Q: 1+2, plan: 1, fill/assemble: 1 |

This makes decomposition a protocol change rather than hidden extra compute.

### 5.3 Kill criteria

Drop the plan/lemma branch if any of the following holds across three development repetitions:

- no previously unsolved problem becomes comparator-accepted;
- it produces no accepted helper lemma on the triggered problems;
- its accepted-proofs-per-dollar is worse than allocating the same two calls to fresh proposals;
- it causes frequent statement-integrity or source-assembly failures;
- p90 per-problem spend or wall time approaches the hard cap without a solve gain.

The default submission should remain the simple portfolio if the upgrade does not clear these gates.

---

## 6. Code-level hardening recommendations

### 6.1 Preserve the best repair checkpoint

[`repair.py`](../re-takehome-main/experiments_agents/repair.py) always feeds the most recent failed candidate into the next repair. A later attempt can regress from an elaborating proof to a parse error, and the agent then repairs the regression.

Maintain a deterministic `best_so_far` tier:

1. statement/definition integrity passes;
2. source extraction succeeds;
3. parses;
4. elaborates without unknown identifiers/type errors;
5. fewer primary errors;
6. fewer unsolved goals;
7. smaller edit on a tie.

This ranking chooses the next repair seed only. It never counts as correctness; final acceptance remains comparator-safe Lean success.

### 6.2 Improve stall detection

The current loop stops as soon as the normalized diagnostic repeats once. That can be too aggressive: a candidate may change materially while leaving the same remaining goal/error text.

Recommended rule:

- stop immediately if candidate hash and normalized primary diagnostic both repeat;
- otherwise require two consecutive non-improving attempts;
- reset the stall counter only on an actual tier improvement, not merely different whitespace/line positions;
- start the next independent model trajectory on stall rather than spending cross-model repair on the same artifact.

Ablate current threshold versus the revised threshold on `S_dev`. Do not tune it separately per problem.

### 6.3 Preserve the root diagnostic

`format_messages()` currently concatenates messages and keeps the last 6,000 characters. For long error lists, this can remove the first/root parser or elaboration error and preserve only cascading failures.

Instead retain:

- first primary error;
- errors at the reported failing span;
- final unsolved-goal state;
- timeout marker;
- a compact count by severity/category.

If raw text still requires truncation, use first 3,000 + last 3,000 characters with an explicit truncation marker.

### 6.4 Make extraction failure explicit

`extract_lean()` silently falls back to the previous candidate when no fenced or import-containing Lean source is found. This can cause the same source to be rechecked and misclassified as mathematical stagnation.

Record:

- `extraction_ok`;
- response hash;
- candidate hash;
- whether fallback was used.

Route one fallback event to a bounded “return complete Lean only” formatting correction. On a second failure, end that trajectory.

### 6.5 Enforce declaration integrity before early return

`lean.check_file()` establishes that a file is valid Lean; it does not necessarily establish comparator equivalence to the original challenge. A model could change:

- theorem statement;
- theorem name;
- required definition;
- numeric answer declaration;
- imports or declarations relevant to comparator behavior.

Before treating REPL acceptance as terminal:

1. compare required theorem/definition names with the manifest;
2. verify theorem headers and required non-proof declarations are unchanged except allowed `sorry` replacements;
3. reject forbidden constructs;
4. verify numeric-answer definitions remain valid required literals where specified;
5. then return for the final comparator.

Prefer proof-body replacement or header hashing over trusting prompt instructions.

### 6.6 Keep complete per-attempt provenance

For every call/check, log:

- protocol arm and trajectory ID;
- proposer/repairer model;
- stage and turn;
- candidate hash and parent hash;
- extraction status;
- integrity status;
- diagnostic category and normalized primary diagnostic;
- Lean accepted/timed out;
- input/output/reasoning tokens if exposed;
- actual API cost;
- LLM latency and Lean latency;
- provider and retry/reroute metadata;
- stop reason.

This makes success-by-call, error transitions, and replay experiments possible without reading private scratch reasoning.

---

## 7. Evaluation and analysis plan

### 7.1 Primary and secondary outcomes

**Primary:** number/fraction of problems accepted by the final comparator.

**Secondary:**

- accepted proofs per API dollar;
- accepted proofs per model call;
- accepted proofs per Lean check;
- cumulative success by call index;
- cumulative success by dollars;
- wall time p50/p90/max;
- model-only and protocol-only coverage;
- error-category transitions;
- regressions and collaboration-only wins.

Do not optimize a diagnostic proxy instead of comparator success.

### 7.2 Required overlap table

For every paired comparison, report:

| Outcome | Count |
|---|---:|
| Both solve | |
| Treatment only solves | |
| Control only solves | |
| Neither solves | |

The most important tables are:

- `Repair-G4` versus `Fresh-G4`;
- `Portfolio-GQ8` versus `Portfolio-GG8`;
- same-model versus cross-model one-step repair on identical candidates.

### 7.3 Repeated-run reporting

With three development repetitions, report:

- mean solve rate across repetitions;
- exact per-problem solve frequency `0/3` through `3/3`;
- paired bootstrap interval over problems, labeled exploratory;
- McNemar/exact paired counts where meaningful;
- all raw runs, not only the best seed.

Because `n=9` is small, emphasize effect size and stability rather than a fragile p-value.

### 7.4 Practical decision thresholds

Adopt `Portfolio-GQ8` over `Portfolio-GG8` only if:

- it does not reduce mean solve rate;
- it produces at least one stable unique solve or a clear cost advantage;
- the gain appears in at least two of three development repetitions rather than one lucky sample;
- p90 spend/wall remains comfortably below the hard cap.

Retain cross-model repair only if paired candidate replay shows more successful repairs or consistently better error transitions than same-model repair on identical inputs. Otherwise, omit it.

If intervals overlap and practical performance is similar, choose the simpler protocol.

---

## 8. Holdout (`S_eval`) protocol

Do not inspect or tune on `S_eval` until all of the following are frozen:

- exact code commit;
- exact model IDs;
- model order;
- proposal/repair prompts;
- temperature and token caps;
- maximum calls;
- stall rule;
- error categories/actions;
- integrity checks;
- plan branch and trigger, if retained;
- provider retry policy;
- per-problem soft and hard cost limits.

### 8.1 Minimum frozen holdout arms

Run once each:

1. `S-Q8` — model A operational solo baseline;
2. `S-G8` — model B operational solo baseline;
3. `Portfolio-GG8` — same-model multi-trajectory protocol control;
4. `Portfolio-GQ8` — heterogeneous proposal portfolio;
5. the routed/plan upgrade only if it passed its development kill criteria and is the declared final candidate.

If budget or deadline requires fewer arms, the non-negotiable set is both solo models, the same-model protocol control, and the final collaboration protocol.

### 8.2 After holdout

- Do not tune prompts or thresholds in response to `S_eval`.
- Report every result, including regressions.
- Keep `S_eval` descriptive because `n=7` is small.
- If a harness/provider failure occurs, apply the predeclared rerun rule; do not selectively rerun model failures.
- Distinguish comparator failure, Lean failure, provider failure, and budget/timeout failure.

---

## 9. Recommended wording for the final research report

### 9.1 Claims supported if the current pattern replicates

> Source-aware compiler repair improves test-time efficiency relative to the kit’s memoryless feedback loop.

> The two fixed models exhibit complementary proposal coverage, and a sequential Lean-selected portfolio captures this diversity more reliably than having one model edit the other’s failed proof.

> Same-model portfolio controls show whether the gain comes from heterogeneous model identity or simply from a second independent trajectory.

> Lean diagnostics provide the coordination signal and Lean/comparator acceptance remains the only correctness decision.

### 9.2 Claims to avoid

Avoid:

- “handoff hurts” without candidate replay;
- “budgets were matched” when only ceilings were shared;
- “GPT-OSS is a math planner and Qwen is a Lean specialist” without task-level evidence;
- “routing learned which model fits each theorem” from nine examples;
- “multi-agent debate improved proof quality” when the protocol is a portfolio plus verifier;
- “6/9 achieved” until the integrated portfolio arm actually runs—currently 6/9 is a derived union;
- any claim that a REPL-accepted altered statement counts as success.

### 9.3 Recommended system name

Use a mechanistic name such as:

- **Verifier-Gated Local-Repair Portfolio**
- **Lean-Gated Dual-Trajectory Repair**
- **Typed Repair Portfolio** if the diagnostic router is retained

Avoid “debate,” “society,” or “swarm”; those names misdescribe the actual source of value.

---

## 10. Deadline-aware execution sequence

### August 26 — Fix measurement and build the decisive arms

1. Implement `Fresh-G4`, `Portfolio-GQ8`, and `Portfolio-GG8`.
2. Add candidate/parent hashes, extraction status, integrity status, stop reason, and per-call cost metadata.
3. Fix root-diagnostic truncation and premature stall detection.
4. Add unit tests for source extraction, repeated candidates, integrity rejection, and early stop.

**Gate:** do not pay for runs until local fake-service tests prove the second trajectory starts fresh and the eight-call cap is enforced.

### August 27 — Development repetitions

1. Run the minimum decisive matrix three times on `S_dev`.
2. Build cumulative solve-by-call and solve-by-dollar tables.
3. Run paired one-step candidate replay for both proposer directions.
4. Inspect all collaboration-only wins and control-only regressions.

**Gate:** select the default portfolio only from predeclared metrics; do not tune individual problem rules.

### August 28 — Optional hard-problem upgrade and freeze

1. Test the compact three-lemma branch only on the three never-solved development problems.
2. Compare against spending the same two calls on fresh proposals.
3. Apply the kill criteria.
4. Freeze commit, prompts, caps, router, model order, and evaluation commands.

**Gate:** if the upgrade is not clearly positive, submit the simpler portfolio.

### August 29 — One-shot holdout and writeup

1. Run the frozen mandatory holdout arms once on `S_eval`.
2. Validate every accepted solution with the final comparator.
3. Produce the overlap, cost, call, and failure tables.
4. Write limitations with the same prominence as positive results.

### August 30 — Buffer and submission

1. Reproduce the final selected run configuration from the runbook.
2. Verify repository cleanliness, documented environment, and exact submission command.
3. Finalize the PDF and repository link.
4. Do not use the buffer for post-holdout tuning.

---

## 11. Final ranked recommendations

| Rank | Recommendation | Expected value | Risk | Kill criterion |
|---:|---|---|---|---|
| **1** | Run an executable `Portfolio-GQ8`: G self-repair trajectory, then fresh Q self-repair trajectory | Captures observed 6/9 R-arm union under the same eight-call maximum as S | Union may be stochastic | No stable gain over `Portfolio-GG8` across three dev repetitions |
| **2** | Add `Fresh-G4` and `Portfolio-GG8` controls | Separates repair from extra sampling and heterogeneity from a second trajectory | More evaluation arms | None; these are required for the scientific claim |
| **3** | Run paired candidate replay for repairer identity | Cleanest test of cross-model repair | One-step result may not capture long trajectories | Cross repair has no paired advantage; then remove it |
| **4** | Harden best checkpoint, stall detection, diagnostics, extraction, and statement integrity | Prevents avoidable regressions and comparator-invalid early stops | Engineering time | Unit tests fail or complexity threatens deadline; prioritize integrity + diagnostics first |
| **5** | Add a conditional ≤3-lemma plan only after both trajectories fail | Only plausible route beyond the current 6/9 ceiling | Complexity and wasted calls | No new solve/verified helper lemma under an equal eight-call comparison |

---

## 12. Freeze checklist

- [ ] `S_eval` remains unopened/uninspected.
- [ ] Current results are described as one development repetition.
- [ ] Common budget ceiling is not mislabeled as matched realized spend.
- [ ] `Fresh-G4` exists and is tested against `Repair-G4`.
- [ ] `Portfolio-GQ8` is an actual run, not a derived union.
- [ ] `Portfolio-GG8` is the primary same-model portfolio control.
- [ ] Second trajectories start from the original challenge.
- [ ] Candidate replay uses identical source/diagnostics and recorded hashes.
- [ ] Final agent has a hard maximum of eight model calls unless a different cap is explicitly justified.
- [ ] Success-by-call and success-by-dollar curves are produced.
- [ ] Statement/definition integrity is checked before early success.
- [ ] Root Lean diagnostics are preserved.
- [ ] Repeated candidate/diagnostic stall logic is tested.
- [ ] Model IDs, prompts, temperature, token caps, retries, timeouts, and model order are frozen.
- [ ] Plan/lemma branch either passes its kill criteria or is removed.
- [ ] Both solo models, same-model protocol control, and collaboration protocol are scheduled for one-shot holdout.
- [ ] No result is called “multi-model improvement” unless it beats the matched same-model portfolio control.

---

## Final recommendation in one sentence

Build and evaluate a **GPT-OSS-first, Qwen-second Lean-gated portfolio in which each model repairs only its own candidate**, use an eight-call same-model portfolio as the causal control, and add compact lemma decomposition only if it rescues the three never-solved development problems without extra compute.
