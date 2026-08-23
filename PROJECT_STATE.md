# PROJECT_STATE

## 0. Project

**Verified Mechanisms — Research Engineer Take-Home**

Deadline: **August 30, 2026 — EOD Anywhere on Earth**

Primary objective:

> Design a coordination layer that makes the fixed Qwen and GPT-OSS models collaborate to solve mathematical problems and produce Lean 4 proofs accepted by the evaluator.

Secondary/scientific objective:

> Determine whether collaboration actually outperforms either model working alone, and characterize when and why collaboration helps.

The submission consists of:

- GitHub repository.
- Agent implementation in `submission/agent.py`.
- PDF writeup of 1–10 pages, excluding appendix.
- Empirical comparison of:
  - Qwen solo.
  - GPT-OSS solo.
  - Collaboration.

The runtime system may use only the two fixed models specified by Verified Mechanisms:

- Qwen: `qwen/qwen3.5-flash-02-23`
- GPT-OSS: `openai/gpt-oss-120b`

The evaluation is based on Lean proofs accepted by the provided evaluation infrastructure. Each holdout problem has a maximum budget of **$1** and an **8-hour wall-clock cap**.

---

## 1. Current interpretation of the task

This is not primarily a prompt-engineering task.

The object being designed is the **coordination mechanism** between two fixed models.

We therefore care about:

\[
P(\text{Lean proof accepted} \mid \text{coordination protocol})
\]

subject to runtime and monetary constraints.

Lean should be treated not merely as a final judge, but potentially as an information-producing component of the search process:

\[
\text{candidate}
\rightarrow
\text{Lean}
\rightarrow
\text{diagnostic}
\rightarrow
\text{repair}
\rightarrow
\text{Lean}.
\]

The scientific question is not merely:

> Does collaboration score higher?

but:

> Under controlled compute, when does collaboration change the outcome of a problem, and what contribution from one model enables that change?

The take-home explicitly asks for per-problem comparison and for confounding factors to be accounted for.

---

## 2. Engineering philosophy

### 2.1 Repository as external memory

No critical project state should exist only inside a Codex or Claude Code conversation.

Persistent context belongs in the repository.

Every agent session should begin by reading:

1. `PROJECT_STATE.md`
2. `HANDOFF.md`
3. Relevant experiment/design documents.
4. Relevant source code.
5. `RULES.md` and `docs/AGENT_API.md` when execution constraints are relevant.

Every meaningful work session should end by updating persistent state.

### 2.2 Simplicity over uncontrolled complexity

Verified Mechanisms explicitly prefers a simple collaboration design that can be understood over a complicated system that provides only marginal gains.

Therefore:

- every mechanism should have a hypothesis;
- every mechanism should be ablatable;
- unnecessary agent roles should be avoided;
- every additional model call should have a reason;
- every important architectural choice should be experimentally testable.

---

## 3. Initial research hypotheses

These are **working hypotheses**, not established facts.

### H1 — Compiler-feedback collaboration

Collaboration helps when one model can repair or reinterpret failures produced by another model after Lean provides precise compiler feedback.

Minimal loop:

\[
M_1
\rightarrow
\text{candidate proof}
\rightarrow
\text{Lean}
\rightarrow
\text{error}
\rightarrow
M_2
\rightarrow
\text{repair}.
\]

### H2 — Functional specialization

The two models may have complementary strengths for different roles, for example:

- mathematical decomposition;
- Lean proof synthesis;
- compiler-error diagnosis;
- repair;
- critique;
- simplification.

We do **not** currently assume which model is superior at each role.

Role assignment should be calibrated empirically.

### H3 — Shared formal artifacts

Collaboration may improve when models communicate through structured intermediate artifacts rather than unrestricted conversation.

Candidate mechanism:

#### Blackboard / lemma workspace

A shared state containing:

- target theorem;
- proposed proof strategy;
- candidate lemmas;
- Lean formulation of each lemma;
- verification status;
- compiler diagnostics;
- provenance;
- unresolved obligations.

Example:

```text
Goal T
│
├── L1 : verified
├── L2 : failing
│     └── Lean diagnostic: ...
└── L3 : unattempted
```

Potential advantage:

Collaboration happens over **formal intermediate objects** rather than prose alone.

This hypothesis must be compared against simpler collaboration mechanisms before being adopted.

---

## 4. Required baselines

At minimum, experiments should contain:

