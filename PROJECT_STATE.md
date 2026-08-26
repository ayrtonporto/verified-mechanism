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

Status: **DONE enough to leave** (2026-08-24). Env + first paid e2e calibration green.

Tasks:

- [x] Read repository documentation / AGENT_API / RULES / baseline.
- [x] Understand Lean invocation + comparator (smoke green).
- [x] WSL image pull + health + smoke + REPL path.
- [x] OpenRouter key in WSL `.env` (gitignored; harness loads it).
- [x] First own paid e2e: Qwen baseline on `p01_linear` → **passed** (see §13.11).
- [ ] Run `scripts/judge_check.sh` (still pending; not blocking research start).
- [ ] Own full solo baselines on all 16 (Phase 2).

Do not modify architecture before finishing broader calibration / solo baselines.

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

### D014 — Frozen coordination plan (2026-08-24)

Accepted. Authoritative detail: `design/COORDINATION_PLAN.md`.

Summary:

- Main score = Lean comparator accepts (Part One). Science = solos vs collab vs **same-model two-role** under matched budgets (Part Two).
- Default stack = draft → Lean → targeted repair → optional cross-model handoff on stall → hard early stop. Optional front door: two drafts, Lean selects.
- Same-model propose/repair is a **required control**, not optional. Cross-model gain in Lean under equal budget is unproven in the literature (see SOTA memo).
- Idea upgrade at most one, and only after numbers: error-type routing and/or ≤4 verified lemmas on semantic stall. No debate, no day-one blackboard, no external RAG.
- Nights measure one arm at a time; days read failures and change at most one thing. Registry + spend plan live under `experiments/` when execution starts.
- SOTA inputs: `design/SOTA_RESEARCH_BRIEF.md`, `design/SOTA_MULTI_MODEL_MATH_MEMO.md`.

### D015 — What “better coordination” means

Accepted.

- Primary: more problems with accepted Lean proofs under caps.
- Secondary: honest causal story (method vs second model vs extra compute).
- Faster/cheaper are constraints and confounders, not the main grade.

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
- [x] OpenRouter key in WSL `.env` only (`~/verified-mechanism/re-takehome-main/.env`, gitignored).
- [x] First paid e2e calibration (Qwen × p01) — **passed** 2026-08-24 (see §13.11).
- [x] Phase 0–1 science layer — **done** 2026-08-25 (see §16).
- [x] Twin calib GPT-OSS S-G × p01 — **passed** 2026-08-25 (see §13.11b).
- [ ] **Windows native Lean path green** — toolchains on D: ready; Docker Desktop blocked by C: free space; hybrid TCP docker not green for REPL (see `WINDOWS_RUNTIME.md`).
- [ ] Keep Windows tree and WSL clone in sync when dual-editing (less critical once Windows runtime is green).
- [ ] Decide on a cloud VM for the heavy Part-Two experiment matrix (optional if Windows native is stable).

### 13.9 Measured Lean timings on Ryzen/WSL (2026-08-23/24)

| Operation | Container RAM | Wall |
|---|---|---|
| `import Mathlib` (REPL) | 8g | ~44 s cold |
| `import Mathlib` / check under 5g | 5g | thrash / timeout (150GB+ blkio) |
| smoke comparator `p01_linear` | 8g | ~1 m 48 s total |
| REPL `check_file` warm | 8g | ~9 s |
| **Paid e2e** Qwen baseline `p01_linear` | 8g | **~192 s** total (~101 s comparator) |

Image digest unchanged:
`ghcr.io/verifiedmechanisms/re-takehome-lean@sha256:ee48287cd31c0a7df572093a879ed7289c2f01fec6c7af8716c605fc8c670c39`.

### 13.10 Decisions

- **D011 — Local Lean containers run with `LEAN_CONTAINER_MEMORY=8g` on this laptop.** Required for
  Mathlib. Do not lower back to 5g for local dev. Judging default stays 5g. Document in writeup if
  relevant to reproducibility of *our* Part-Two numbers. **Before submit:** either keep the env-only
  override (preferred; default remains 5g) or revert the `lean.py` patch and document the local
  recipe only — kit must not silently change judge defaults.
- **D012 — Failures under 5g/180s on this laptop are environment, not problem/repo bugs.** Confirmed
  by e2e green under 8g + 900s comparator timeout with the same baseline and problem.
- **D013 — CLI `--problems` takes a problem-*set* directory (with `manifest.json`), not a single
  problem folder.** For one-problem runs use a temp set (see `run_p01_e2e_clean.sh`).

