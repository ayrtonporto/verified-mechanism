# Research Brief — Multi-Model Coordination for Formal Math / Lean

**Document type:** Self-contained research assignment for another model (or human researcher)  
**Language:** English (deliverable must be English)  
**Project context:** Verified Mechanisms Research Engineer take-home (internal use)  
**Date written:** 2026-08-24  
**Primary goal of this brief:** Map recent (≈ last 12–18 months, with emphasis on 2025–2026) ideas that *actually moved the needle* on mathematical problem solving and formal proof (especially Lean), with priority on **multi-model / multi-agent coordination**, so we can choose a simple but non-naive coordination design instead of reinventing a thin baseline.

---

## 0. How to use this document

You are a research analyst. You are **not** implementing code and **not** solving our take-home.

Your job:

1. Survey what has worked recently in LLM math + formal verification agents.
2. Extract **mechanisms** (coordination patterns), not brand names.
3. Rank what is transferable to a **two-fixed-model, Lean-in-the-loop, $1/problem** setting.
4. Deliver a structured memo we can turn into design decisions in 1–2 hours of reading.

**Do not invent citations.** If you cannot verify a paper/system, label it `UNVERIFIED` or omit it. Prefer primary sources (papers, official blogs, GitHub READMEs, eval leaderboards with clear protocols).

**Recency:** Prefer work from **2024-06 → 2026-08**, and flag anything older only if it is still the conceptual root (e.g. draft-repair-with-compiler-feedback).

---

## 1. Our setting (constraints you must respect)

We are designing a **coordination layer** between exactly two fixed chat models (via an API), to solve math problems and produce **Lean 4** proofs accepted by a compiler/comparator.

### Hard constraints (non-negotiable)

| Constraint | Detail |
|---|---|
| Models | Exactly two fixed model IDs (think: one strong open “reasoner-class” model + one fast/cheap model). **No** swapping in GPT-5 / Claude / o3 at runtime. |
| Network at runtime | Only the LLM API + local Lean tooling. **No** web search, **No** arbitrary tools, **No** Mathlib RAG service unless it is local and already allowed (assume **no external retrieval** unless you mark an idea as “needs retrieval — low transfer”). |
| Verification | Lean 4 + Mathlib inside a sandbox. Feedback = compiler/REPL diagnostics. Final accept/reject is strict (comparator-style). |
| Budget | Roughly **≤ $1 USD per problem** API spend and long wall-clock allowance; real development budget is small (tens of dollars total). |
| Problem form | English statement + Lean skeleton with `sorry`; must keep theorem statements unchanged. |
| Design preference of graders | **Simple and understandable** coordination beats a complex system with marginal gains. |
| Scientific requirement | Must compare: model A solo, model B solo, collaboration; explain **when/why** collab helps; control confounds (extra calls, cost, Lean iterations). |
| Forbidden | Per-problem hardcoded proofs; problem-id lookup tables of solutions. |

### What “success” means for ideas you recommend

An idea is valuable if it could plausibly raise:

\[
P(\text{Lean proof accepted} \mid \text{coordination protocol})
\]

under the constraints above, **and** admit a clean ablation (e.g. same-model roles vs cross-model, with/without compiler feedback, with/without decomposition).

---

## 2. Research questions (answer explicitly)

### RQ1 — Single-agent formal math (baseline of the field)
What pipelines dominated recent Lean/formal math agents?

Break down into reusable pieces:

- whole-proof generation vs stepwise tactics
- compiler-feedback repair loops
- lemma / subgoal decomposition
- search (best-first, MCTS, beam, rejection sampling)
- premise selection / library awareness (without external web)
- informal → formal bridges (draft in natural language, then formalize)
- repair specialized prompts vs generic “try again”
- when people use temperature/diversity vs greedy

### RQ2 — Multi-agent and multi-model coordination
What coordination patterns have empirical support?

Catalog at least these families (add more if warranted):

