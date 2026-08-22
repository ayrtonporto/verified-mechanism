# Verified Mechanisms Take-Home: Full Briefing

Status as of 22 August 2026. Working document, in English so it can be fed to coding agents.

---

## 0. Situation

I applied to Verified Mechanisms and was invited to the take-home round by Karthik Viswanathan.
Two emails so far:

1. **Invitation** (research engineer track), with the RE brief PDF and an OpenRouter API key.
2. **Update**: funding came through, they now hire **four people instead of two** (two research
   scientists, two research engineers). I was placed on the **research engineer** track based on
   my CV and form answers. Both briefs were attached so candidates can switch tracks.

**Key dates**

| Event | Date |
| --- | --- |
| Take-home due | 30 August, EoD Anywhere on Earth |
| Grading | 31 August to 4 September |
| Final interviews | 7 to 11 September |
| Project start | 14 September |
| Project end | 14 December |

**Track switching**

- Moving to **research scientist** takes effect immediately (that task needs nothing from them).
- Moving to **research engineer** requires them to issue an OpenRouter key, up to one day of delay.
- They asked to be told as early as possible.
- I currently hold an RE key, so right now both doors are open.

**Extensions**: explicitly offered if the reason is legitimate. Ask by email.

**Contact**: hiring@verifiedmechanisms.ai

---

## 1. Links

| What | URL |
| --- | --- |
| RE kit repository | https://github.com/VerifiedMechanisms/re-takehome |
| RE rules | https://github.com/VerifiedMechanisms/re-takehome/blob/main/RULES.md |
| RS repository | https://github.com/VerifiedMechanisms/rs-takehome |
| RS theorems directory | https://github.com/VerifiedMechanisms/rs-takehome/tree/main/theorems |
| Lean comparator (scoring tool) | https://github.com/leanprover/comparator |

Submission is through a Google form linked in each brief PDF. Both tracks accept a PDF writeup;
the RE track also requires the GitHub repository link.

---

## 2. The decision: which track

### What each task actually measures

**Research engineer.** Build a coordination layer that makes two fixed models collaborate to
solve maths problems and prove them in Lean 4, then run a controlled experiment on whether the
collaboration beats either model alone. Measures: Python and async engineering, agent design
under hard budget constraints, Docker, empirical experimental design.

**Research scientist.** Read an autoresearch run of ~200 agent-generated theorems about
H*(f), the minimum number of attention heads needed to compute a Boolean function f, decide
which results matter, then produce original results of my own. Bonus for formalising them in
Lean. Measures: mathematical research judgement, ability to produce a new theorem, and research
communication.

### Comparative advantage argument

The RS task sits much closer to my background. It is Boolean function complexity dressed as mech
interp: relating a new complexity measure to established ones, proving upper and lower bounds.
That is the same territory as my thesis work on dualities for bounded distributive lattices with
normal operators. The mech interp framing is a thin layer over combinatorics and complexity.

The rarer asset: being able to **prove a new result and formalise it in Lean 4**. That
intersection is uncommon and is exactly this lab's business. On the RE track I compete against
people who write research infrastructure daily. On the RS track I compete from a position of
relative strength.

Against that: I do not have deep programming fundamentals, and the RE task is engineering end to
end. Claude Code makes it feasible, but I have to defend every design decision in the final
interview.

### Risk asymmetry (the real trade-off)

- **RE has a guaranteed floor.** The kit ships a working single-model baseline, so even a
  mediocre coordination layer scores points and produces data for part two. Near impossible to
  submit nothing. The ceiling is capped by engineering skill.
- **RS has a low floor and a high ceiling.** If no original result on H* materialises in the
  available days, part two is weak and the submission is much thinner. If a result does land and
  gets formalised, the submission stands out.

RE is the low variance bet. RS is the high variance bet that plays my best card.

### How to decide: a timeboxed spike

Do not decide abstractly. The RS repository is public and needs nothing from them.

1. Read `model.md` and `problem_statement.md`.
2. Skim `theorems/` to see what the agents already covered.
3. Answer one question: **do I see an angle?**

If a concrete direction appears within a couple of hours, switch to RS. If nothing lights up,
stay on RE and execute the plan in section 4.

Note that an extension shifts the RS risk calculus much more than the RE one, because the RS
bottleneck is thinking time, not compute time.

---

## 3. Research scientist track: setup and a candidate angle

### The model

A multihead attention module: n input bits plus one query token, H parallel attention heads, and
a linear readout from the query token. A Boolean function f on n bits is *computable with H
heads* if some choice of embeddings, attention parameters and readout reproduces f on every
input.

    H*(f) := min { H : f is computable with H heads }