### 13.11 First paid e2e calibration (2026-08-24)

Canonical successful run (WSL):

```text
~/verified-mechanism/re-takehome-main/outputs/baseline/20260824T040147Z/
```

| Field | Value |
|---|---|
| Condition | baseline `simple_agent`, **Qwen only** |
| Problem set | temp 1-problem set `tmp_p01_only` (`p01_linear`) |
| Result | **passed** `1/1`, comparator.passed=true, timed_out=false |
| Cost | **$0.00017719** (1 LLM call) |
| Wall | **~192 s** (comparator ~101 s) |
| Turns | 1 / max 3; `accepted_by_repl=true` |
| Caps | `VM_BUDGET_USD=1.00`, `VM_TIME_LIMIT_S=1200`, `COMPARATOR_TIMEOUT_S=900`, `LEAN_CONTAINER_MEMORY=8g` |
| Script | `run_p01_e2e_clean.sh` (local helper; not submission surface) |

**Implication for budget planning:** easy problems are sub-millidollar with Qwen+few turns. A full
16-problem solo is still unknown (harder problems + more turns dominate). Next calibration: same
recipe with **GPT-OSS** on p01, then a mid/hard problem, before full solos.

**Earlier incomplete paid attempt** (`20260823T231035Z`): LLM+REPL succeeded (~$0.00023) but
comparator/packaging did not finish cleanly (WSL client cuts / 180s rescores). Prefer the
`20260824T040147Z` run as the calibration reference.

### 13.11b Twin calib — GPT-OSS S-G × p01 (2026-08-25)

Canonical successful run (WSL; Windows tree has a copy under the kit `outputs/`):

```text
re-takehome-main/outputs/s_g/20260825T041102Z/
```

| Field | Value |
|---|---|
| Condition | **S-G** `experiments_agents.s_g:create_agent` (kit baseline loop, GPT-OSS pinned) |
| Problem set | temp 1-problem set `tmp_p01_only` (`p01_linear`) |
| Result | **passed** `1/1`, comparator.passed=true, timed_out=false |
| Cost | **$0.00007538** (1 LLM call; OpenRouter `usage.cost` → `actual_cost_usd`) |
| Wall | **~193 s** (comparator ~101 s) |
| Turns | 1 / max 3; `accepted_by_repl=true`; metadata `arm=S-G`, `calls_g=1`, `lean_checks=1` |
| Caps | same local recipe: 8g container, 900s comparator |
| Script | `run_p01_sg_calib.sh` |

**WSL tooling note (not OOM):** several earlier S-G attempts died after LLM+checkpoint when the
launcher dropped the WSL session (exit 127 / incomplete runs). Free RAM was high (~7–8 GB free).
Root issue = **session lifecycle / quoting**, not Mathlib thrash. Motivates **Windows native runtime**
pivot (§16.3, `WINDOWS_RUNTIME.md`).

### 13.12 Local-only kit note (remember before submit)

Touched under `re-takehome-main/` for local dev only:

- `src/re_harness/lean.py` — reads `LEAN_CONTAINER_MEMORY` (default **still `5g`**).

Do **not** treat this as an architecture change. Before final GitHub submit for grading: confirm
whether to ship the env hook (safe if default unchanged) or restore pristine kit bytes and keep
overrides only in run docs/scripts outside the graded path.

Helpers outside the kit contract (Windows tree and/or WSL home): `do_setup.sh`, `do_smoke.sh`,
`run_p01_e2e_clean.sh`, `repl_smoke.py`, `diag_mathlib_import.sh`, `check_status.py`, etc.

---

## 14. Current status

**Project stage:** Phase 0–1 **done** (2026-08-25). Coordination plan frozen. Science arms
invokable. Twin calib green. **RUNTIME RESOLVED (2026-08-25): run on `sshrun` via SSH+tmux — see §17.**
**Next = freeze split → S_dev solos on `sshrun`.**

- Detail plan: `design/COORDINATION_PLAN.md`
- Builder brief (executed): `design/BUILDER_BRIEF.md`
- SOTA memo: `design/SOTA_MULTI_MODEL_MATH_MEMO.md` (and root copy if present)
- Experiment index: `experiments/REGISTRY.md`, `SPEND_PLAN.md`, `SPLIT.md` (**unset**),
  `BASELINE_SEMANTICS.md`, `tables/master_matrix.md`, `RUNBOOK.md`