1. **Propose → verify → repair** (possibly different models)
2. **Generator–critic** / debate (does debate help formal math or mostly free-form QA?)
3. **Planner–executor** (informal plan vs Lean coder)
4. **Dual (or n) sampling + selection** by a verifier (Lean as selector, not an LLM judge)
5. **Role specialization** (algebraist vs Lean syntax specialist, etc.)
6. **Blackboard / shared workspace** of lemmas and obligations
7. **Router / portfolio** policies (pick strategy by failure mode)
8. **Self-consistency / majority** over informal answers vs formal proofs (different!)
9. **Same model, multiple roles/skills** vs **different models**
10. **Hierarchical decomposition** (IMO-style: sketch → lemmas → fill)

For each pattern that mattered in the literature or strong systems: mechanism, evidence quality, cost profile, failure modes.

### RQ3 — What is *causal* vs *more compute*?
The field is full of systems that win because they spend 100× more tokens.

We need you to flag, for each hot idea:

- Does the paper/system control for **equal budget** (calls, tokens, $ , wall time, verifier queries)?
- Is the gain from **heterogeneous models** or from **protocol structure**?
- Is the verifier (Lean/Python/sympy) doing the real work as a filter?

### RQ4 — Math contests vs formal proofs
Separate evidence:

| Track | Examples of goals | Transfer to our Lean setting |
|---|---|---|
| Informal math (AIME/IMO shortlist, answer only) | numeric/expression answers | Partial — strategy transfer, not proof transfer |
| Autoformalization | NL → Lean statement/proof | High if proof-oriented |
| Whole-proof Lean synthesis | Mathlib theorems, miniF2F, ProofNet, PutnamBench-like | **Highest** |
| Tactic-level RL / search | tactic policies, proof search | Medium — may be heavy for 2-API-model setup |
| Tool-using agents (code exec, CAS) | Python/SymPy loops | Low/medium — we have Lean, not free CAS unless inside Lean |

Do **not** collapse “got AIME 90” with “produces Lean that compiles.”

### RQ5 — Heterogeneous model pairs
Any evidence that **pairing dissimilar models** beats:

- best single model alone, and
- same model playing both roles,

especially under **matched budget**?

We care a lot about this. Our scientific story may be: cross-model helps **or** protocol helps even with one model.

### RQ6 — What failed or plateaued?
List ideas that were fashionable but weak for formal proof:

- long multi-agent debate without a verifier
- pure voting on proof text
- huge persona prompts
- unconstrained blackboards that drift
- retrieval that doesn’t match the local Mathlib version

Negatives save us time.

---

## 3. Scope of sources

### Must search / cover

- arXiv (cs.AI, cs.LG, cs.LO, math.LO): Lean agents, autoformalization, multi-agent reasoning, formal math benchmarks
- Systems / blogs with evals: DeepMind (AlphaProof-related public writeups), OpenAI/ICLR formal math notes if any, academic Lean agent papers
- Benchmarks and what tops them (with protocol notes): miniF2F, ProofNet, PutnamBench, LeanDojo-related, FrontierMath (informal; careful), AIME/HMMT agent writeups only as informal-math transfer
- Multi-agent frameworks **only if** they report math/formal results (AutoGen/Crew/LangGraph-style posts without Lean numbers are low priority)
- 2025–2026 “agentic math” surveys if reputable

### Priority keywords (use combinations)

```
Lean 4 LLM agent proof repair
autoformalization multi-agent
compiler feedback theorem proving LLM
miniF2F whole proof generation
PutnamBench LLM
lemma decomposition LLM Lean
draft sketch formalize Lean
multi-model collaboration LLM
generator critic formal verification
portfolio theorem proving
imitation recovery Lean error messages
heterogeneous LLM ensemble math
```

### Time window

- Core survey: **2024-06 to 2026-08**
- Include earlier seminal items only as “roots” (e.g. early draft-and-repair, LeanDojo, DSP-style draft-sketch-prove if still cited as backbone)

---

## 4. Deliverable format (strict)

Produce a single markdown memo: `SOTA_MULTI_MODEL_MATH_MEMO.md`

### Section A — Executive summary (≤ 20 lines)
- 5–10 bullets: what actually works now
- 3 bullets: what does *not* transfer to our constraints
- 1 recommended “default modern stack” for a 1-week two-model Lean agent

### Section B — Landscape map
A table:

| Mechanism | Informal math evidence | Formal/Lean evidence | Cost | Complexity | Transfer to 2-model+$1 | Notes |
|---|---|---|---|---|---|---|

Score transfer as `High / Med / Low`.