### B1 — Qwen solo

Qwen receives the problem and has access to the same Lean-feedback mechanism permitted to collaborative agents.

### B2 — GPT-OSS solo

GPT-OSS under an analogous setup.

### B3 — Minimal collaboration

A simple two-model protocol.

Candidate initial design:

1. Model A proposes solution/proof.
2. Lean checks it.
3. Model B sees:
   - problem;
   - attempted proof;
   - Lean output.
4. Model B diagnoses or repairs.
5. Lean checks again.
6. Repeat under explicit limits.

### B4 — Enhanced collaboration

Only after B1–B3 are stable.

Candidate:

Structured blackboard / lemma decomposition.

---

## 5. Experimental principles

For every experimental condition record at least:

- problem identifier;
- condition;
- success/failure;
- final Lean status;
- number of model calls;
- calls by model;
- token usage if available;
- dollar cost;
- wall-clock time;
- number of Lean compilation attempts;
- number and type of compiler failures;
- final proof;
- transcript/log path;
- git commit;
- random/configuration seed where applicable.

The central per-problem result matrix should eventually resemble:

| Problem | Qwen | GPT-OSS | Collaboration |
|---|---:|---:|---:|
| P1 | 0/1 | 0/1 | 0/1 |
| P2 | 0/1 | 0/1 | 0/1 |

Particularly informative outcome classes:

#### Synergy

\[
(Q,G,C)=(0,0,1)
\]

Collaboration succeeds where neither solo system succeeds.

#### Qwen rescue

\[
(1,0,1)
\]

#### GPT-OSS rescue

\[
(0,1,1)
\]

#### Collaboration regression

\[
(1,1,0),\;(1,0,0),\;(0,1,0)
\]

These failures are scientifically important and should not be hidden.

---

## 6. Confounders to control

A collaboration system can appear superior simply because it receives more inference compute.

Potential confounders:

- total number of model calls;
- total tokens;
- dollar spend;
- number of Lean-feedback iterations;
- wall-clock budget;
- context size;
- retries;
- prompt length;
- access to previous failed attempts.

Where practical, compare systems under approximately matched:

\[
\text{cost},
\quad
\text{calls},
\quad
\text{Lean interactions}.
\]

If exact matching is impossible, report the mismatch explicitly.

---

## 7. Planned phases

### Phase 0 — Repository understanding

Status: **MOSTLY DONE** (env unblocked 2026-08-23; `judge_check.sh` still pending until key + agent/baseline run)

Tasks:

- [x] Read repository documentation / AGENT_API / RULES / baseline.
- [x] Understand Lean invocation + comparator (smoke green).
- [x] WSL image pull + health + smoke + REPL path.
- [ ] Run `scripts/judge_check.sh` (needs key + non-stub agent or baseline flag).
- [ ] Own baseline runs (kit `outputs/baseline/*` are reference only).

Do not modify architecture before finishing calibration measurements.

### Phase 1 — Instrumentation

Build a reliable experiment harness before optimizing agent behavior.

Required capabilities:

- deterministic experiment naming;
- structured logs;
- cost accounting;
- transcript persistence;
- Lean compiler output capture;
- per-problem result serialization;
- reproducible configuration.

### Phase 2 — Solo baselines

Run:

- Qwen solo.
- GPT-OSS solo.

Use identical or closely comparable budgets.

Goal:

Establish the empirical complementarity landscape.

Questions:

- Which problems does each solve?
- Which failures are mathematical?
- Which failures are Lean-specific?
- Which failures appear repairable after compiler feedback?

### Phase 3 — Minimal collaboration

Implement the simplest defensible collaboration mechanism.

Primary candidate:

**propose → verify → diagnose/repair → verify**

Avoid adding blackboard decomposition until this protocol has measurable results.

### Phase 4 — Analyze failure modes

Create a taxonomy.

Candidate categories:

- incorrect mathematical strategy;
- correct mathematics, invalid Lean;
- missing library/theorem knowledge;
- tactic failure;
- type mismatch;
- elaboration failure;
- local repair failure;
- context drift;
- repeated identical failure;
- excessive cost/search.

The taxonomy should emerge from transcripts rather than being imposed blindly.

### Phase 5 — Enhanced collaboration

Use Phase 3–4 evidence to decide whether to implement:

- explicit critic;
- role switching;
- lemma decomposition;
- blackboard;
- adaptive routing;
- confidence-based arbitration;
- multiple candidate generation.