- Arms: `re-takehome-main/experiments_agents/` (`s_q` `s_g` `r_q` `r_g` `h_qg` `h_gq`)
- `submission/agent.py` still stub (no final adaptive scorer)
- Remote: `https://github.com/ayrtonporto/verified-mechanism`

**Runtime recipe — WSL fallback (proven):**

```bash
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900
export PYTHONPATH="$HOME/verified-mechanism/re-takehome-main${PYTHONPATH:+:$PYTHONPATH}"
cd ~/verified-mechanism/re-takehome-main
# Keep session attached for full job wall time
```

**Runtime recipe — PRODUCTION is now `sshrun` via SSH+tmux (see §17).** WSL/Windows-native
recipes below/above are superseded (WSL session-kill; Desktop engine crash on Lean image).

Immediate objective for the next session:

> 1) Freeze `S_dev`/`S_eval` (SPLIT.md still unset).  
> 2) Run S-Q and S-G on S_dev **on `sshrun`, in tmux, one arm at a time**; log to REGISTRY; then R then H.  
> 3) `git pull` on sshrun first to sync any new arm scripts; adapt arm scripts to sshrun paths (§17).  
> No blackboard/debate. No large matrix without SPEND_PLAN + OK.

---

## 15. Frozen plan snapshot (2026-08-24/25)

Full text: **`design/COORDINATION_PLAN.md`**. Do not contradict it in chat-only decisions; edit the file.

| Piece | Choice |
|---|---|
| Submit goal | Max comparator passes under $1 / 8h; simple design |
| Science goal | Per-problem S / R / H; Solo Union derived; confounds logged |
| Arms | **S-Q, S-G, R-Q, R-G, H-QG, H-GQ** (names in plan) |
| S semantics | Kit `simple_agent` multi-turn Lean loop — **not** silent R |
| R semantics | Explicit propose/repair + failed proof + diagnostics + invariants |
| H semantics | Same as R; only repair model id changes |
| Optional later | Error routing; dual draft; ≤4 lemmas after data |
| Rejected for now | Debate, day-one blackboard, RAG, huge search |
| Ops | Night = one arm; registry + spend; pilot caps proposed turns S=8, R/H=1+3 |
| Next concrete | Windows smoke → freeze split → S_dev solos |

---

## 16. Phase 0–1 delivery + Windows pivot (2026-08-25)

### 16.1 Delivered

- `experiments/*` human layer (registry, spend, split placeholder, baseline semantics, matrix).
- `re-takehome-main/experiments_agents/*` — six factories via `--agent module:factory`.
- Cost path verified in kit: OpenRouter `usage.cost` → events → `budget.spent_usd` / summary.
- Calibs: CAL-Q-p01 (prior) + CAL-G-p01 (this block); spend ~$0.00025.
- Docs: `HANDOFF.md`, `WINDOWS_RUNTIME.md`, this section.

### 16.2 Decisions

- **D014 — Experimental arm IDs are S/R/H** as in `design/COORDINATION_PLAN.md` (not B1/B2/A/C labels in code).
- **D015 — S must remain baseline-faithful**; R is explicit targeted repair; H = R + other repair model.
- **D016 — Prefer Windows native runtime for long paid jobs** after WSL session-kill pain; WSL stays fallback until/unless Windows smoke fails. Not motivated by OOM on the failed S-G attempts.
- **D017 — No full matrix / no final adaptive agent** until split frozen and core S→R→H measured.

### 16.3 Windows migration checklist

See **`WINDOWS_RUNTIME.md`**. Minimum proof: Docker Desktop up, Windows venv, `.env` present
(gitignored), one p01 pass with `actual_cost_usd` logged, REGISTRY row `*-win`.

### 16.4 Spend snapshot

| Item | USD |
|---|---|
| Lab key hard cap | ~50 |
| Logged calib (Q+G p01) | ~0.00025 |
| Phase 0–1 soft cap | ≤0.05 (met) |
| Reserve final/writeup | 20–30% untouched |

---

## 17. RUNTIME RESOLVED — `sshrun` via SSH + tmux (2026-08-25)

**Supersedes the WSL-fallback / Windows-native hunt (D016, §13–16).** This is where all paid Lean
runs happen from now on.

### 17.1 Where and why

**Where:** the always-on Linux box **`sshrun`**, over SSH, with every long job launched **inside `tmux`**.

**Why (measured):**