### Section C — Deep dives (8–15 items max)
For each important paper/system:

```markdown
### [Short name] — Title (year)
- **Type:** informal math | autoformalization | Lean whole-proof | tactic RL | multi-agent | other
- **Venue / link:** ...
- **Core mechanism:** 3–6 sentences
- **Coordination pattern:** (from RQ2 list or new name)
- **Verifier role:** none | python | lean | other
- **Models used:** homogeneous / heterogeneous; which
- **Headline result:** (benchmark + number + baseline)
- **Budget honesty:** controlled? matched? unknown?
- **Why it worked (authors + your read):**
- **Failure modes:**
- **Transfer recipe for us:** concrete, 5–10 lines (what to copy, what to drop)
- **Ablation we should run if we adopt it:**
- **Confidence in this summary:** high | med | low
```

Prefer fewer deep dives done carefully over a dump of 40 names.

### Section D — Mechanism cookbook (the valuable part)
Rewrite the field as **design patterns** independent of branding:

For each pattern:

1. **Name**
2. **Information flow diagram** (ASCII is fine)
3. **State shared between agents** (what must be on the blackboard)
4. **Stop conditions**
5. **When it helps** (hypothesis)
6. **When it hurts** (cost, drift, regression)
7. **Minimal implementation** in a world with only:
   - `llm.complete(model, messages)`
   - `lean.check_file(source) -> diagnostics`
   - checkpoint(best_so_far)
8. **Required ablations**
9. **Estimated relative cost** vs single-model repair loop (e.g. 1.0×, 1.5×, 3×)

Must include at least:

- single-model compiler repair loop
- cross-model repair handoff
- same-model dual-role (propose/repair) control
- planner–formalizer split
- dual-propose + Lean selection
- subgoal/lemma workspace (minimal)
- error-type-conditioned repair policy
- adaptive compute / early stop
- (optional) critic-only reframe without drafting full proofs

### Section E — Heterogeneity: when two models beat one
A focused subsection:

- Evidence for complementary skills (math planning vs formal detail, etc.)
- Evidence that **same model + good protocol** captures most gains
- Any results on **asymmetric roles** (strong proposer + weak repairer or vice versa)
- Practical recommendation for a fast model + a large open model pair

### Section F — Confounders checklist (for our Part Two)
A concrete checklist we should report in experiments, distilled from how strong papers avoid fooling themselves.

### Section G — Ranked recommendations for *our* project

Rank **top 5 coordination designs** we should consider this week:

For each:

| Field | Content |
|---|---|
| Rank | 1–5 |
| Name | |
| One-sentence thesis | |
| Novelty vs bare cross-repair | low/med/high |
| Implementation effort | S/M/L (in days for 1 engineer+AI assist) |
| Eval cost | S/M/L |
| Scientific story quality | how publishable/explainable in a 5-page RE writeup |
| Risk | |
| First experiment to run | |
| Kill criterion | when to abandon |

Then give a **suggested 7-day research+build sequence** that front-loads measurement and still leaves room for one “idea upgrade.”

### Section H — Bibliography
Normalized list with links/arXiv IDs. Mark `READ` vs `SKIM` priority.

### Section I — Open questions / unknowns
What you could not resolve; what we must measure ourselves.

---

## 5. Evaluation criteria for *your* memo quality

We will judge your memo by:

1. **Actionability** — can we pick a design tomorrow?
2. **Constraint fit** — ruthless about $1, two fixed models, Lean-only tools
3. **Causal honesty** — call out budget confounds
4. **Non-generic advice** — not “use chain of thought and agents”
5. **Separation of informal vs formal evidence**
6. **Ablations first-class** — especially same-model multi-role vs cross-model
7. **Simplicity bias** — prefer mechanisms graders can understand

---

## 6. Anti-goals (do not do these)

- Do not write our `submission/agent.py`.
- Do not propose fine-tuning, RL training, or building a new Lean kernel.
- Do not depend on proprietary hidden tools we cannot call at runtime.
- Do not recommend 5+ agent swarms as the default.
- Do not treat leaderboard screenshots without method as evidence.
- Do not ignore **same-model role separation** as a control; it is central to our scientific claim.
- Do not assume infinite Mathlib premise retrieval.
- Do not equate “multi-agent” with “better”; demand a coordination object (shared state, handoff rule, selection rule).

