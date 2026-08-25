# SOTA memo: multi-model coordination for formal mathematics and Lean 4

**Date:** 2026-08-24  
**Decision context:** exactly two fixed chat-model APIs; local Lean 4 + Mathlib; unchanged theorem statements; no runtime web/RAG; target API spend at or below $1/problem.  
**Evidence convention:** “formal” means kernel-checked proof acceptance, not answer accuracy. “Matched” means the comparison substantially controls calls/tokens/verifier queries; “matched-ish” means it controls one major resource but not all. Reported results are not treated as causal unless the protocol supports that reading.

## Section A — Executive summary

- Lean feedback is the highest-value coordination signal: compile every candidate, expose the exact diagnostic and local proof state, and accept only a clean Lean check.
- Recent SOTA comes mainly from verified sampling, targeted repair, decomposition, and very large test-time compute—not from long conversations among agents.
- Whole-proof generation is the right cheap first shot; tactic search and recursive decomposition belong behind an escalation gate.
- Repair should preserve the best verified progress and edit the smallest failing region; generic “try again” wastes budget and often regresses.
- Dual proposals help when they are genuinely diverse and Lean selects; proof-text voting and LLM judging add little once a kernel is available.
- Short, formalizable plans and 2–4 named lemmas can rescue strategy failures, but natural-language solutions can also distract Lean provers.
- Same-model role separation already produces real gains; there is no public, matched-budget Lean evidence that heterogeneous models are intrinsically better.
- Cross-model value is therefore a hypothesis about complementary errors, to be tested against same-model propose/repair at equal calls, tokens, dollars, and Lean checks.
- Error-conditioned routing is the best “idea upgrade”: keep syntax/library repairs cheap and local; spend the strong model only on repeated semantic or decomposition failures.
- Early stopping is part of the algorithm: stop on success, repeated identical diagnostics, no checkpoint improvement, or the per-problem dollar cap.
- **Does not transfer:** AlphaProof/Seed-Prover-scale RL, thousands of samples, multi-day search, and test-time training.
- **Does not transfer:** external retrieval services or premise indexes not guaranteed to match the local Mathlib build.
- **Does not transfer:** free-form multi-agent debate, majority vote over proof text, large persona swarms, and unconstrained blackboards.
- **Default modern stack for one week:** one candidate from each fixed model → Lean selection → deterministic error router → at most two local repairs → one cross-model critic/patch handoff on stagnation → optional compact 2–4-lemma plan only for semantic failures → hard early stop and checkpointed best candidate.

## Section B — Landscape map

| Mechanism | Informal math evidence | Formal/Lean evidence | Cost | Complexity | Transfer to 2-model+$1 | Notes |
|---|---|---|---:|---:|---|---|
| Whole-proof generation | Strong for solution drafting | Strong baseline in DeepSeek-Prover, Goedel-Prover, Kimina | Low per draw; high at large pass@k | Low | **High** | Best first action; sampling gains can hide 100–1000x compute. |
| Compiler-guided local repair | Coding agents and answer refinement suggest it | Baldur root; MA-LoT, APOLLO, Delta, Seed-Prover | Low–Med | Low | **High** | Most defensible core loop; use exact diagnostics and smallest-edit prompts. |
| Dual sampling + Lean selection | Self-consistency is strong answer-only baseline | Best-of-N is a universal formal baseline | Med | Low | **High** | Lean is an exact selector only for fully accepted proofs; partial ranking needs care. |
| Error-type routing | Weakly studied outside code | FormalMATH error taxonomy; APOLLO’s modular path | Low | Low–Med | **High** | Direct causal evidence is thin, but it is cheap and highly ablatable. |
| Planner → formalizer | Strong on hard informal math, mixed on easy tasks | DSP root; DeepSeek-Prover-V2; Delta; Aristotle; contrary FormalMATH evidence | Med | Med | **Med–High** | Make it conditional and force Lean-shaped lemmas, not a long essay. |
| Minimal lemma workspace | Hierarchical solving helps hard contests | LEGO-Prover/POETRY roots; Delta, Seed-Prover, Aristotle | Med–High | Med | **Med** | Useful after monolithic stagnation; cap at 2–4 obligations. |
| Tactic-level tree search / critic | Search is standard in planning | LeanDojo, InternLM2.5-StepProver, DeepSeek-Prover-V1.5 | High–Very high | High | **Low–Med** | Valuable field baseline, but poor one-week/$1 default. |
| Premise retrieval / library search | RAG often helps knowledge tasks | ReProver/COPRA; premise selection is material | Med | High | **Low** | Runtime assumption forbids external retrieval; local error-driven identifier use remains allowed. |
| Same-model dual roles | Iterative refinement often helps | MA-LoT and many repair systems | Med | Low | **High** | Mandatory control for any heterogeneous claim. |
| Heterogeneous proposer/repairer | ReConcile and some MAD studies support diversity | No clean matched-budget Lean result found | Med | Low | **Med (experimental)** | Test only as a routed handoff; do not make diversity the causal claim in advance. |
| Free-form debate / majority vote | Mixed; often loses to CoT/self-consistency | No convincing Lean-specific advantage | High | Med | **Low** | Kernel feedback dominates persuasion; conversations duplicate tokens. |
| Adaptive compute / early stop | Test-time scaling is broad | APOLLO, Delta, Seed-Prover tiers | Variable | Low–Med | **High** | The practical way to fit a dollar cap; report both cap and realized spend. |
| Test-time RL / massive conjecture generation | Reported at olympiad level | AlphaProof, Seed-Prover heavy modes | Extreme | Extreme | **Low** | Strong result, wrong operating regime. |

### Answers to RQ1, RQ3, and RQ4 in one view

The dominant recent formal pipeline is **whole proof first, Lean check, then either targeted repair or verified search**. Whole-proof models exploit long-range mathematical structure cheaply; stepwise provers expose more intermediate states but pay many model/verifier calls. Temperature or prompt variation matters because Lean can reject invalid diversity for free relative to another LLM judgment, but the useful comparison is pass@k against the same k—not a pass@1024 headline against pass@1. Premise retrieval materially helps tactic systems, yet it is version-sensitive and outside this runtime unless implemented entirely locally.

Most SOTA headlines mix protocol with compute. DeepSeek-Prover-V1.5 shows a modest residual search gain at a fixed sample/token envelope; MA-LoT shows targeted correction beating comparably expensive whole-proof sampling, though with more tokens and specialized training; Delta shows repair/decomposition scaling better than best-of-N at fixed call budgets but at budgets far above ours; APOLLO reports large sample-efficiency gains but does not isolate every component. Conversely, AlphaProof and Seed-Prover demonstrate what is possible with formal feedback, not what is feasible for two APIs under $1.

Evidence must stay separated by track. ReConcile and heterogeneous debate studies are **informal/answer-level** evidence about complementary errors. DSP, Baldur, ReProver, and the recent Lean agents are **formal synthesis** evidence. FormalMATH’s multi-LLM pipeline concerns benchmark statement validation, not runtime proof collaboration. AIME/IMO answer accuracy therefore motivates planning prompts at most; it does not establish Lean success.

## Section C — Deep dives

### DSP — Draft, Sketch, and Prove (2022; conceptual root)