- **WSL is out — session-kill (the real "WSL se muere a mitad" bug).** When an agent/tool launches a
  WSL job, the WSL VM tears down as soon as the launching `wsl.exe` client disconnects → the job dies
  mid-run **with free RAM (not OOM)**. Reproduced repeatedly; `nohup`/`setsid`/a persistent anchor
  client did **not** save it. Symptoms: exit 127 / `0x80072746`, empty logs (ungraceful kill),
  missing `summary.json`.
- **Windows-native Docker Desktop is out** — engine crashes loading the large Lean image on this
  15 GB laptop (§ Runtime truth).
- **`sshrun` over SSH + tmux works** — jobs **survive client disconnect**. Proven: a 28-min smoke and
  a full paid p01 both ran to completion while the SSH client came and went. This is the reliable path.
- **`sshrun` is slow (AMD A4-3300, 2011, 2 cores) but that is fine:** the 8 h/problem cap is ~100×
  the ~5-min p01 wall, so slowness does **not** cause false timeouts → the science stays valid. It
  only costs throughput (matrix = one overnight unattended tmux run, not days). No cloud (no budget).

### 17.2 `sshrun` facts (for a fresh session)

- Access: `ssh usuario@sshrun` (Tailscale; key auth works; passwordless sudo).
- Repo: `~/Documentos/verified-mechanism` (git; `git pull` needs a token — use `gh auth token` on the
  Windows side and pull `https://x-access-token:<TOKEN>@github.com/ayrtonporto/verified-mechanism.git`).
- Kit: `~/Documentos/verified-mechanism/re-takehome-main`; `.venv` OK; **system python 3.12** (no
  pyshim needed, unlike WSL).
- Image: `ghcr.io/verifiedmechanisms/re-takehome-lean@sha256:ee48287c…` pulled; `health` OK.
- `.env` present (key copied from WSL, len 73, `sk-or-`), `N_WORKERS=1`, `VM_BUDGET_USD=1.00`,
  `VM_TIME_LIMIT_S=28800`.
- `tmux` 3.4 installed.
- **Disk was the trap:** btrfs + hidden **Timeshift snapshots** ate ~30 GB invisible to `du`. Deleted
  the 2 old snapshots (`timeshift --delete`) → ~35 GB free; kept today's. avid/babelbench images
  untouched (protected). Watch disk before big pulls.

### 17.3 Validated run — p01 Qwen baseline (2026-08-25)

`passed 1/1`, `actual_cost_usd 0.00017459`, wall **~4.7 min** (comparator ~2.6 min), 1 turn, 1 LLM
call. Artifacts: `re-takehome-main/outputs/baseline/<timestamp>/`.

### 17.4 Production run pattern

```bash
# Adapt an arm/run script from WSL paths to sshrun paths (once):
#   /home/ayrton/verified-mechanism      -> /home/usuario/Documentos/verified-mechanism
#   drop the "/home/ayrton/.pyshim:/home/ayrton/.local/bin:" PATH prefix (sshrun has py3.12)
ssh usuario@sshrun 'cd ~/Documentos/verified-mechanism && \
  sed -e "s#/home/ayrton/verified-mechanism#/home/usuario/Documentos/verified-mechanism#g" \
      -e "s#/home/ayrton/\.pyshim:/home/ayrton/\.local/bin:##g" \
      run_p01_e2e_clean.sh > run_p01_sshrun.sh'

# Launch inside tmux so it survives disconnect; poll the log for a DONE marker:
ssh usuario@sshrun 'cd ~/Documentos/verified-mechanism && \
  tmux new-session -d -s p01 "PYTHONUNBUFFERED=1 bash run_p01_sshrun.sh; echo DONE_\$? >> run_p01_e2e_clean.log"'
```

Env recipe (already in the arm scripts): `LEAN_CONTAINER_MEMORY=8g`, `COMPARATOR_TIMEOUT_S=900`,
`LEAN_CHECK_TIMEOUT_S=300`, `N_WORKERS=1`. Arm scripts live at repo root
(`run_p01_e2e_clean.sh` = S-Q baseline; `run_p01_sg_calib.sh` = S-G via
`experiments_agents.s_g:create_agent`); adapt each the same way.

### 17.5 Decisions

- **D018 — Production runtime = `sshrun` over SSH + tmux.** Supersedes **D016** (Windows-native). WSL
  abandoned for runs (session-kill); kept only for local edits. Desktop rejected (engine crash). No cloud.
- **D019 — `sshrun` slowness is acceptable** (8 h cap ≫ ~5-min p01 → no false timeouts). Matrix runs as
  an overnight unattended tmux job, one arm at a time.