---

## 7. Seed hypotheses we already hold (challenge or refine them)

These are **priors**, not truths. Attack them if evidence disagrees.

1. **H1 — Compiler feedback is the highest-value coordination signal** for formal success; free-form debate without Lean is weak.
2. **H2 — Cross-model handoff helps only if models err differently**; otherwise same-model dual-role ≈ cross-model.
3. **H3 — Informal plan → formalize** beats direct whole-proof generation on harder problems.
4. **H4 — Lemma/subgoal blackboards help mainly when monolithic proofs fail**, not on short algebra goals.
5. **H5 — Lean as selector among diverse candidates** is more reliable than an LLM-as-judge over proofs.
6. **H6 — Error-type routing** (syntax/type/library/math-gap) beats a single generic repair prompt.
7. **H7 — Most published multi-agent gains are unmatched-compute artifacts.**

For each hypothesis, say: **supported / mixed / contradicted / unknown**, with citations.

---

## 8. Minimum evidence standard

When you say something “works”:

- Name the **benchmark**
- Name the **baseline**
- Say whether verification is **formal** or **answer-only**
- Say whether budget was **matched**
- Give a **confidence** tag

If a famous system lacks public protocol detail (e.g. partial AlphaProof disclosure), separate **publicly reproducible claims** from **reported claims**.

---

## 9. Suggested search workflow (for the research model)

1. Start with recent surveys + Lean agent papers (2024–2026).
2. Build a list of mechanisms; merge duplicates under pattern names.
3. For each pattern, find the **strongest empirical report** and the **best simple reproduction story**.
4. Filter by transfer score under Section 1 constraints.
5. Write Section D (cookbook) before final rankings — rankings must fall out of mechanisms, not hype.
6. Explicitly answer RQ5 (heterogeneity) even if the answer is “weak evidence.”
7. End with top-5 designs + kill criteria.

---

## 10. One-page “good answer” example (style only; invent nothing)

Your tone should look like:

> “Pattern P (planner→formalizer→Lean repair) shows repeated gains on miniF2F-style whole-proof settings when the planner is allowed only informal sketches and the formalizer may not change the theorem statement. Gains often shrink under equal Lean-iteration budgets; the residual gain, when present, comes from fewer doomed proof strategies. Debate without verifier shows little formal benefit. For a two-model $1 cap, implement P with max K repair steps, ablate same-model roles, and use Lean—not an LLM—to accept candidates.”

That level of sharpness is the bar.

---

## 11. Optional appendix requests

If time allows, add:

- **Appendix A:** Glossary (DSP, whole-proof vs tactic, comparator, etc.)
- **Appendix B:** Benchmark cheat-sheet (what each measures / contamination risks)
- **Appendix C:** “Steal these prompt structures” — only high-level structure, not long copyrighted prompts
- **Appendix D:** Red-team of our Candidate A (cross-model Lean repair only): strongest arguments it is enough / not enough

---

## 12. Output checklist before you finish

- [ ] Executive summary present
- [ ] ≥ 8 deep dives with links/arXiv and confidence tags
- [ ] Mechanism cookbook with ASCII flows + ablations
- [ ] Explicit same-model vs cross-model discussion
- [ ] Top-5 ranked designs with kill criteria
- [ ] Hypotheses H1–H7 labeled supported/mixed/contradicted/unknown
- [ ] Informal vs formal evidence separated throughout
- [ ] No unimplemented fantasy tools
- [ ] Bibliography with priority marks

---

## 13. Context blurb (for the researcher’s motivation only)

We already plan night-time measurement runs for:

- Model A solo (compiler repair loop)
- Model B solo
- Cross-model collaboration
- Same-model dual-role control

We are worried this is **methodologically correct but idea-thin**. Your memo should tell us which **one additional coordination object** (shared plan, lemma workspace, dual-propose+Lean-select, error router, etc.) is most justified by recent evidence under tight budgets—and which popular ideas we should ignore.

---

## 14. Final instruction

Return the memo as markdown only. Be opinionated. Prefer “do X, not Y” backed by evidence tiers. If the literature is thin on true multi-model *formal* gains, say so clearly—that result alone is valuable.