Known anchors from the brief: one head realises AND or OR on two bits but not XOR; two heads
realise XOR. The open question is how H* depends on f, and whether it can be understood through
established complexity measures.

### Task structure

- **Part one**: review ~200 theorems in `theorems/` produced by autoresearch runs (GPT-5.5, Sol,
  Fable), pick the most promising, explain what makes them useful. A small subset is formalised
  in Lean under `formalization/`; the rest was reviewed only by the agents that produced it.
- **Part two**: independent results the run did not cover. A new upper or lower bound on H*
  counts, and so does a new way of thinking about the problem. Bonus for building on part one
  and for formal verification.

### Writing constraints

- 1 to 10 pages, appendix excluded.
- Build the answer from scratch: set out notation, state each claim precisely, write the argument
  out rather than pointing at the repository. Research communication is explicitly graded.
- Audience: a mech interp researcher who knows the setup and nothing else, and who has not seen
  the repository lemmas.
- Depth over breadth: one direction explored well beats many scoped out.
- Recommended notation: the one used in `rs-takehome`.

### A candidate angle (my speculation, from the brief alone; verify before trusting)

An attention head computes a weighted average over positions, and the readout is linear. For
**symmetric** functions that means one head essentially recovers the number of ones, and the
readout can only threshold that count. This explains the anchors: OR and AND are a single
threshold on the count, so one head suffices. XOR, viewed as a function of the count, alternates
between 0 and 1 at every step, so a single threshold cannot express it.

Conjecture: for symmetric f, H*(f) is controlled by the **number of alternations** of f along the
Hamming weight axis, with matching upper and lower bounds.

If true and not already in the repository, this is a small, clean theorem, provable in days and
formalisable in Lean. Exactly the shape part two asks for. Check `theorems/` first, it may
already be covered.

---

## 4. Research engineer track: everything I know

### The shape of the work

The kit already implements the entire runtime. I write **one function**:

```python
async def solve(problem: Problem, services: Services) -> AgentResult:
    ...
```

in `submission/agent.py`. The harness provides OpenRouter access, per-problem budget accounting,
durable logs, concurrent problem scheduling, Dockerised Lean checking, and final Comparator
scoring. Lean, Mathlib, compiled Mathlib artifacts, the JSON REPL, `lean4export` and Comparator
all come from a pinned Docker image. No host Lean installation needed.

### The three services

| Service | Purpose |
| --- | --- |
| `await services.llm.complete(...)` | Restricted, budgeted, logged OpenRouter call |
| `await services.lean.check_file(source)` | Check a complete Lean file in the networkless Lean container |
| `services.checkpoint(source)` | Preserve a candidate solution during a long run |

**Design rule**: checkpoint every candidate the moment it compiles. If the agent stalls or runs
out of time, the checkpointed solution is what gets scored. Never leave a working proof only in
memory.

### Problem format

Each problem is a folder: `problem.md` states it in English, `challenge.lean` states it formally
with `sorry` where the proof goes. The system turns the folder into a Lean file the compiler
accepts, **with their statement unchanged**. The Comparator exists precisely to detect a weakened
statement. Sixteen sample problems ship in `sample-problems/`; the private holdout has roughly a
dozen in the same format.

### The two models (fixed)

- Model A: `qwen/qwen3.5-flash-02-23`
- Model B: `openai/gpt-oss-120b`

Any sampling parameters, reasoning-effort settings and prompting are allowed. No `:free`,
`:online` or other variant suffix. No OpenRouter plugins.

### Hard rules that constrain the design

1. **Network**: at run time the system may contact **only** `openrouter.ai`, and only with those
   two model IDs. No web search, no other provider. All Python dependencies must be declared in
   `pyproject.toml`; they are installed before the network lock.
2. **No per-problem special-casing.** The system must be problem-agnostic: no hardcoded proofs,
   no databases keyed to specific problems or statements. Generic few-shot examples and generic
   tactic libraries are fine.
3. **Attribution**: building on open-source harnesses is allowed with attribution in the README,
   but the two-model coordination layer must be my own work.
4. **Model participation** is recorded in `result.json` and reviewed separately. It is not a
   mechanical condition for the point, but a "collaboration" where one model does everything will
   be visible and will cost me qualitatively.
5. **Simplicity preference**, stated explicitly: they would rather run a simple design they fully
   understand than a complicated one that scores marginally better. On a near tie, the simpler
   submission wins.