### 17.6 Next action (superseded by §18)

1. `git pull` on `sshrun` to sync latest arm scripts.
2. Freeze `S_dev`/`S_eval` (`experiments/SPLIT.md` still unset).
3. Adapt + run **S-Q** and **S-G** on `S_dev` on `sshrun`, in tmux, one arm at a time; log rows in
   `experiments/REGISTRY.md`. Then **R**, then **H**. Respect `SPEND_PLAN.md`; no full matrix without OK.

## 18. S_dev matrix complete + kit rate-limit fix (2026-08-26)

### 18.1 Split accepted
`experiments/SPLIT.md` **accepted** by user (was `proposed`). Membership locked;
`S_eval` (7 ids) remains an untouched holdout. Runnable sets materialized at
`re-takehome-main/sets/{calib,S_dev,S_eval}` (commit `f5d84e8`).

### 18.2 Kit rate-limit fix adopted
Launching S-G hit **HTTP 429** on `openai/gpt-oss-120b` (OpenRouter shared pool,
provider AkashML). Maintainer shipped upstream fix `8739a10` ("Handle provider
rate limits without closing the budget ledger"); we adopted it into the vendored
kit as `7baca49` by copying the four touched files (`src/re_harness/llm.py`,
`RULES.md`, `docs/AGENT_API.md`, `tests/test_llm.py`), which were pristine at
upstream `f7109de`. Net functional change in `llm.py`:
- `provider.allow_fallbacks` **False → True**: OpenRouter may reroute a busy-
  provider request to another provider of the **same** model (model fallback still
  off; `require_parameters` + `max_price` ceiling unchanged). Probe: rerouted
  AkashML → CoreWeave, 0 errors.
- 429 no longer marks the budget ledger "unknown"; releases the reservation or
  settles reported cost (`_coerce_cost`/`_reported_cost`).
Our two local kit patches were **preserved** (not reverted): `artifacts.py`
`os.fchmod` Windows guard, `lean.py` `LEAN_CONTAINER_MEMORY` override. sshrun's
kit updated by `scp` (it can't `git fetch` — no creds).

### 18.3 Results (fixed kit, S_dev, 6 arms, 0×429)
| Arm | pass/9 | REGISTRY | notes |
|-----|:-----:|----------|-------|
| S-Q | 3 | Mx-SQ-Sdev | p01,p03,p06 |
| S-G | 4 | Mx-SG-Sdev | p01,p03,p05,putnam_2018_a1 |
| Union(S) | 5 | (derived) | S-Q ∨ S-G |
| R-Q | 4 | Mx-RQ-Sdev | +p10 vs S-Q |
| R-G | 5 | Mx-RG-Sdev | +p10 vs S-G; best single arm |
| H-QG | 4 | Mx-HQG-Sdev | Q propose → G repair |
| H-GQ | 3 | Mx-HGQ-Sdev | G propose → Q repair; **lost p05** |

Per-problem grid in `experiments/tables/master_matrix.md`. Spend this matrix
≈ $0.333; cumulative ≈ $0.41. Never solved by any arm: `p09_imo1964`,
`rmo_2000_2`, `rmo_2000_3`. Any-arm union = 6/9.

### 18.4 Reading
- **Proposer model dominates.** `p06` = Qwen-propose only; `p05` = GPT-OSS only.
- **Repair adds a thin, same-model margin.** Only `p10` is unlocked by repair, and
  only by R-Q/R-G — in 1+3 turns that the S baseline's 8 turns don't reach
  (structured diagnostic repair is more turn-efficient).
- **Handoff (cross-model repair) is not free.** H-GQ lost `p05` that same-model
  R-G kept → the repairer works best on its own model's failure mode.
- **Model complementarity is the biggest lever** (Union(S)=5 ≥ every single arm)
  → the final `submission/agent.py` should favor **adaptive model choice / union**
  over deeper repair.
- **Confounder to freeze/document:** S uses 8 turns, R/H use propose=1+repair=3=4;
  matched axis was **$**, not turns.

### 18.5 Next action (a fresh chat starts here)
1. Iterate on `S_dev` only (allowed); target the repair margin + model-choice lever.
2. Freeze prompts/caps/routing/arm code (record turn budgets) **before** `S_eval`.
3. Run each frozen arm **once** on `S_eval` (Phase 6); log `Ev-*-Seval`.
4. Build adaptive `submission/agent.py` (still a stub).
Driver/status scripts on sshrun: `run_matrix_sdev.sh`, `check.sh`.