Do not implement mechanisms without an associated hypothesis.

### Phase 6 — Ablations

Possible experiments:

- collaboration without compiler feedback;
- same model playing both roles;
- fixed role assignment vs dynamic role assignment;
- blackboard vs raw transcript;
- equal-budget collaboration vs equal-call collaboration;
- one repair round vs multiple repair rounds.

### Phase 7 — Final evaluation

Freeze the agent architecture.

Run full sample benchmark under reproducible configuration.

Generate:

- result table;
- costs;
- success counts;
- transcripts;
- selected case studies.

No architectural changes after results used in the final writeup unless experiments are rerun.

### Phase 8 — Writeup

Writeup must explain:

- harness design choices;
- results;
- scientific understanding of collaboration.

Potential structure:

1. Problem
2. Coordination design
3. Experimental methodology
4. Main results
5. When collaboration helps
6. Failure modes
7. Ablations/confounders
8. Limitations
9. Conclusion

Appendix:

- prompts;
- detailed tables;
- selected transcripts;
- extra experiments.

---

## 8. Working calendar

### Saturday Aug 22

Environment and repository understanding.

Deliverable:

- baseline runs;
- constraints understood;
- experiment infrastructure plan.

### Sunday Aug 23

Instrumentation + solo baselines.

Deliverable:

- Qwen and GPT-OSS baseline data.

### Monday Aug 24

Minimal collaboration implementation.

Deliverable:

- first reproducible collaborative system.

### Tuesday Aug 25

Failure analysis + improved coordination.

Deliverable:

- evidence-based architectural iteration.

### Wednesday Aug 26

Full experiments.

Deliverable:

- main comparison table.

### Thursday Aug 27

Ablations and confounder analysis.

Deliverable:

- scientific evidence for/against hypotheses.

### Friday Aug 28

Writeup.

Deliverable:

- complete first draft.

### Saturday Aug 29

Freeze + validation.

Tasks:

- clean repository;
- rerun experiments where necessary;
- run `scripts/judge_check.sh`;
- validate PDF;
- inspect Git history;
- final reproducibility check.

### Sunday Aug 30

Submission.

No unnecessary architecture changes.

---

## 9. Context-management protocol

### Beginning of every coding-agent session

The agent must:

1. Read `PROJECT_STATE.md`.
2. Read `HANDOFF.md`.
3. Read current relevant code.
4. Read any referenced experiment logs.
5. Summarize its understanding before making large architectural changes.

Suggested instruction:

> Read PROJECT_STATE.md and HANDOFF.md first. Treat them as authoritative project memory. Inspect the relevant code and experiment logs before making changes. Do not alter project-level decisions silently.

### During work

Any significant decision must be recorded.

Significant means:

- architecture changes;
- prompt/protocol changes;
- experiment methodology changes;
- evaluator discoveries;
- unexpected constraints;
- abandoned approaches;
- new failure modes;
- changes affecting reproducibility.

### End of every coding-agent session

The agent must:

1. run relevant tests;
2. record experiments;
3. update `PROJECT_STATE.md` if global state changed;
4. completely rewrite `HANDOFF.md`;
5. commit coherent changes;
6. leave repository in a resumable state.

---

## 10. Git discipline

Prefer small, semantically meaningful commits.

Examples:

```text
chore: verify baseline and judge setup
feat: add structured experiment logging
exp: run qwen solo baseline
exp: run gpt-oss solo baseline
feat: add compiler-feedback repair loop
exp: compare minimal collaboration against solo baselines
analysis: classify lean failure modes
feat: add lemma blackboard
exp: ablate blackboard coordination
docs: draft methodology and results
```

Never combine unrelated experimental and architectural changes when avoidable.

Experiments should identify the commit that generated them.

---

## 11. Current decisions

### D001 — Repository is authoritative memory

Accepted.

### D002 — Instrument before optimizing

Accepted.

### D003 — Solo baselines precede architectural conclusions

Accepted.

### D004 — Lean compiler feedback is treated as a potential coordination signal

Accepted as a hypothesis to test.

### D005 — Blackboard/lemma decomposition is promising but not yet selected as final architecture

Accepted.

It must earn its complexity empirically.

### D006 — Roles are functional, not permanently attached to a specific model

Accepted.

We will empirically test which model performs which role better.

---

## 12. Unknowns / must verify from repository