6. They read transcripts, **cross-check them against the key's usage ledger on OpenRouter**, and
   may re-run any reported experiment. Everything in the writeup must be reproducible from the
   repository artifacts.

### Scoring

One point per problem, zero otherwise. A problem scores iff:

- Comparator accepts every required declaration.
- Numeric answer declarations, when present, have valid literal bodies.
- Actual OpenRouter spend for that problem is at most **$1.00** (spend means OpenRouter's returned
  `usage.cost`, summed across both models and every call).
- The problem finishes within its deadline (**8 hours** wall clock).

### How they judge

They clone the repo into the kit devcontainer and run, per problem:

```
OPENROUTER_API_KEY=<fresh key> VM_TIME_LIMIT_S=28800 VM_BUDGET_USD=1.00 \
  python run.py --problems <holdout> --out <out-root>
```

One run per problem, problems isolated: a crash on one zeroes only that problem. They re-verify
every solution themselves. Expected artifacts under `<out-root>/<agent-name>/<timestamp>/`:
`<problem-id>/solution.lean`, `result.json`, `transcript.json`, `events.jsonl`, plus root
`run.json` and `summary.json`. Full LLM content and actual usage must be present. **API keys must
never appear.**

**Crash policy**: if the entrypoint fails in their environment they spend up to 15 minutes on
good-faith fixes, after which the mechanical score stands at whatever completed. Passing
`scripts/judge_check.sh` before submitting is the protection.

### Machine requirements

Docker Engine or Desktop, Python 3.11+, ~20 GB free disk, at least 8 GB RAM for one worker, and
roughly 5 GB more per additional worker. Linux, WSL2, Intel Macs and Apple Silicon supported.

### Useful commands

```bash
bash scripts/setup.sh          # one-time setup
cp .env.example .env           # then add the OpenRouter key; .env is gitignored
bash scripts/smoke_test.sh     # no-key smoke test
bash scripts/judge_check.sh    # judging contract check, run early and often

.venv/bin/python run.py --problems sample-problems --out outputs
.venv/bin/python run.py --problems sample-problems --out outputs --resume latest
.venv/bin/python run.py --problems sample-problems --out outputs --n-workers 2
.venv/bin/python run.py --problems sample-problems --out outputs \
  --agent baselines.simple_agent:create_agent

bash scripts/rescore.sh outputs/submission/<run-name>   # rescore saved solutions
```

Baseline knobs: `BASELINE_MODEL`, `BASELINE_MAX_TURNS`, `BASELINE_MAX_TOKENS`,
`BASELINE_TEMPERATURE`.

---

## 5. Collaboration designs (part one)

Four options, from least to most ambitious.

**A. Portfolio.** Both models attempt the problem independently; take whichever compiles. Trivial
to implement and probably strong, because the two models fail on different things. Note that this
is **not collaboration**, it is diversity. It is the control that any fancier design has to beat.

**B. Role split (informal to formal).** One model does the mathematics in English (finds the
numeric answer, builds the argument), the other translates it into Lean 4. Hypothesis: reasoning
and formalising are separable skills and each model is better at one.

**C. Cross-model repair (most promising).** One model writes the Lean, the compiler returns
errors, and the **other** model reads those errors and proposes the fix. Intuition: a stuck model
repeats its own error because the error comes from its internal model of Mathlib; a second model
in the repair loop breaks the cycle. Also generates excellent part-two evidence, in the form of
transcripts where one model unblocks the other on a specific lemma.

**D. Answer consensus before formalising.** Many problems need a numeric answer as well as a
proof. Ask both models, only proceed when they agree. Cheap, and avoids burning the budget
formalising a wrong answer. A component inside B or C, not a design on its own.

**Recommended path**: implement A first for a floor, then build C with D inside it and A as
fallback. That is a design explainable in one paragraph with a clear mechanistic hypothesis
behind it.

**Role assignment**: GPT-OSS 120b is the larger model, likely the better reasoner and more
expensive. Qwen flash is small, fast and cheap, so it supports many attempts. That suggests Qwen
generating candidate volume and GPT-OSS diagnosing and repairing. Do not assume this, **measure
it**: measuring that asymmetry is literally part two.

---

## 6. Experimental design (part two)

This is where the submission can differentiate itself. Most candidates will report three
aggregate numbers and declare victory.

**Budget control is confounder number one.** If the collaboration makes twice as many calls as a
solo run, the comparison is more compute versus less compute, not collaboration versus solo. The
honest comparison is at **matched spend**: if the collaboration spends $0.40 per problem, the
solo baselines must also be allowed $0.40, via more attempts or more repair turns.