- **Type:** autoformalization / other formal whole-proof
- **Venue / link:** NeurIPS 2022; [arXiv:2210.12283](https://arxiv.org/abs/2210.12283)
- **Core mechanism:** DSP separates an informal mathematical draft from a formal proof sketch whose holes become subproblems for an automated prover. The sketch transfers high-level structure while delegating routine closure. This is the clean conceptual root of planner–formalizer–verifier pipelines, although its experiments use Isabelle rather than Lean 4 and depend on a separate automated prover.
- **Coordination pattern:** planner–executor; hierarchical decomposition
- **Verifier role:** other (Isabelle)
- **Models used:** homogeneous/one language model in the reported pipeline, plus an automated theorem prover
- **Headline result:** on the Isabelle miniF2F test split, the reported proof rate rises from 20.9% for the prior language-model setup to 39.3% for DSP; formal verification, not answer-only.
- **Budget honesty:** not a matched-dollar result; the pipeline allows many formalization/proving attempts and adds an automated prover.
- **Why it worked (authors + your read):** an informal proof supplies global structure while holes keep formal search local. The durable causal object is the *explicit obligation boundary*, not free-form prose.
- **Failure modes:** a wrong sketch decomposes the problem into false or useless obligations; translation can lose side conditions; results do not directly establish Lean 4 behavior.
- **Transfer recipe for us:**
  1. Do not run DSP on every problem.
  2. Trigger it only after direct proofs fail with semantic/unsolved-goal errors.
  3. Ask the strong model for at most three Lean-shaped lemma statements.
  4. Require the original theorem statement to remain byte-for-byte unchanged.
  5. Have Lean check each lemma and the final assembly; discard prose once formal obligations exist.
  6. Drop the external automated prover and any broad premise retrieval.
- **Ablation we should run if we adopt it:** direct repair vs one compact plan with the same total model calls and Lean checks; cross-model planner/formalizer vs same-model roles.
- **Confidence in this summary:** high

### Baldur — Whole-Proof Generation and Repair with Large Language Models (2023; conceptual root)

- **Type:** other formal whole-proof
- **Venue / link:** ESEC/FSE 2023; [arXiv:2303.04910](https://arxiv.org/abs/2303.04910)
- **Core mechanism:** Baldur generates complete Isabelle proofs, sends failures to the prover, and invokes a repair model with the failed proof plus error message. Repair is trained as a distinct task rather than phrased as an unconstrained retry. The system can also complement a search prover (Thor), showing that generative and search failures are not identical.
- **Coordination pattern:** propose → verify → repair; specialized generator–repairer
- **Verifier role:** other (Isabelle)
- **Models used:** homogeneous model family with separately trained generation and repair behavior; not a heterogeneous API pair
- **Headline result:** Baldur combined with Thor proves 65.7% of 6,336 held-out Isabelle theorems and adds 8.7 percentage points over Thor alone; formal verification.
- **Budget honesty:** extra repair/generation compute is not fully matched against an equally sampled Thor baseline; complementary coverage is clearer than the causal size of repair.
- **Why it worked (authors + your read):** the compiler message identifies a concrete defect, and whole-proof context lets the model make coherent edits. The result is strong evidence for formal feedback, not for multi-model debate.
- **Failure modes:** repair can rewrite correct regions, cycle on the same diagnostic, or fail when the proof idea rather than syntax is wrong; Isabelle transfer is imperfect.
- **Transfer recipe for us:**
  1. Store the exact failed Lean source and diagnostics.
  2. Ask for a complete replacement proof block, but demand the smallest conceptual change.
  3. Protect imports and theorem statement.
  4. Check immediately; never let one model self-certify.
  5. Detect repeated diagnostics and hand off or stop.
  6. Treat separate models as an ablation, not a requirement of the mechanism.
- **Ablation we should run if we adopt it:** fresh resample vs diagnostic repair at equal one-call increments; same-model repair vs cross-model repair.
- **Confidence in this summary:** high

### LeanDojo / ReProver — Theorem Proving with Retrieval-Augmented Language Models (2023; conceptual root)

- **Type:** tactic RL / other
- **Venue / link:** NeurIPS 2023; [arXiv:2306.15626](https://arxiv.org/abs/2306.15626)
- **Core mechanism:** LeanDojo supplies a Lean interaction environment and a benchmark of 98,734 theorems; ReProver retrieves premises and predicts tactics inside proof search. The benchmark carefully exposes which premises are accessible at a theorem’s location and uses hard negatives for retrieval. This made library awareness a first-class part of formal proving rather than leaving the model to hallucinate names.
- **Coordination pattern:** tactic search; premise-selection portfolio
- **Verifier role:** lean
- **Models used:** one retrieval-augmented tactic model; no runtime model collaboration
- **Headline result:** ReProver substantially outperforms its non-retrieval variant and the paper’s GPT-4 prompting baseline on LeanDojo’s random and challenging splits; the exact rates vary by split/configuration, so this memo does not compress them into one number.
- **Budget honesty:** the retrieval ablation is informative, but the operating regime includes a trained retriever, indexed corpus, and proof search unavailable in our minimal API setting.
- **Why it worked (authors + your read):** many “reasoning” failures are actually library-name and premise-access failures. Restricting candidates to valid local declarations raises both accuracy and diagnostic quality.
- **Failure modes:** index/version mismatch, inaccessible declarations, retrieval latency, tactic branching, and benchmark leakage through nearby proofs.
- **Transfer recipe for us:**
  1. Do not build a RAG service this week.
  2. Pin and report the exact Lean/Mathlib version.
  3. Return unknown-identifier and type-mismatch diagnostics verbatim.
  4. Permit only local, already-available Lean inspection if the harness exposes it.
  5. Encourage common Mathlib automation before exotic lemma-name guesses.
  6. Mark a future local premise index as a separate system, not a coordination tweak.
- **Ablation we should run if we adopt it:** error messages only vs any allowed local declaration context, with the same model calls and search cap.
- **Confidence in this summary:** high

### DeepSeek-Prover-V1.5 — Harnessing Proof Assistant Feedback for Reinforcement Learning and Monte-Carlo Tree Search (2024)

- **Type:** Lean whole-proof / tactic RL
- **Venue / link:** [arXiv:2408.08152](https://arxiv.org/abs/2408.08152)
- **Core mechanism:** V1.5 combines whole-proof generation, reinforcement learning from Lean acceptance, and RMaxTS search over proof states. The search can start from long chain-of-thought/whole-proof candidates and use proof-assistant feedback to allocate later samples. It is important because it compares search and non-search modes within one model family rather than only reporting a giant pass@k.
- **Coordination pattern:** propose → verify → search/repair; adaptive portfolio
- **Verifier role:** lean
- **Models used:** homogeneous DeepSeek-Prover-V1.5 family
- **Headline result:** miniF2F test reaches 60.2% for single-pass CoT at 16×6,400 tokens and 63.5% for RMaxTS with mixed proof styles at 32×6,400; ProofNet test reaches 25.3%. The paper also reports 51.6% miniF2F pass@128 in its pass@k comparison.
- **Budget honesty:** unusually useful matched-ish evidence: at 16×6,400, CoT single-pass is 60.2% and CoT RMaxTS 62.7%; mixed-style RMaxTS at a larger 32-sample allocation reaches 63.5%. It controls token/sample envelopes better than most SOTA reports, but training/RL and wall time are not ours.
- **Why it worked (authors + your read):** formal feedback shapes both training and test-time allocation; search adds a modest residual over diverse whole-proof sampling. The ablation on intrinsic reward shows that the search policy, not the MCTS label alone, matters.
- **Failure modes:** gains are small relative to compute, search scaffolding is complex, and an RL-specialized local model is unlike two generic chat APIs.
- **Transfer recipe for us:**
  1. Copy the portfolio idea, not MCTS.
  2. Sample different proof styles/prompts early.
  3. Use Lean to decide success and diagnose failure.
  4. Spend later calls only on the most promising failed candidate.
  5. Keep a hard cap; do not simulate a tree with chat transcripts.
  6. Report pass@1 and success at each cumulative call count.
- **Ablation we should run if we adopt it:** two independent full proofs vs one proof + one repair; fixed round-robin vs diagnostic adaptive allocation, all at identical call/token/Lean-check caps.
- **Confidence in this summary:** high

### MA-LoT — Model-Collaboration Lean-based Long Chain-of-Thought Reasoning enhances Formal Theorem Proving (2025)

- **Type:** Lean whole-proof / multi-agent
- **Venue / link:** [arXiv:2503.03205](https://arxiv.org/abs/2503.03205)
- **Core mechanism:** MA-LoT separates whole-proof generation from formal-error analysis and correction, repeatedly checking with Lean. Its LoT-Solver is trained on long formal reasoning, including 64,912 correction examples. Despite “model-collaboration” in the name, the main runtime evidence is role specialization around the same underlying specialized solver—not a clean comparison of two different model IDs.
- **Coordination pattern:** propose → verify → repair; same-model dual-role
- **Verifier role:** lean
- **Models used:** homogeneous specialized LoT-Solver roles; experiments span Goedel- and DeepSeek-derived bases, but do not establish a heterogeneous runtime pair advantage
- **Headline result:** 61.07% on Lean4 miniF2F test, compared with 55.33% for the paper’s Goedel-Prover whole-proof baseline and 50.70% for InternLM-Step-Prover. In a staged Goedel run, whole proof is 54.92%, then 59.43%, 61.07%, and 61.89% after successive correction rounds.
- **Budget honesty:** matched-ish, not fully matched. The useful 16 initial + 2×8 repair configuration gets 61.07% versus 58.20% for pass@32 whole-proof, but averages about 658 vs 492 generated tokens and substantially more GPU work. The authors also compare against a roughly 1.7x-compute whole-proof baseline and retain a reported advantage, though specialized correction training remains a confound.
- **Why it worked (authors + your read):** correction prompts consume a high-information Lean signal and focus new tokens on a known failure. A generic “prover as corrector” improves much less, supporting task framing/training rather than mere extra calls.
- **Failure modes:** custom training data is unavailable to us; later rounds have diminishing returns; repeated full rewrites can regress; the name can mislead readers into attributing gains to heterogeneous models.
- **Transfer recipe for us:**
  1. Separate generation and repair prompts even if the model ID is unchanged.
  2. Include exact diagnostics and the current best source.
  3. Ask for diagnosis plus patched proof, not another independent essay.
  4. Keep at most two ordinary correction rounds.
  5. Use the second model only after stagnation or for an explicit experimental arm.
  6. Log generated tokens because equal call counts are not equal compute.
- **Ablation we should run if we adopt it:** fresh sampling, same-model repair, and cross-model repair under identical per-problem token and Lean-check caps.
- **Confidence in this summary:** high

### DeepSeek-Prover-V2 — Advancing Formal Mathematical Reasoning via Reinforcement Learning for Subgoal Decomposition (2025)

- **Type:** autoformalization / Lean whole-proof / tactic RL
- **Venue / link:** [arXiv:2504.21801](https://arxiv.org/abs/2504.21801)
- **Core mechanism:** a large model first produces a natural-language proof sketch and decomposes a theorem into formally stated subgoals; a smaller prover recursively fills those goals. The combined proof/chain-of-thought data seed reinforcement learning for the released prover models. At inference, the prover is a single trained model—the heterogeneous teacher/student pipeline is mainly data construction, not a two-model runtime result.
- **Coordination pattern:** hierarchical decomposition; planner–executor during data generation
- **Verifier role:** lean
- **Models used:** heterogeneous during training-data generation (DeepSeek-V3 plus a 7B prover); homogeneous specialized prover at evaluation
- **Headline result:** the 671B model reports miniF2F test 61.9% pass@1, 82.4% pass@32, 86.6% pass@1,024, and 88.9% pass@8,192; ProofNet test 37.1% at pass@1,024 and 49 of 658 PutnamBench problems in arXiv v2.
- **Budget honesty:** headline gains combine specialized training, model scale, decomposition data, RL, and huge pass@k. This is not evidence for a <$1 runtime collaboration protocol.
- **Why it worked (authors + your read):** subgoal decomposition generates learnable formal reasoning traces and gives long proofs intermediate supervision. The transferable part is short verified obligations, not the training stack.
- **Failure modes:** incorrect subgoal statements, teacher/student confounds, high sampling budgets, and no direct same-model-vs-cross-model runtime ablation.
- **Transfer recipe for us:**
  1. Use the strong model as a conditional planner only after direct failure.
  2. Ask for 2–4 exact Lean lemma statements and a final assembly sketch.
  3. Reject any plan that changes the theorem statement or adds unproved assumptions.
  4. Let either fixed model fill lemmas, one call at a time.
  5. Cache only kernel-accepted lemmas in the problem-local workspace.
  6. Do not infer that teacher/student diversity proves runtime heterogeneity.
- **Ablation we should run if we adopt it:** direct whole-proof repair vs decomposition at equal calls; A→B vs A→A planner/formalizer; reverse B→A as a smaller diagnostic arm.
- **Confidence in this summary:** high

### APOLLO — Automated LLM and Lean Collaboration for Advanced Formal Reasoning (2025)

- **Type:** Lean whole-proof / multi-agent
- **Venue / link:** [arXiv:2505.05758](https://arxiv.org/abs/2505.05758)
- **Core mechanism:** APOLLO is a modular repair pipeline: refine syntax, locate failing proof blocks, temporarily isolate them as holes, try Lean automation, recursively ask an LLM to fill remaining obligations, reassemble, and recheck with no holes allowed. Its “agents” are mostly deterministic or prompted stages around a prover, not a free-form society of independent model personas. This is a strong example of the verifier doing the routing and filtering.
- **Coordination pattern:** propose → verify → repair; role specialization; error router; hierarchical decomposition
- **Verifier role:** lean
- **Models used:** usually one prover model at a time; the system is model-agnostic, not evidence for heterogeneous pair causality
- **Headline result:** the current paper reports Goedel-Prover-V2 + APOLLO at 84.9% miniF2F with an average 63 samples/344K tokens, matching the raw model’s 84.9% at 128/699K. Kimina-Prover rises from 70.8% raw at 1,024 samples to 75.0% with APOLLO at an average 307 samples; Goedel-Prover-SFT reaches 65.6% with a few hundred average samples versus 64.7% under the paper’s 25,600-sample raw reference. General chat models rise from low single-digit pass@1 to above 40% under the pipeline.
- **Budget honesty:** strong sample-efficiency signal, but not a complete causal ablation. Some baselines come from source publications, average recursive usage is compared with fixed raw pass@k, and tokens/latency/dollars are not simultaneously matched.
- **Why it worked (authors + your read):** the system narrows a global failure to a checkable local obligation and dispatches cheap automation before another LLM call. The key is *failure localization plus strict reassembly*, not the number of named agents.
- **Failure modes:** temporary holes can accidentally survive unless final validation forbids them; recursion can explode; automated tactics may time out; reported averages can hide a long tail above our budget.
- **Transfer recipe for us:**
  1. Never accept `sorry`, `admit`, or a changed theorem statement.
  2. Copy only the localization idea: use diagnostics/line context to identify one failing block.
  3. Try a tiny fixed set of already-permitted Lean tactics only if the harness supports source edits safely.
  4. Ask one model for that local proof, then reassemble and check the whole file.
  5. Cap recursion at one decomposition level and 2–4 obligations.
  6. Report realized calls and tokens, not just the maximum.
- **Ablation we should run if we adopt it:** full-proof repair vs localized block repair at equal model calls; automation-first vs direct LLM repair; always verify final no-hole source.
- **Confidence in this summary:** med–high

### Delta Prover — Solving Formal Math Problems by Decomposition and Iterative Reflection (2025)

- **Type:** Lean whole-proof / multi-agent-like tool-using agent
- **Venue / link:** [arXiv:2507.15225](https://arxiv.org/abs/2507.15225)
- **Core mechanism:** Delta Prover orchestrates Gemini 2.5 Pro with Lean 4 using iterative whole-proof repair and reflective decomposition through a custom Lean DSL. It repairs directly first; after failure, it creates subproblems, proves them, and reuses the results. The agent also retrieves relevant identifiers, an important dependency that does not transfer under our assumed runtime.
- **Coordination pattern:** propose → verify → repair; hierarchical decomposition; blackboard; adaptive compute
- **Verifier role:** lean
- **Models used:** homogeneous single general-purpose model plus Lean and retrieval, not heterogeneous
- **Headline result:** 95.9% on miniF2F test at a reported sample budget of 16,384, versus 49.1% for Gemini best-of-N at the same nominal budget. This is formal success but far outside the $1 regime.
- **Budget honesty:** the fixed-budget studies are unusually informative: at total budget 1,024, allocating more calls to iterative repair per trajectory beats more independent restarts. However, the paper’s “sample budget” is a call cap/scaling coordinate rather than a matched dollar or average per-problem cost, and the headline requires massive compute.
- **Why it worked (authors + your read):** Lean diagnostics preserve trajectory-specific information; repair compounds partial progress; decomposition changes the search space after monolithic stagnation. A highlighted IMO 2019 problem fails after 1,024 repair-only calls but is solved through 83 subproblems at roughly 332 calls—mechanistically vivid, but one case and still enormous.
- **Failure modes:** cost explosion, incorrect or excessive subgoals, custom DSL complexity, retrieval dependence, and a result dominated by a frontier general model plus huge test-time budget.
- **Transfer recipe for us:**
  1. Copy the escalation order: direct repair before decomposition.
  2. Keep a `best_so_far` candidate and compact diagnostic history.
  3. Decompose only after two non-improving semantic failures.
  4. Limit decomposition to one level and at most four lemmas.
  5. Omit the DSL and external retrieval.
  6. Give the second model only the best proof, current error, proven lemmas, and one requested action.
  7. End on success, repeated error, non-improvement, or budget.
- **Ablation we should run if we adopt it:** at fixed four calls, compare four fresh draws, one draw + three repairs, and one draw + one repair + two decomposition calls.
- **Confidence in this summary:** high on reported mechanism/result; med on low-budget transfer

### Seed-Prover — Deep and Broad Reasoning for Automated Theorem Proving (2025)

- **Type:** Lean whole-proof / tactic RL
- **Venue / link:** [arXiv:2507.23726](https://arxiv.org/abs/2507.23726)
- **Core mechanism:** Seed-Prover is a lemma-style whole-proof model that iteratively refines using Lean feedback, previously proved lemmas, and self-summaries. Its light, medium, and heavy inference modes progressively add inner lemma repair, broader sampling, and large conjecture pools. The local lemma store records exact statements, proof terms, difficulty, and dependencies—a disciplined blackboard rather than a chat log.
- **Coordination pattern:** hierarchical decomposition; verified blackboard; adaptive compute
- **Verifier role:** lean
- **Models used:** homogeneous specialized Seed-Prover system; geometry uses a separate specialized engine
- **Headline result:** the paper reports 121/155 (78.1%) formalized past IMO problems, 99.6% on miniF2F test in medium mode, and 331 PutnamBench problems in medium mode. It also reports five of six IMO 2025 problems formally proved across its systems.
- **Budget honesty:** not matched to our regime. Light mode itself corresponds roughly to 8–16 initial samples with 8–16 refinements (64–256 whole-proof-equivalent calls) and one to two hours; heavy mode proposes thousands of conjectures and can run for days. Specialized RL/training and very large inference obscure component causality.
- **Why it worked (authors + your read):** formal feedback plus durable, verified lemmas lets the solver go both deep and broad without trusting natural-language state. Tiered escalation avoids applying the maximum method to every theorem.
- **Failure modes:** massive cost, conjecture sprawl, LLM judging in heavy filtering, self-summary drift, specialized training, and geometry infrastructure unavailable to us.
- **Transfer recipe for us:**
  1. Copy the *schema* of the lemma store, not its scale.
  2. Store only Lean-accepted lemma name, statement, proof, and dependencies.
  3. Cap the store at four problem-local lemmas.
  4. Use three tiers: direct, repair, compact decomposition.
  5. Never generate thousands of conjectures or use an LLM judge.
  6. Restart the final proof once with accepted lemmas in context, then stop.
- **Ablation we should run if we adopt it:** no workspace vs accepted-lemma-only workspace at the same call cap; always-medium vs diagnostic escalation with realized-cost reporting.
- **Confidence in this summary:** med–high; public report is detailed, but the full operating stack is not cheaply reproducible

### Aristotle — IMO-level Automated Theorem Proving (2025)

- **Type:** autoformalization / Lean whole-proof / tactic RL / other
- **Venue / link:** [arXiv:2510.01346](https://arxiv.org/abs/2510.01346)
- **Core mechanism:** Aristotle combines a learned Lean search system with an informal-to-formal loop: draft an informal proof, identify short lemmas, formalize them, inspect compiler errors, correct them, and retain proved lemmas across attempts. Its formal search uses a policy/value-guided graph search, while hard contest proofs receive substantial parallel inference and test-time training. The public report is valuable architectural evidence, not a small-system recipe.
- **Coordination pattern:** planner–formalizer; hierarchical decomposition; verified blackboard; search portfolio
- **Verifier role:** lean
- **Models used:** multiple system components around a very large model; public evidence does not isolate heterogeneous chat-model effects
- **Headline result:** the report presents complete Lean proofs for five of the six IMO 2025 problems from hand-translated formal statements; formal verification. It does not provide a clean low-budget miniF2F-style component ablation for the informal lemma loop.
- **Budget honesty:** uncontrolled for our question: >200B-scale model, many parallel instances, repeated feedback, and test-time training. The statements were hand formalized, which *does* align with our supplied-skeleton setting.
- **Why it worked (authors + your read):** hard proofs need stable intermediate mathematical objects. Keeping proved lemmas while revising only failures prevents the destructive restart behavior of monolithic generation.
- **Failure modes:** enormous engineering/compute, hand-formalization dependence, weak public causal isolation, and search machinery beyond a two-API harness.
- **Transfer recipe for us:**
  1. Use the supplied skeleton as fixed ground truth.
  2. Let the strong model propose a very short lemma plan only after failure.
  3. Prove one lemma at a time and retain only kernel-accepted facts.
  4. Present failed lemmas—not the entire conversation—to the repairer.
  5. Assemble once and run a strict whole-file check.
  6. Do not claim Aristotle-like capability from this stripped protocol.
- **Ablation we should run if we adopt it:** retained verified lemmas vs full restart after each failed assembly, at the same model-call budget.
- **Confidence in this summary:** med

### AlphaProof — Olympiad-Level Formal Mathematical Reasoning with Reinforcement Learning (2025/2026 publication)

- **Type:** autoformalization / tactic RL / other
- **Venue / link:** Nature; [paper](https://www.nature.com/articles/s41586-025-09833-y), [Google Research publication page](https://research.google/pubs/olympiad-level-formal-mathematical-reasoning-with-reinforcement-learning/)
- **Core mechanism:** AlphaProof adapts AlphaZero-style reinforcement learning to Lean, training on a huge synthetic formal corpus and using proof-assistant rewards. For the IMO, natural-language problems were manually translated to formal statements and the prover used extensive problem-specific test-time search/training. The kernel supplies a perfect terminal reward, but almost everything about the optimization scale is outside our setting.
- **Coordination pattern:** search portfolio; verifier-guided RL; adaptive compute
- **Verifier role:** lean
- **Models used:** a specialized homogeneous formal system; AlphaGeometry 2 handles geometry separately in the combined IMO score
- **Headline result:** AlphaProof solved three of five non-geometry IMO 2024 problems; together with AlphaGeometry 2 the system solved four of six and scored 28/42, equivalent to silver-medal performance. These are reported formally checked solutions from manually translated statements.
- **Budget honesty:** maximally unmatched for us: the Nature report describes roughly 100K TPU-days for autoformalization, 80K TPU-days for main training, and millions of test-time variants/multi-day runs. Public claims are credible but not a reproducible <$1 protocol.
- **Why it worked (authors + your read):** formal verification creates an unambiguous learning/search objective, and massive synthetic coverage plus adaptive computation reaches rare long proofs. It validates the *value of the verifier*, not multi-agent dialogue.
- **Failure modes:** scale, manual statement translation, test-time training, sparse reward, and no practical component mapping to two chat APIs.
- **Transfer recipe for us:**
  1. Copy strict Lean acceptance and adaptive stopping only.
  2. Treat the provided theorem statement as immutable.
  3. Log every verifier query and cumulative success curve.
  4. Allocate a few extra calls only when diagnostics indicate progress.
  5. Drop RL, synthetic-data generation, test-time training, and massive search.
- **Ablation we should run if we adopt it:** fixed calls per problem vs progress-gated calls with the same global evaluation budget.
- **Confidence in this summary:** high on the public result; high that direct transfer is low

### FormalMATH — Benchmarking Formal Mathematical Reasoning of Large Language Models (2025)

- **Type:** autoformalization / Lean whole-proof / benchmark
- **Venue / link:** [arXiv:2505.02735](https://arxiv.org/abs/2505.02735)
- **Core mechanism:** FormalMATH contributes 5,560 Lean 4 problems spanning high-school to undergraduate domains and evaluates whole-proof provers under practical and scaled sampling. Its construction uses specialized formalizers, multi-LLM semantic checks, negation-based disproof, and human review; that is benchmark creation, not an available runtime proving method. More useful for us are its guidance and failure analyses.
- **Coordination pattern:** dual sampling/ensemble at evaluation; multi-model semantic validation during dataset construction
- **Verifier role:** lean
- **Models used:** multiple specialized provers; heterogeneous models in data validation, not runtime proof repair
- **Headline result:** the strongest evaluated system solves only 16.46% of the full benchmark at practical pass@32. On FormalMATH-Lite, the reported all-prover ensemble reaches 54.11% at an aggregate 4×3,200 sample regime; this is formal but extremely expensive.
- **Budget honesty:** the benchmark tables expose pass@k, which helps, but ensemble headlines are compute-heavy. The multi-model statement pipeline reportedly costs several dollars per retained statement and is irrelevant to our fixed supplied skeletons.
- **Why it worked (authors + your read):** diversity helps coverage at large k, while the benchmark exposes domain and tactic biases hidden by miniF2F saturation. Crucially, adding natural-language solutions is not uniformly helpful: the paper reports higher proof perplexity and, for several models, lower success than a simpler CoT prompt.
- **Failure modes:** domain imbalance, contamination risk, pass@k compute inflation, and informal guidance that omits exact formal side conditions. The error analysis finds incomplete proofs and misuse of automation among dominant categories, but classifications are partly model-assisted/manual and not a router ablation.
- **Transfer recipe for us:**
  1. Do not force an informal plan on every problem.
  2. Route by formal diagnostic and observed stagnation.
  3. Make any plan short, Lean-shaped, and disposable.
  4. Record failure categories: parse/elaboration, unknown identifier, tactic/timeout, unsolved goals, semantic strategy.
  5. Evaluate across domains, not only easy algebra.
  6. Keep the original statement supplied by the task; no semantic-voting pipeline is needed.
- **Ablation we should run if we adopt it:** no-plan vs short-formal-plan vs free-form informal solution at equal tokens/calls, stratified by domain and initial failure type.
- **Confidence in this summary:** high

### Stop Overvaluing Multi-Agent Debate — Rethink Evaluation and Embrace Model Heterogeneity (2025)

- **Type:** multi-agent / informal reasoning
- **Venue / link:** [arXiv:2502.08788](https://arxiv.org/abs/2502.08788)
- **Core mechanism:** the study evaluates five multi-agent debate methods across nine benchmarks and four foundation models against basic Chain-of-Thought and self-consistency. It then constructs heterogeneous versions by mixing model families. Its central contribution is negative: elaborate debate is usually not the source of gains; diversity can matter, but simple baselines are hard to beat.
- **Coordination pattern:** generator–critic/debate; heterogeneous ensemble; self-consistency control
- **Verifier role:** none for the relevant math tasks; answer matching, not Lean
- **Models used:** both homogeneous and heterogeneous pools, including GPT-4o-mini and Llama-3.1-70B mixtures
- **Headline result:** no tested debate method wins more than about 20% of model/benchmark comparisons against CoT, and self-consistency is often more token-efficient. Heterogeneous Society-of-Mind averages 76.7 versus 72.5 for CoT and improves over the mean homogeneous counterpart, but on the mathematical/program-reasoning subset heterogeneity is mostly similar; GSM8K is the clearest gain.
- **Budget honesty:** much better than typical MAD work: common six-call configurations and token-aware comparisons are reported. It still does not match API dollars, model strength, or formal verifier queries, and it contains no Lean benchmark.
- **Why it worked (authors + your read):** debate only helps when it imports genuinely different errors or knowledge. When agents share a failure mode, conversation adds correlated tokens; self-consistency obtains diversity more directly.
- **Failure modes:** answer-level evidence may not transfer to proof text; a strong/weak mixture can lower average proposal quality; verbosity and anchoring grow with rounds.
- **Transfer recipe for us:**
  1. Do not implement multi-round debate.
  2. Preserve a simple same-model multi-role control.
  3. If testing heterogeneity, use one structured handoff and Lean acceptance.
  4. Measure disagreement and error-category transitions, not just final solve rate.
  5. Normalize tokens, dollars, and verifier checks.
  6. Claim heterogeneity only if it beats the best solo and same-model protocol.
- **Ablation we should run if we adopt it:** A→A, B→B, A→B, and B→A with the same prompt roles, calls, token ceilings, and Lean checks.
- **Confidence in this summary:** high for informal MAD; low–med for Lean transfer

### ReConcile — Round-Table Conference Improves Reasoning via Consensus among Diverse LLMs (2024; older root for heterogeneity)

- **Type:** multi-agent / informal math
- **Venue / link:** ACL 2024; [arXiv:2309.13007](https://arxiv.org/abs/2309.13007)
- **Core mechanism:** ReConcile has heterogeneous models share answers, explanations, and confidence, revise over rounds, then use confidence-weighted voting. It explicitly studies response diversity and attributes some gains to different model families. This is one of the stronger positive results for heterogeneity, but it relies on persuasion and answer voting rather than formal verification.
- **Coordination pattern:** generator–critic/debate; self-consistency/weighted vote; heterogeneous ensemble
- **Verifier role:** none
- **Models used:** heterogeneous combinations of API, open, and domain models; configurations include ChatGPT, Bard, Claude 2, and later math-model combinations
- **Headline result:** the paper reports up to 11.4-point gains across seven reasoning datasets and roughly 8 points on MATH; one reported MATH configuration reaches 58.3 versus 50.5 for its best single model and 48.7 for a debate baseline. These are answer-level, not formal proofs.
- **Budget honesty:** only 100 examples per dataset in some costly API evaluations and multiple discussion rounds; same-round comparisons help, but tokens/dollars and strongest-single resampling are not fully matched.
- **Why it worked (authors + your read):** different model families produce less correlated candidate rationales, so a mistaken agent sometimes sees a correct alternative. Lean lets us keep the diversity benefit while discarding confidence voting and persuasion.
- **Failure modes:** confidence is poorly calibrated; models can converge on a persuasive error; discussion is expensive; the 2023-era model roster limits current external validity.
- **Transfer recipe for us:**
  1. Take one independent candidate from each model.
  2. Let Lean, not confidence, select complete proofs.
  3. On two failures, expose only candidate + diagnostic, not a round-table transcript.
  4. Route one critic/repair handoff if error categories differ or progress stalls.
  5. Stop after the handoff; no consensus vote is needed.
  6. Treat MATH evidence as a prior, not formal validation.
- **Ablation we should run if we adopt it:** heterogeneous dual-propose vs two samples from the better single model, with equal spend and Lean checks; then add one handoff to both arms.
- **Confidence in this summary:** high on the paper; low–med on Lean transfer

## Section D — Mechanism cookbook

### Operating contract shared by every pattern

The theorem statement, imports, and allowed harness are immutable. A candidate is **solved only when `lean.check_file(source)` returns no rejecting diagnostic under the comparator’s rules**. A checkpoint for a failed proof is merely a repair starting point; it is never partial credit. Use a deterministic progress tuple such as `(parses, elaborates, no_unknown_identifiers, fewer_primary_errors, fewer_unsolved_goals, smaller_edit)` and retain the earlier candidate on a tie. Because diagnostic counts are not monotone, require actual improvement in a primary category rather than treating one fewer message as mathematical progress.

Cost estimates below use **1.0x = one initial whole-proof call plus up to two same-model compiler-repair calls**, with the same output-token ceilings. Dollar multipliers must be recomputed from the actual two model prices; call multipliers alone are insufficient.

### Pattern 1 — Single-model compiler repair loop

1. **Information flow diagram**

   ```text
   statement+skeleton ──> Model X: draft ──> Lean
                              ^                |
                              | failed source  | diagnostics
                              +----------------+
                                      |
                              checkpoint best; repeat <= 2
   ```

2. **State shared between agents:** no inter-agent state. Persist immutable source prefix/theorem statement, current best candidate, current Lean diagnostics, progress tuple, call/token/dollar counters, and hashes of prior `(candidate, diagnostic)` pairs.
3. **Stop conditions:** Lean accepts; two repairs used; identical candidate or primary diagnostic repeats; no progress in two consecutive checks; output would exceed context/dollar cap; forbidden token or changed statement detected.
4. **When it helps:** parse/elaboration errors, wrong lemma names exposed by Lean, local tactic failures, or one missing side condition. Baldur and MA-LoT make this the default evidence-backed baseline.
5. **When it hurts:** the mathematical strategy is wrong, the model rewrites correct code, or identical feedback causes a loop. Repeated repair can be less diverse than a fresh draw.
6. **Minimal implementation:**

   ```python
   src = llm.complete(X, draft_messages(problem, skeleton))
   for step in range(3):
       diag = lean.check_file(src)
       if diag.accepted: return src
       checkpoint(src, diag)
       if step == 2 or repeated_or_stalled(src, diag): break
       src = llm.complete(X, repair_messages(problem, src, diag))
   return failure(best_checkpoint)
   ```

   `repair_messages` includes the exact diagnostic, forbids statement/import edits and proof holes, and requests the smallest complete replacement proof. Local code performs statement/hash checks; the model never reports its own success.
7. **Required ablations:** one draft + two repairs vs three independent drafts; exact diagnostics vs “proof failed”; repair full source vs only the failing proof block.
8. **Estimated relative cost:** **1.0x** by definition; often 0.4–0.8x realized with early success.

### Pattern 2 — Cross-model repair handoff

1. **Information flow diagram**

   ```text
   problem ──> Model A: draft ──> Lean ──fail──> checkpoint
                                                     |
                                  source+diagnostic  v
                                             Model B: repair ──> Lean
   ```

2. **State shared between agents:** only the immutable problem/skeleton, best failed source, normalized diagnostics, optional one-line deterministic failure label, and budget. Do not share hidden rationales or the entire transcript.
3. **Stop conditions:** Lean accepts; one A repair plus one B handoff used; B returns the same source; primary failure does not improve; dollar cap reached.
4. **When it helps:** A and B have complementary formal/math errors, B notices an assumption or library misuse A repeatedly misses, or a fresh context breaks anchoring. ReConcile/Heter-MAD offer an informal diversity prior; formal proof evidence is currently indirect.
5. **When it hurts:** B is weaker at Lean, lacks A’s implicit plan, rewrites valid structure, or simply adds an expensive correlated sample. A cheap repairer should not be asked to reinvent a hard strategy.
6. **Minimal implementation:** run one ordinary repair with the proposer; on deterministic stagnation, call the other model with `problem + exact source + exact diagnostics + requested local action`. Check immediately and keep the prior checkpoint on regression. Reverse roles in a separate arm rather than dynamically inventing a third policy.
7. **Required ablations:** A→B vs A→A with identical role prompt; B→A vs B→B; best solo at the same dollar budget; handoff-on-stall vs unconditional handoff. Report error-transition matrices.
8. **Estimated relative cost:** **0.9–1.4x** in calls relative to baseline; dollars can be lower or much higher depending on which model is the repairer.

### Pattern 3 — Same-model dual-role control

1. **Information flow diagram**

   ```text
   problem ──> Model X [PROPOSER prompt] ──> Lean
                                                |
                                                v
              Model X [REPAIRER prompt] <── diagnostics+source
   ```

2. **State shared between agents:** identical to cross-model handoff. The only manipulated variable is model identity; role instructions and exposed state remain fixed.
3. **Stop conditions:** exactly the same as Pattern 2.
4. **When it helps:** role separation focuses attention even without heterogeneous weights. MA-LoT’s correction staging supports this mechanism, and it is the indispensable scientific control.
5. **When it hurts:** the same model reproduces the same misconception, role labels become persona theater, or prompt differences accidentally change token use.
6. **Minimal implementation:** replace `model=B` in Pattern 2 with `model=A` while holding all messages except the model ID constant. Run the corresponding B→B arm as well. Keep generation settings and output caps identical to the cross-model arms.
7. **Required ablations:** A solo fresh sampling, A→A, A→B; B solo fresh sampling, B→B, B→A; matched calls/tokens/dollars/Lean checks. Also compare specialized repair instructions with a generic retry.
8. **Estimated relative cost:** **0.9–1.1x**; it should be virtually identical in calls/tokens to the corresponding handoff.

### Pattern 4 — Conditional planner–formalizer split

1. **Information flow diagram**

   ```text
   direct proof(s) ──fail semantically──> Model P: compact plan
                                                |
                                      2–4 Lean-shaped lemmas
                                                v
                                      Model F: formalize/fill
                                                |
                                               Lean
   ```

2. **State shared between agents:** problem and fixed skeleton; a plan containing theorem-level strategy, exact candidate lemma statements, dependencies, and prohibited-assumption reminder; checked failures. No long scratchpad is needed.
3. **Stop conditions:** plan has >4 lemmas, changes the goal, adds unjustified assumptions, or cannot be parsed into obligations; each lemma gets at most one initial fill plus one repair; one final assembly; global cap.
4. **When it helps:** repeated unsolved goals or mathematically wrong direct strategies on longer problems; evidence comes from DSP, DeepSeek-Prover-V2, Delta, Seed-Prover, and Aristotle.
5. **When it hurts:** easy algebra/normalization goals, verbose natural-language plans, missing formal side conditions, and plan tokens that displace proof tokens. FormalMATH directly warns that supplied informal solutions can reduce proof success.
6. **Minimal implementation:** after two non-improving semantic failures, call `llm.complete(P, plan_messages(...))`. Require a machine-readable list of 2–4 lemma statements plus a one-line assembly. Call `llm.complete(F, fill_messages(...))`, splice complete proofs into a local source, run `lean.check_file`, checkpoint only accepted lemmas, and perform one final assembly call if needed.
7. **Required ablations:** no plan vs compact plan vs free-form solution; P=A/F=B vs P=A/F=A; reverse roles; always-plan vs semantic-failure gate; equal total token/call cap.
8. **Estimated relative cost:** **1.3–2.0x** when triggered; **0.2–0.5x incremental average** if only 15–25% of problems escalate.

### Pattern 5 — Dual-propose + Lean selection

1. **Information flow diagram**

   ```text
                   ┌─> Model A: proof ─> Lean ─┐
   problem+skeleton┤                           ├─> accept any valid;
                   └─> Model B: proof ─> Lean ─┘   else choose repair seed
   ```

2. **State shared between agents:** none during proposal. After checks, store both sources, diagnostics, acceptance flags, costs, and deterministic progress tuples. Independence is the point.
3. **Stop conditions:** first accepted proof if calls are sequential and early-stop is permitted; otherwise after both checks; if neither passes, retain only the better deterministic repair seed plus a pointer to the alternative strategy.
4. **When it helps:** models or temperatures generate genuinely different strategies; Lean can perfectly select complete successes; one candidate may elaborate far enough to repair. Best-of-N and heterogeneous informal ensembles support the diversity premise.
5. **When it hurts:** parallel execution spends the second call even when the first succeeds; models produce correlated drafts; invalid candidates cannot be reliably ranked by diagnostic count; sampling the weaker model may be worse than a second strong-model draw.
6. **Minimal implementation:** request one independent complete proof from each model without showing either the other’s response; check both. If either is accepted, return the shorter accepted proof or the first accepted proof under a predeclared rule. If both fail, choose a repair seed by the fixed progress tuple; never ask an LLM to vote on correctness.
7. **Required ablations:** A+B vs A+A vs B+B; sequential cheap-first vs parallel; equal calls and equal dollars (two separate analyses if prices differ); diversity measures by strategy/error category; repair-best vs repair-first.
8. **Estimated relative cost:** **0.7–1.3x** relative to the three-call baseline; about **2x a single-draft pass@1**. Sequential early stop lowers realized cost.

### Pattern 6 — Minimal verified lemma workspace

1. **Information flow diagram**

   ```text
   failed goal ─> planner: [L1, L2, L3]
                         |    |    |
                       Lean Lean Lean
                         \    |    /
                    VERIFIED-ONLY BLACKBOARD
                              |
                         final assembler ─> Lean
   ```

2. **State shared between agents:** at most four records: `{name, exact Lean statement, accepted proof, dependencies}` plus outstanding obligations and final target. Failed proof text stays in diagnostic history, not in the blackboard. Every accepted record is immutable.
3. **Stop conditions:** four-lemma cap; dependency cycle; lemma statement fails to elaborate; two attempts per lemma; no newly accepted lemma in two calls; final assembly fails after one repair; budget cap.
4. **When it helps:** monolithic strategy is sound but too long, multiple attempts rediscover the same intermediate fact, or a verified helper cleanly reduces the remaining goal. Delta, Seed-Prover, and Aristotle strongly use this object at much larger scale.
5. **When it hurts:** short goals; speculative or false lemmas; context inflation; proofs that depend on local variables incorrectly; blackboard drift if unverified claims are admitted.
6. **Minimal implementation:** obtain the bounded lemma list, create a source containing the original theorem context plus one lemma at a time, call `lean.check_file`, and checkpoint a record only on acceptance. For the final call, supply only the original target and accepted records. A valid main proof must compile after all temporary placeholders are removed.
7. **Required ablations:** verified-only workspace vs no workspace; workspace vs unverified prose notes; two vs four lemmas; retain accepted lemmas vs restart; stratify by initial proof length/domain.
8. **Estimated relative cost:** **1.5–3.0x when triggered**; unsuitable as the universal default under $1.

### Pattern 7 — Error-type-conditioned repair policy

1. **Information flow diagram**

   ```text
                     ┌ parse/elab/identifier ─> cheap local repair
   Lean diagnostics ─┼ tactic/timeout         ─> tactic-focused patch
                     ├ unsolved local goals    ─> proof-gap repair
                     └ semantic stagnation     ─> strong critic/plan/lemmas
   ```

2. **State shared between agents:** raw diagnostics, deterministic category, source span/line if available, attempt count per category, last action, progress tuple, and budget. The category is an orchestration hint, never a correctness judgment.
3. **Stop conditions:** category-specific cap; same primary diagnostic after two attempts; regression to an earlier category twice; success; budget. Suggested caps: syntax/library one cheap repair; local tactic one proposer repair; semantic one cross-model reframe; decomposition only once.
4. **When it helps:** cheap errors can be fixed without spending the strong model, while repeated semantic gaps justify a different operation. APOLLO supplies architectural evidence and FormalMATH supplies a failure taxonomy; a direct router ablation is still missing.
5. **When it hurts:** Lean diagnostics are noisy/cascading, the classifier mistakes a downstream parse error for the root cause, or branching logic becomes unexplainable. Do not train a router this week.
6. **Minimal implementation:** ordered string/structure rules over Lean diagnostics classify `parse`, `elaboration_or_identifier`, `tactic_failure_or_timeout`, `unsolved_goals`, or `semantic_or_unknown`. Each maps to a fixed prompt/model/action table. On low confidence, use the ordinary proposer repair rather than inventing a new branch. All branches call only `llm.complete`, `lean.check_file`, and `checkpoint`.
7. **Required ablations:** router vs one generic repair prompt; deterministic category vs no label but same raw diagnostic; routed model identity vs routed prompt only; confusion audit on a hand-labeled sample; equal maximum and realized-cost curves.
8. **Estimated relative cost:** **0.8–1.1x average**; the intended gain is fewer wasted expensive calls, not more branches.

### Pattern 8 — Adaptive compute and early stop

1. **Information flow diagram**

   ```text
   cheap draft ─> Lean ─accepted──────────────> STOP
                    |
                 improved? ─yes─> bounded repair ─> Lean
                    |
                   no / repeated
                    v
             one escalation if budget allows ─> Lean ─> STOP
   ```

2. **State shared between agents:** cumulative calls, input/output tokens, estimated dollars, Lean checks, wall time, error history, best checkpoint, and next-action cost estimate.
3. **Stop conditions:** acceptance; statement mutation/forbidden construct; repeated candidate/diagnostic; no progress twice; per-problem soft cap; hard $1 cap; optional global evaluation cap. Predeclare all thresholds.
4. **When it helps:** easy problems terminate cheaply and hard-but-progressing problems receive one extra operation. APOLLO’s average sample savings and the light/medium/heavy logic in Delta/Seed-Prover support adaptive allocation.
5. **When it hurts:** a bad progress heuristic pours compute into hopeless problems or prematurely cuts off a promising new strategy. Dollar estimates may be wrong if reasoning tokens/pricing are opaque.
6. **Minimal implementation:** before each call, choose only among a fixed action list and refuse any action whose worst-case output would cross the hard cap. Use deterministic rules, not an LLM router. Log a cumulative success curve at each call/dollar threshold. A checkpoint may guide the next action but never override Lean.
7. **Required ablations:** adaptive vs fixed call count at equal global spend; soft cap values; progress-gated vs failure-count-gated; sequential cheap-first vs strong-first; report tail spend (p50/p90/max), not just mean.
8. **Estimated relative cost:** **0.5–1.5x realized**, hard-capped at a predeclared maximum; likely the main mechanism that makes the integrated stack fit $1.

### Optional Pattern 9 — Critic-only reframe

1. **Information flow diagram**

   ```text
   failed source+Lean error ─> other model: diagnosis + patch instruction only
                                        |
                                        v
                              original model: one repair ─> Lean
   ```

2. **State shared between agents:** exact source/diagnostic and a bounded critic record: root-cause category, one suspected bad step, one alternative tactic/lemma. No full proof from the critic.
3. **Stop conditions:** critic cannot identify a concrete Lean-relevant change; one repair fails; critic repeats the existing diagnosis; budget.
4. **When it helps:** the expensive/strong model is better used for mathematical reframing than for regenerating boilerplate, or the cheap model is a competent Lean coder once given a plan.
5. **When it hurts:** the diagnosis is not checkable, an extra translation step loses detail, or two calls cost more than one strong full repair.
6. **Minimal implementation:** one bounded-output critic call followed by one proposer repair call, then Lean check. Constrain the critic to structured fields and no proof text.
7. **Required ablations:** critic-only + repair vs critic directly repairing; cross-model critic vs same-model self-critique; equal dollars; diagnosis agreement with observed Lean error transitions.
8. **Estimated relative cost:** **1.2–1.6x**; use only on a predeclared subset or after stagnation.

### Cookbook verdict

Build Patterns **1, 3, 5, 7, and 8** first. Add Pattern **2** as the scientific treatment and Pattern **4/6** as a single bounded upgrade for hard semantic failures. Do not build a debate layer, MCTS, a retrieval service, or a general blackboard in week one.

## Section E — Heterogeneity: when two models beat one

### What the evidence actually says

There is credible **answer-level** evidence that dissimilar models can cover different errors. ReConcile reports a substantial MATH gain for a heterogeneous round table, and the 2025 debate audit finds that heterogeneous variants improve average performance even while homogeneous debate usually fails to beat simple CoT/self-consistency. Response diversity correlating with gains makes the complementarity story plausible.

There is **not** corresponding matched-budget Lean evidence. MA-LoT’s runtime roles are mainly the same specialized model; APOLLO’s “agents” are pipeline stages; DeepSeek-Prover-V2’s heterogeneous teacher/student interaction happens during data generation; FormalMATH uses multiple models to validate statements; Delta, Seed-Prover, and the primary DeepSeek systems use one prover family at inference. None answers the decisive question: does A→B repair beat A→A and the best solo model under the same dollars, tokens, Lean checks, and source statements?

The best current position is therefore:

- **Protocol structure is established; heterogeneous advantage is unproven for formal proof.** Same-model generation/repair already gains from exact Lean feedback and role-focused prompts.
- **Complementary skills are problem- and direction-specific.** A large reasoner may find a mathematical invariant but hallucinate Lean details; a fast model may know common tactics but be unable to repair a wrong strategy. The reverse can also occur if the large model is the better formal coder.
- **Asymmetric roles should be diagnosed, not assumed.** Evaluate all four directed pairs A→A, A→B, B→A, B→B. An average “collaboration” score hides whether only one direction works.
- **The kernel replaces consensus.** Different models may propose or critique; only Lean accepts. Confidence-weighted voting and majority proof text are unnecessary.
- **Diversity must beat the opportunity cost.** A+B is useful only if it outperforms A+A or a second sample from the stronger model at the same spend.

### Practical recommendation for a fast model + a large open reasoner

Start sequentially with the model that maximizes **accepted proofs per dollar**, not automatically the large model. Give that model one whole-proof attempt and one cheap diagnostic repair. Spend the large model only when (a) the first model’s failure is semantic/unsolved-goal rather than syntax, or (b) the same primary error persists. Ask the large model for a bounded diagnosis/patch or a 2–4-lemma plan; if the fast model is demonstrably better at Lean syntax, let it perform the final formalization. On the experimental branch, reverse the roles to learn the pair’s actual asymmetry.

Do not label this “multi-agent debate.” A more accurate design description is **typed, verifier-gated model handoff**.

### H1–H7 audit

| Hypothesis | Verdict | Evidence and qualification |
|---|---|---|
| **H1 — Compiler feedback is the highest-value coordination signal.** | **Supported** | Baldur establishes the root repair pattern; [MA-LoT](https://arxiv.org/abs/2503.03205), [APOLLO](https://arxiv.org/abs/2505.05758), and [Delta](https://arxiv.org/abs/2507.15225) all turn formal feedback into targeted progress. Free-form MAD often loses to simpler baselines in [Zhang et al.](https://arxiv.org/abs/2502.08788). Evidence is formal for feedback, informal-negative for debate. |
| **H2 — Cross-model handoff helps only if models err differently.** | **Mixed** | ReConcile and heterogeneous MAD support diversity at answer level; same-model MA-LoT shows heterogeneity is not necessary for repair gains. No matched Lean A→B vs A→A result was found. “Only if” is plausible but must be measured through paired failure transitions. |
| **H3 — Informal plan → formalize beats direct generation on harder problems.** | **Mixed** | DSP, DeepSeek-Prover-V2, Delta, and Aristotle support decomposition; [FormalMATH](https://arxiv.org/abs/2505.02735) finds natural-language guidance can reduce success. The refined claim is “a short formalizable plan can help after semantic stagnation,” not “always plan first.” |
| **H4 — Lemma blackboards help mainly after monolithic failure.** | **Mixed** | Delta’s hard-case analysis and the architectures of Seed-Prover/Aristotle support the escalation, but broad low-budget matched ablations are absent. Easy-goal harm is a strong efficiency inference rather than a demonstrated universal result. |
| **H5 — Lean selection is more reliable than LLM judging.** | **Supported** | For complete proofs, the Lean kernel is definitive; best-of-N formal systems rely on it. Informal consensus remains fallible and debate baselines are mixed. For *failed-candidate ranking*, however, Lean diagnostics are only heuristics; the support does not extend to partial-proof scoring. |
| **H6 — Error-type routing beats one generic repair prompt.** | **Mixed** | APOLLO’s staged system and FormalMATH’s failure taxonomy support the mechanism; MA-LoT shows specialized correction outperforms a generic prover-as-corrector. No simple direct deterministic-router ablation under matched API cost was found. This is exactly the cheap unknown we should test. |
| **H7 — Most published multi-agent gains are unmatched-compute artifacts.** | **Supported, with nuance** | The broad MAD audit shows simple CoT/self-consistency baselines erase many gains; formal SOTA reports often use enormous pass@k. Yet MA-LoT and Delta retain some gains in matched-ish/fixed-budget studies, so *structured repair* is not merely more compute. |

## Section F — Confounders checklist for Part Two

### Experimental unit and correctness

- [ ] Freeze the problem set before running; include every attempted item in the denominator.
- [ ] Hash the immutable theorem statement/import prefix before and after every candidate.
- [ ] Reject `sorry`, `admit`, unsafe escapes, altered declarations, and comparator-specific forbidden constructs.
- [ ] Pin Lean, Mathlib, project commit, command, timeout, and hardware/sandbox limits.
- [ ] Use exactly the same comparator as final evaluation; “compiles in a scratch file” is not sufficient if the comparator differs.
- [ ] Primary outcome: binary accepted proof per problem. Secondary outcomes never override it.

### Fair model/protocol comparisons

- [ ] Report A solo, B solo, A→A, B→B, A→B, and B→A, plus the chosen integrated policy.
- [ ] Hold role prompts constant when changing model identity; version all prompts in the appendix/repository.
- [ ] Fix temperature, top-p, maximum output tokens, retry policy, and concurrency per arm, or report differences explicitly.
- [ ] Run the same problems in every arm; use paired confidence intervals and paired tests (for example, paired bootstrap and McNemar on solve/fail).
- [ ] Randomize arm order or interleave calls to reduce time-of-day/API-version effects; record model IDs and provider timestamps.
- [ ] Count provider errors/timeouts as predeclared retries or failures identically across arms.

### Budget and compute

- [ ] Record input tokens, output/reasoning tokens when exposed, model calls, Lean checks, wall time, and estimated dollars **per problem and arm**.
- [ ] Compare under both an equal maximum budget and realized cost; report p50, p90, maximum, and success-vs-cumulative-dollar curves.
- [ ] Separate sequential early-stop from parallel dual-propose; parallelism changes wall time but not spend.
- [ ] Do not compare pass@k to pass@1 without showing the full cumulative curve.
- [ ] If model prices differ, provide equal-call and equal-dollar analyses; neither substitutes for the other.
- [ ] Include local Lean timeouts and verifier-query counts; a protocol can shift cost from API to search.

### Causal attribution

- [ ] Factor the treatment into: extra sample, role prompt, diagnostic feedback, model identity, router, and decomposition/workspace.
- [ ] Compare repair against a fresh resample at the same next-call budget.
- [ ] Compare same-model role separation against cross-model handoff before claiming heterogeneity.
- [ ] Compare raw diagnostics against a typed label + raw diagnostics before claiming router value.
- [ ] Compare conditional decomposition against always-on decomposition and no decomposition.
- [ ] Report overlap: solved by A only, B only, both, and collaboration only. A few “collab-only” wins can be offset by regressions.
- [ ] Audit whether the collaborator repairs the checkpoint or silently replaces it with a new strategy; both can work but imply different mechanisms.

### Diagnostics and failure analysis

- [ ] Predeclare a small error taxonomy: parse, elaboration/type/identifier, tactic failure/timeout, unsolved goals, semantic/strategy, harness/provider.
- [ ] Hand-label a sample to estimate deterministic router errors; Lean messages can cascade.
- [ ] Log error-category transitions and checkpoint improvements by directed pair.
- [ ] Inspect regressions where collaboration loses a solo success under the same cap.
- [ ] Stratify by domain, statement length, initial diagnostic, and direct-proof length; do not mine many tiny slices for significance.
- [ ] Preserve raw artifacts for reproducibility while keeping model scratch reasoning out of the coordination state.

### Reporting hygiene

- [ ] Distinguish “reported,” “reproduced,” and “our result.”
- [ ] Give exact benchmark version/split and note miniF2F/ProofNet/PutnamBench Lean-version drift.
- [ ] State whether intervals are over problems, stochastic runs, or both.
- [ ] Publish failures and kill criteria, not only the winning configuration.
- [ ] Avoid the term “multi-agent improvement” when the treatment is simply more samples or more dollars.

## Section G — Ranked recommendations for our project

### Rank 1

| Field | Content |
|---|---|
| **Rank** | **1** |
| **Name** | Typed verifier-gated handoff |
| **One-sentence thesis** | Use a deterministic Lean-error router to decide between cheap local repair, one cross-model reframe, and one bounded decomposition—then stop. |
| **Novelty vs bare cross-repair** | **Med**: the new coordination object is an auditable failure-type/action table. |
| **Implementation effort** | **M** (2–3 engineer-days including logging/tests) |
| **Eval cost** | **M** |
| **Scientific story quality** | Excellent for a five-page writeup: a clear hypothesis, a small mechanism, and clean router/no-router plus same/cross-model ablations. |
| **Risk** | Diagnostics are noisy; branches may be too sparse to estimate; an overbuilt router becomes brittle. |
| **First experiment to run** | On 20–40 calibration problems, compare generic same-model repair with deterministic error-routed prompts at the same two post-draft calls. |
| **Kill criterion** | Kill model routing if it fails to improve solve rate or accepted-proofs/$ and shows no beneficial error transitions; keep only early stopping and raw diagnostics. |

### Rank 2

| Field | Content |
|---|---|
| **Rank** | **2** |
| **Name** | Dual-propose → Lean-select → repair-best |
| **One-sentence thesis** | Buy diversity once, let Lean accept either proof, then spend at most one repair on the deterministically better failed candidate. |
| **Novelty vs bare cross-repair** | **Low–Med** |
| **Implementation effort** | **S** (about 1 day) |
| **Eval cost** | **M** because A+B, A+A, and B+B are all required. |
| **Scientific story quality** | Very clear separation of diversity from dialogue, with Lean—not an LLM—as selector. |
| **Risk** | The second model may be worse than a second strong-model sample; failed-candidate ranking can be unstable. |
| **First experiment to run** | Compare A+B, A+A, and B+B at two total drafts, then one fixed repair, under equal dollars and equal calls. |
| **Kill criterion** | Abandon heterogeneous dual-propose if its confidence interval excludes a practically useful gain over the best homogeneous pair or its cost-normalized curve is worse. |

### Rank 3

| Field | Content |
|---|---|
| **Rank** | **3** |
| **Name** | Conditional compact planner–formalizer |
| **One-sentence thesis** | After two semantic failures, let the stronger planner emit at most four Lean-shaped lemmas and let the better formal coder fill them. |
| **Novelty vs bare cross-repair** | **Med–High** |
| **Implementation effort** | **M** (2–3 days) |
| **Eval cost** | **M** if gated; **L** if run universally. |
| **Scientific story quality** | Strong mechanism story connecting DSP/DeepSeek-V2/Delta to a constrained API setting, while testing FormalMATH’s contrary warning. |
| **Risk** | Plans consume budget, omit side conditions, or help too few problems; role asymmetry may be opposite the assumed one. |
| **First experiment to run** | Apply only to a frozen set of semantic-stagnation failures; compare no plan, compact formal plan, and same-token free-form solution. |
| **Kill criterion** | Drop if fewer than 10% of triggered failures gain a verified intermediate lemma or if incremental accepted-proofs/$ loses to another direct repair. |

### Rank 4

| Field | Content |
|---|---|
| **Rank** | **4** |
| **Name** | Four-slot verified lemma workspace |
| **One-sentence thesis** | Share only kernel-accepted problem-local lemmas, never free-form beliefs, across a single decomposition/assembly cycle. |
| **Novelty vs bare cross-repair** | **High** |
| **Implementation effort** | **M–L** (3–4 days to make source assembly safe) |
| **Eval cost** | **L** |
| **Scientific story quality** | Excellent if it rescues long proofs; the verified-only blackboard is concrete and interpretable. |
| **Risk** | Source-context bugs, false/unhelpful lemma plans, and costs above $1; too ambitious for the first stable system. |
| **First experiment to run** | On failures that already have a plausible 2–4 lemma plan, compare retained accepted lemmas with full restart at the same call cap. |
| **Kill criterion** | Stop if the median triggered problem accepts no helper lemma, assembly introduces frequent regressions, or p90 spend violates the cap. |

### Rank 5

| Field | Content |
|---|---|
| **Rank** | **5** |
| **Name** | Cross-model critic-only reframe |
| **One-sentence thesis** | Ask the complementary model for one bounded diagnosis and alternative step, then let the original formalizer patch once. |
| **Novelty vs bare cross-repair** | **Med** |
| **Implementation effort** | **S** |
| **Eval cost** | **M** because direct-repair and same-model-critic controls are necessary. |
| **Scientific story quality** | Clean test of whether complementarity lies in planning rather than Lean code generation. |
| **Risk** | Two-stage translation loses information and costs more than one direct strong-model patch. |
| **First experiment to run** | On repeated semantic failures, compare B-critic→A-repair, A-self-critic→A-repair, and B-direct-repair at equal dollars. |
| **Kill criterion** | Kill if critic recommendations rarely predict a favorable diagnostic transition or direct repair dominates solve rate and cost. |

### Recommended default stack

Implement Rank 1 using Rank 2 as its front end:

```text
cheap/high-value proposal ─> Lean ─accepted─> stop
          |
          +─failed─> second independent proposal (other model in treatment,
                     same model in control) ─> Lean ─accepted─> stop
                                      |
                               classify both failures
                                      |
                 local formal error ─> one targeted repair
                 semantic stagnation ─> one cross-model reframe/patch
                 repeated hard gap   ─> optional <=4-lemma plan (upgrade arm)
                                      |
                                     Lean ─> stop
```

This is simple enough to explain in one figure, supports all mandatory baselines, and gives the “idea-thin” Candidate A a real coordination object: **a typed, verifier-derived handoff rule**.

### Suggested seven-day research + build sequence

| Day | Deliverable | Decision gate |
|---|---|---|
| **1 — Measurement before mechanisms** | Freeze problems, comparator, statement-integrity checks, model configs, prices, token/Lean/cost logging, and the error taxonomy. Run small pass@1 probes for A and B. | If the harness cannot reproduce strict acceptance and costs, do not build coordination yet. |
| **2 — Strong solo baselines** | Implement one draft + two compiler repairs for A and B; add fresh-resample control and cumulative curves. | Choose the default proposer by accepted-proofs/$, not reputation. |
| **3 — Identity-controlled handoffs** | Add A→A, B→B, A→B, B→A with identical role prompts and limits. | If cross-model directions show no complementary transitions, keep heterogeneity experimental. |
| **4 — Dual-propose and router** | Add A+B/A+A/B+B dual proposals, deterministic progress checkpoint, and the five-category error router. | Pick one front end and freeze it; avoid tuning on final evaluation problems. |
| **5 — Full ablation run** | Interleaved runs with fixed seeds/settings; paired solve overlap, error transitions, tokens, dollars, Lean checks, p50/p90/max. | Kill any branch that loses cost-normalized success or lacks enough triggered cases. |
| **6 — One idea upgrade** | Implement only the compact planner/≤4-lemma workspace for predeclared semantic-stagnation cases. | Retain only if it creates verified intermediates and stays under the cap. |
| **7 — Replication and writeup** | Rerun the frozen winner and mandatory controls; inspect every collab-only win/regression; produce architecture, results, limitations, and exact prompts/configs. | Prefer the simpler protocol when intervals overlap materially. |

## Section H — Bibliography

### READ — decision-critical

1. Wang et al. **MA-LoT: Model-Collaboration Lean-based Long Chain-of-Thought Reasoning enhances Formal Theorem Proving.** arXiv:2503.03205 (2025). [arXiv](https://arxiv.org/abs/2503.03205)
2. Ospanov and Yousefzadeh. **APOLLO: Automated LLM and Lean Collaboration for Advanced Formal Reasoning.** arXiv:2505.05758 (2025). [arXiv](https://arxiv.org/abs/2505.05758)
3. Zhou et al. **Solving Formal Math Problems by Decomposition and Iterative Reflection.** arXiv:2507.15225 (2025). [arXiv](https://arxiv.org/abs/2507.15225)
4. Chen et al. **Seed-Prover: Deep and Broad Reasoning for Automated Theorem Proving.** arXiv:2507.23726 (2025). [arXiv](https://arxiv.org/abs/2507.23726)
5. Xin et al. **DeepSeek-Prover-V1.5: Harnessing Proof Assistant Feedback for Reinforcement Learning and Monte-Carlo Tree Search.** arXiv:2408.08152 (2024). [arXiv](https://arxiv.org/abs/2408.08152)
6. Ren et al. **DeepSeek-Prover-V2: Advancing Formal Mathematical Reasoning via Reinforcement Learning for Subgoal Decomposition.** arXiv:2504.21801 (2025). [arXiv](https://arxiv.org/abs/2504.21801)
7. Yu et al. **FormalMATH: Benchmarking Formal Mathematical Reasoning of Large Language Models.** arXiv:2505.02735 (2025). [arXiv](https://arxiv.org/abs/2505.02735)
8. Zhang et al. **Stop Overvaluing Multi-Agent Debate — We Must Rethink Evaluation and Embrace Model Heterogeneity.** arXiv:2502.08788 (2025). [arXiv](https://arxiv.org/abs/2502.08788)
9. Chen, Saha, and Bansal. **ReConcile: Round-Table Conference Improves Reasoning via Consensus among Diverse LLMs.** ACL 2024; arXiv:2309.13007. [arXiv](https://arxiv.org/abs/2309.13007)
10. First et al. **Baldur: Whole-Proof Generation and Repair with Large Language Models.** ESEC/FSE 2023; arXiv:2303.04910. [arXiv](https://arxiv.org/abs/2303.04910)
11. Jiang et al. **Draft, Sketch, and Prove: Guiding Formal Theorem Provers with Informal Proofs.** NeurIPS 2022; arXiv:2210.12283. [arXiv](https://arxiv.org/abs/2210.12283)
12. Yang et al. **LeanDojo: Theorem Proving with Retrieval-Augmented Language Models.** NeurIPS 2023; arXiv:2306.15626. [arXiv](https://arxiv.org/abs/2306.15626)
13. Google DeepMind et al. **Olympiad-Level Formal Mathematical Reasoning with Reinforcement Learning.** Nature (online 2025); DOI article s41586-025-09833-y. [Nature](https://www.nature.com/articles/s41586-025-09833-y) · [Google Research](https://research.google/pubs/olympiad-level-formal-mathematical-reasoning-with-reinforcement-learning/)
14. Xin et al. **DeepSeek-Prover: Advancing Theorem Proving in LLMs through Large-Scale Synthetic Data.** arXiv:2405.14333 (2024). [arXiv](https://arxiv.org/abs/2405.14333)

### SKIM — context, roots, benchmarks, or lower transfer

15. Lin et al. **Goedel-Prover: A Frontier Model for Open-Source Automated Theorem Proving.** arXiv:2502.07640 (2025). [arXiv](https://arxiv.org/abs/2502.07640)
16. Wang et al. **Kimina-Prover Preview: Towards Large Formal Reasoning Models with Reinforcement Learning.** arXiv:2504.11354 (2025). [arXiv](https://arxiv.org/abs/2504.11354)
17. Wu et al. **InternLM2.5-StepProver: Advancing Automated Theorem Proving via Critic-Guided Search.** arXiv:2410.15700 (2024). [arXiv](https://arxiv.org/abs/2410.15700)
18. Thakur et al. **An In-Context Learning Agent for Formal Theorem-Proving (COPRA).** arXiv:2310.04353 (2023). [arXiv](https://arxiv.org/abs/2310.04353)
19. Wang et al. **LEGO-Prover: Neural Theorem Proving with Growing Libraries.** arXiv:2310.00656 (2023). [arXiv](https://arxiv.org/abs/2310.00656)
20. Wang et al. **Proving Theorems Recursively.** arXiv:2405.14414 (2024). [arXiv](https://arxiv.org/abs/2405.14414)
21. Zheng et al. **Lyra: Orchestrating Dual Correction in Automated Theorem Proving.** arXiv:2309.15806 (2023). [arXiv](https://arxiv.org/abs/2309.15806)
22. Lin et al. **Lean-STaR: Learning to Interleave Thinking and Proving.** arXiv:2407.10040 (2024). [arXiv](https://arxiv.org/abs/2407.10040)
23. Liang et al. **Should We Be Going MAD? A Look at Multi-Agent Debate Strategies for LLMs.** arXiv:2311.17371 (2023; ICML 2024). [arXiv](https://arxiv.org/abs/2311.17371)
24. Zheng, Han, and Polu. **miniF2F: a Cross-System Benchmark for Formal Olympiad-Level Mathematics.** arXiv:2109.00110 (2021). [arXiv](https://arxiv.org/abs/2109.00110)
25. Azerbayev et al. **ProofNet: Autoformalizing and Formally Proving Undergraduate-Level Mathematics.** arXiv:2302.12433 (2023). [arXiv](https://arxiv.org/abs/2302.12433)
26. Tsoukalas et al. **PutnamBench: Evaluating Neural Theorem-Provers on the Putnam Mathematical Competition.** arXiv:2407.11214 (2024). [arXiv](https://arxiv.org/abs/2407.11214)
27. Glazer et al. **FrontierMath: A Benchmark for Evaluating Advanced Mathematical Reasoning in AI.** arXiv:2411.04872 (2024). [arXiv](https://arxiv.org/abs/2411.04872)
28. Yang et al. **Formal Mathematical Reasoning: A New Frontier in AI.** arXiv:2412.16075 (2024; ICML 2025 position paper). [arXiv](https://arxiv.org/abs/2412.16075)
29. Weng et al. **Autoformalization in the Era of Large Language Models: A Survey.** arXiv:2505.23486 (2025). [arXiv](https://arxiv.org/abs/2505.23486)
30. Wang et al. **A Survey on Large Language Models for Mathematical Reasoning.** arXiv:2506.08446 (2025). [arXiv](https://arxiv.org/abs/2506.08446)
31. Achim et al. **Aristotle: IMO-level Automated Theorem Proving.** arXiv:2510.01346 (2025). [arXiv](https://arxiv.org/abs/2510.01346)

## Section I — Open questions / unknowns

1. **The central unknown is still RQ5.** No public study found here runs two fixed chat models on Lean and reports A solo, B solo, A→A, B→B, A→B, and B→A under matched dollars and verifier queries. Our experiment can be genuinely informative even if the answer is “same-model protocol explains all gains.”
2. **Which direction is complementary?** Model size is not a role label. We must measure whether the large model is better at initial strategy, diagnosis, Lean repair, or all three.
3. **Can failed formal candidates be ranked robustly?** Lean perfectly accepts complete proofs, but fewer diagnostics or later failure lines do not necessarily imply a better mathematical proof. The checkpoint heuristic needs a regression audit.
4. **Does a deterministic error router improve success or merely reduce cost?** Either is valuable, but they are different claims. Sparse categories may require reporting descriptive transitions rather than significance.
5. **When does a plan help?** FormalMATH contradicts the universal-planning prior. Difficulty, domain, and initial error type may define the useful subset; the trigger should be frozen before final evaluation.
6. **How small can a useful blackboard be?** Recent systems use tens to thousands of subproblems. It is unknown whether 2–4 verified lemmas preserve enough benefit under $1.
7. **How stable are results across Lean/Mathlib versions?** Unknown identifiers and automation behavior are version-specific. Benchmark numbers using Lean 3, older Lean 4 ports, or different theorem counts are not directly comparable.
8. **What is the real price of hidden reasoning tokens?** Some APIs expose incomplete usage accounting. We need provider invoices/usage fields and conservative worst-case gates.
9. **Are gains robust beyond miniF2F algebra?** miniF2F is small and increasingly saturated at huge pass@k. A small domain-diverse set or FormalMATH subset would better test routing, within development budget.
10. **Does sequential execution bias diversity?** Showing no prior candidate preserves independence, but API nondeterminism and changing provider backends can move results. Interleaved runs and exact timestamps/model revisions are needed.
11. **What is the minimum practically meaningful effect?** Define it before seeing results—for example, a solve-rate gain plus no worse accepted-proofs/$, or a cost reduction at non-inferior solve rate.
12. **Public reproducibility remains uneven.** AlphaProof, Aristotle, and Seed-Prover establish capability and architectural motifs; their component effects and budgets cannot be reproduced with this harness. They should motivate, not validate, our design.

---

## Appendix A — Glossary

| Term | Meaning here |
|---|---|
| **Whole proof** | One model response attempts the complete Lean proof body/file before checking. |
| **Tactic-level prover** | Repeatedly predicts the next tactic from a Lean state, usually within search. |
| **DSP** | Draft an informal proof, sketch a formal decomposition with holes, then prove the holes. |
| **Compiler repair** | Feed a failed formal artifact plus proof-assistant diagnostics into a targeted correction call. |
| **Comparator** | The exact strict evaluator that checks statement integrity, forbidden constructs, and Lean acceptance. |
| **Pass@k** | Probability/fraction solved with up to k sampled candidates; it is not comparable to pass@1 without the compute multiplier. |
| **Blackboard** | Shared persistent state. In this memo it means verified lemma records, not an unconstrained transcript. |
| **Heterogeneous** | Different model IDs/weights, not merely two prompts or roles applied to one model. |
| **Matched-ish** | A comparison controls a major resource such as samples/tokens but not every resource, price, and wall-time factor. |

## Appendix B — Benchmark cheat-sheet

| Benchmark | What it measures | Formal system / scale | Main caution for this project |
|---|---|---|---|
| **miniF2F** | Olympiad-style elementary theorem proving | 488 statements across systems; commonly 244 test | Small, algebra-heavy, saturated only at very high pass@k; Lean port/version matters. |
| **ProofNet** | Undergraduate textbook statement formalization/proving | 371 source examples; many Lean evaluations use a 186-item test partition | Lean 3 origin and conversion/version differences; combines formalization and proving concerns. |
| **PutnamBench** | Hard Putnam competition proofs | 1,692 formalizations representing 640 theorems across Lean/Isabelle and a Coq subset | Modern papers quote 657/658 Lean tasks depending on version; success counts are not comparable without release details. |
| **LeanDojo benchmark** | Repository theorem proving with premises | 98,734 Lean theorems/proofs | Retrieval and source-context access are central; not our no-RAG runtime. |
| **FormalMATH** | Broad Lean 4 math from high school to undergraduate | 5,560 problems plus Lite analyses | Hard and domain-diverse; construction/eval protocol is newer and sample-heavy. |
| **FrontierMath** | Very hard research/contest-style answer reasoning | Private answer-level benchmark | Not formal proof synthesis; strategy evidence only. |

## Appendix C — Steal these prompt structures

These are structures, not long copied prompts.

**Draft:** immutable theorem statement → allowed environment → “return only complete Lean source/proof body” → no holes/statement changes → small preference for standard Mathlib tactics.

**Repair:** immutable statement hash/reminder → current full source → exact raw Lean diagnostic → failing span if deterministic → “identify root cause privately; return the smallest complete corrected source” → no new assumptions/holes/import changes.

**Compact plan:** target and local hypotheses → prior semantic failures → output exactly 2–4 candidate Lean lemma statements with dependencies and one-line assembly → forbid proof prose longer than the lemma list.

**Critic-only:** source + diagnostic → output `{failure_type, bad_step, proposed_change, relevant_local_fact}` → forbid a full proof. The formalizer receives that record and the source, then gets one attempt.

## Appendix D — Red-team of bare cross-model Lean repair

### Strongest case that it is enough

- It already contains the field’s most reliable elements: a whole-proof proposal, exact compiler feedback, a fresh model context, and strict verification.
- It is easy to implement and ablate against A→A/B→B, reducing the risk that engineering defects swamp the research result.
- MA-LoT/Baldur imply that targeted repair, not elaborate agent society, carries much of the gain.
- Under $1, every planning/decomposition call displaces a potentially useful direct proof or repair.

### Strongest case that it is not enough

- An unconditional handoff spends the expensive model on syntax errors and gives up after mathematical-strategy failures without changing the search object.
- “Different model” is not a coordination mechanism unless the handoff state and trigger are explicit.
- It cannot explain *when* collaboration helps beyond post-hoc anecdotes.
- Delta/Seed/Aristotle suggest that long proofs need stable verified intermediate lemmas, while dual sampling can catch complementary strategies before anchoring on one failure.

### Decision

Keep bare cross-repair as the primary treatment baseline, then add exactly one upgrade: **deterministic error-conditioned routing with bounded semantic escalation**. This adds explanatory power and cost control without turning the system into a swarm.