The take-home document does not fully specify these details.

Do not guess them.

- Exact `submission/agent.py` API.
- Permitted filesystem behavior.
- Permitted subprocess behavior.
- Exact evaluator invocation.
- Exact OpenRouter interface supplied by the repository.
- How cost is calculated/enforced.
- How Lean feedback can be obtained during a run.
- Whether parallel model calls are permitted/useful.
- Exact output format.
- Comparator restrictions.
- Any restrictions in `RULES.md`.
- Baseline prompting/configuration.
- Mathlib/Lean versions.

These become immediate investigation targets.

---

## 13. Compute environment & infrastructure (as of 2026-08-23)

### 13.1 Repository

- Private working repo: `https://github.com/ayrtonporto/verified-mechanism` (**private**).
- Layout: whole working folder pushed **verbatim**; the pristine kit lives untouched at
  `re-takehome-main/` (nested), planning docs + brief PDF alongside. Git initialized at the
  parent level; `core.autocrlf=false` so the kit stays byte-for-byte (LF) and Linux-friendly.
- No secrets in history: only `.env.example` is tracked; the single `sk-or-v1` string is the
  example grep in the briefing, not a key.
- Cloned on `sshrun` at `~/Documentos/verified-mechanism` (remote URL scrubbed of token).

### 13.2 Two machines

| | **Ryzen box** (this Windows laptop) | **sshrun** (always-on Linux) |
|---|---|---|
| CPU | AMD Ryzen 7 7730U, 8c/16t, AVX2 (x86-64-v3) | AMD A4-3300 APU, **2011**, 2c, **x86-64-v1** (no SSE4.2/AVX) |
| RAM | 15 GB (WSL sees 7.8 GB) | 14 GB |
| Access | interactive; user powers it on/off | Tailscale `usuario@sshrun`, key-auth works, passwordless sudo |
| Docker | **v29.1.3 already in WSL2 Ubuntu-22.04**, distro on **D:** (`D:\WSL\Ubuntu2204`) | v29.7.1, kit fully set up |
| Kit status | uv + Python 3.11.16 ✓, repo cloned into `~/verified-mechanism` ✓; **image pull BLOCKED by host-RAM exhaustion** (see 13.6) | `setup.sh` OK, image pulled, health OK, smoke OK |

### 13.3 Key finding — sshrun is compatible but far too slow

- Lean **runs** on the 2011 CPU (health OK, Lean 4.32.0). No SIGILL. Compatibility confirmed.
- But the no-key smoke test (single trivial problem `p01_linear`) took **14 min 24 s** wall clock
  (Challenge build 217s, Solution build 151s, + comparator). ~10–15× slower than a modern box.
- **Confounder risk for Part Two:** the harness enforces a per-problem time cap
  (`VM_TIME_LIMIT_S`). On slow hardware a problem can hit the cap and **falsely fail**, when it
  would pass on the graders' faster machines → corrupts the "which condition solves what" matrix.
- Image is pinned by digest `ghcr.io/verifiedmechanisms/re-takehome-lean@sha256:ee48287c…`
  (Lean v4.32.0, Mathlib `81a5d257`, comparator `07bc4ea4`). Same image graders use → reproducible.

### 13.4 Decisions

- **D007 — Develop and run all scientific (Part Two) experiments on the Ryzen/WSL2 box.** Timing
  there is representative; sshrun's slowness would bias results via false timeouts. Grading runs on
  the lab's own hardware, so our dev machine choice does not affect the final score, only validity.
- **D008 — sshrun reserved (if at all) for timing-insensitive throughput only.** For "always-on +
  fast + unattended" a cloud VM would be the real answer, not sshrun.

### 13.6 Root cause of the WSL crashes — host RAM exhaustion (definitive, measured)

Repeated attempts to `docker pull` the Lean image in WSL killed the whole VM mid-pull. Ruled out,
with evidence, several wrong theories before finding the real one:

- **Not the CPU / not compatibility** — Lean 4.32.0 runs fine (health OK on both boxes).
- **Not `avid-server`** — it was auto-restarting in WSL each boot, but used only **98 MiB**. Stopped
  it + disabled auto-restart anyway (reversible; image kept).
- **Not the guest swap / not the `.wslconfig` swap theory** — guest swap is present (8 GB) and never
  used; the guest never reached its 8 GB cap.
- **Not the kernel** — standard `6.18.33.2-microsoft-standard-WSL2`, WSL 2.7.11, overlayfs.