**Compare against the union, not the mean.** A problem that Qwen alone solves and GPT-OSS alone
does not is already solved by the pair trivially. The collaboration must solve problems that
**neither model solves alone**. Those cases carry the transcripts.

**Statistics with small n.** Sixteen sample problems, binary outcomes. A two-problem difference
can be pure noise. Run repetitions with different seeds per condition to estimate variance. The
data are binary and paired (same problem under three conditions), so McNemar is the natural test.

**The table to produce**: problems by conditions, ordered so the four quadrants are visible:
solved by all, solved by none, solved only by the collaboration, and **solved by one solo model
but broken by the collaboration**. That last quadrant always exists and hiding it is noticeable.

---

## 7. Execution plan (RE track)

Ordering, not a schedule.

- **Phase 0, reconnaissance.** Bring up Docker, run `smoke_test.sh` with no key, read
  `docs/AGENT_API.md` in full, inspect two or three sample problems, run `judge_check.sh` on the
  untouched repo to see what it checks.
- **Phase 1, economic calibration.** Run the baseline with each model separately on one or two
  problems and read the real `usage.cost` in the transcript. Extrapolate: cost of a full sixteen
  problem run, number of full runs that fit in $50. Everything else depends on this number and it
  is available within the first hour. Do not plan experiments before having it.
- **Phase 2, full baselines.** Qwen solo and GPT-OSS solo over all sixteen, using their baseline.
  This is the floor and half the part-two data.
- **Phase 3, portfolio.** Design A. Tells me how much of the gain is pure diversity.
- **Phase 4, the real design.** C with D inside. Iterate on the sample problems until it beats
  the portfolio.
- **Phase 5, final experiments.** Three conditions at matched budget, with repetitions. **Freeze
  the code first** and do not touch it during the final runs.
- **Phase 6, writeup and submission.** 1 to 10 pages in English, `judge_check.sh` green, clean
  clone run from scratch in a separate directory.

Phases 2 and 5 consume the money. If phase 1 says a full run costs $8, there is room for about
five or six runs total and they need planning, not improvisation.

---

## 8. API key hygiene (non-negotiable)

The submission is a public GitHub repository. A leaked key is both a security problem and a bad
look during grading.

- Key goes in `.env` (already gitignored) or an exported environment variable, never in source.
- The kit ships `.env.example`; copy it, never edit and commit the original with a real value.
- Before submitting, verify the key never entered git history:

```bash
git log -S "sk-or-v1" --oneline      # must return nothing
git log --all --full-history -- .env  # must return nothing
```

- Removing a key from the working tree does not remove it from history. If it ever lands in a
  commit, the history has to be rewritten.
- The key must never appear in `transcript.json` or any other artifact. The harness redacts
  secrets, but verify.
- They evaluate with a separate key, so the whole $50 is available for development and
  experiments.

---

## 9. Working with Claude Code

1. First task: have it read `RULES.md`, `docs/AGENT_API.md`, `baselines/simple_agent.py` and
   `src/re_harness/`, then summarise the exact interface: fields of `Problem`, expected shape of
   `AgentResult`, signature of `services.llm.complete`. Do not guess these types.
2. Write a `CLAUDE.md` at the repository root with the hard constraints: the two model IDs, the
   no-special-casing rule, the openrouter-only network, the simplicity preference, and the mandate
   to checkpoint every compiling candidate. This prevents proposals that violate the rules, the
   typical failure mode when vibecoding against an unusual spec.
3. The repository already ships a `.claude/commands` directory. Check what is there before
   inventing custom commands.
4. Ask for a prose explanation of the flow **before** any code is written. Every part of
   `agent.py` has to be defensible in the writeup and in the final interview.

**Caching caveat**: a response cache is a development tool only. It must live outside
`submission/agent.py` and must not ship with the submission, because a cache of responses keyed to
the sample problems is exactly the database rule 2 forbids. To avoid redoing work across runs, use
the harness's own `--resume`.

---

## 10. Open items

- [ ] Confirm the machine meets the Docker / 20 GB / 8 GB RAM requirements.
- [ ] Do the RS spike: read `model.md`, `problem_statement.md`, skim `theorems/`.
- [ ] Decide the track and email `hiring@verifiedmechanisms.ai` early either way.
- [ ] Decide whether to request an extension, and with what reason.
- [ ] Prepare the LLM disclosure for the submission form (which models and tools, and how used).