**Measured cause (host-side monitor during an active pull):** as the pull inflated `vmmem`
3.1 → 5.2 GB, **host free RAM collapsed 3.9 GB → <1 GB** and stayed pinned ~1 GB for ~40 s, then
Windows/Hyper-V **terminated the VM** (ungraceful → lost unflushed guest writes, hence empty logs).
The guest died because the **host** ran out of RAM, not the guest.

Host RAM budget (15.3 GB total): Chrome ~3.7 GB, Claude Desktop ~2.2 GB, ChatGPT ~1.2 GB, svchost
~1 GB → ~9.6 GB used, ~5.7 GB free. The kit's `import Mathlib` needs ~6.5 GB, which alone exceeds
the free headroom → same crash guaranteed unless host RAM is freed.

### 13.7 Decisions (updated)

- **D009 — The Ryzen/WSL blocker is host RAM, fixable by freeing Windows memory.** Closing Chrome
  (~3.7 GB) + ChatGPT (~1.2 GB) frees ~5 GB → host free ~10–11 GB → WSL can host the ~6.5 GB Mathlib
  working set without killing the VM. Keep WSL `memory=8GB`; do **not** raise it (host is the ceiling).
- **D010 — 15 GB total RAM is marginal for Mathlib.** Viable for **development/testing** with heavy
  apps closed; for **long unattended Part-Two runs** a cloud VM (16–32 GB) remains the robust option.
  This matches the user's original split (dev here, long runs elsewhere).

### 13.8 Open setup tasks (WSL/Ryzen)

- [x] Install Python 3.11 in WSL — done via `uv` (3.11.16) + `~/.pyshim/python3` shim; system python
      untouched.
- [x] Clone private repo into WSL native fs — done at `~/verified-mechanism` (token scrubbed).
- [x] Free host RAM (close Chrome) and complete image pull + health — **2026-08-23**.
- [x] `smoke_test.sh` green with local overrides — **~1 m 48 s**, comparator accepts `p01_linear`.
- [x] REPL agent path verified — `check_file` accepts `linarith` proof in ~9 s warm.
- [x] Root-cause Mathlib thrash under kit `--memory 5g`; local override `LEAN_CONTAINER_MEMORY=8g`
      (patch in `re-takehome-main/src/re_harness/lean.py`, default remains `5g` for judging).
- [x] WSL `.wslconfig` raised to `memory=10GB` (was 8GB) after pull succeeded with headroom.
- [ ] Add OpenRouter key to WSL `.env` (not present yet).
- [ ] Keep Windows tree and WSL clone in sync (WSL clone was still on `86e5ebd` mid-session).
- [ ] Decide on a cloud VM for the heavy Part-Two experiment matrix.

### 13.9 Measured Lean timings on Ryzen/WSL (2026-08-23)

| Operation | Container RAM | Wall |
|---|---|---|
| `import Mathlib` (REPL) | 8g | ~44 s cold |
| `import Mathlib` / check under 5g | 5g | thrash / timeout (150GB+ blkio) |
| smoke comparator `p01_linear` | 8g | ~1 m 48 s total |
| REPL `check_file` warm | 8g | ~9 s |

Image digest unchanged:
`ghcr.io/verifiedmechanisms/re-takehome-lean@sha256:ee48287cd31c0a7df572093a879ed7289c2f01fec6c7af8716c605fc8c670c39`.

### 13.10 Decision

- **D011 — Local Lean containers run with `LEAN_CONTAINER_MEMORY=8g` on this laptop.** Required for
  Mathlib. Do not lower back to 5g for local dev. Judging default stays 5g unless their machines
  differ; if holdout ever OOMs under 5g that is their environment, not ours to "fix" by shipping
  a higher default without measurement on their side. Document the override in the writeup if
  relevant to reproducibility of *our* Part-Two numbers.

---

## 14. Current status

**Project stage:** Phase 0 environment **unblocked**. Ready for key + economic calibration + Phase 1.

No collaboration architecture should yet be considered final. `submission/agent.py` is still the stub.

Immediate objective:

> Put the OpenRouter key in WSL `.env`, sync the WSL clone with the Windows tree, run a 1–2 problem
> economic calibration per model with the shipped baseline, then solo baselines under matched budgets.
> Always export `LEAN_CONTAINER_MEMORY=8g` for local Lean work on this machine.
