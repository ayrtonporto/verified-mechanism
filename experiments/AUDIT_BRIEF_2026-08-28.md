# Audit brief — independent review of the re-takehome repo (2026-08-28)

**Purpose.** You are an independent auditor. Answer the four premises below with
**evidence and exact commands**, not opinion. Be adversarial: the point is to catch
integrity, scope, and universality problems *before* submission (deadline **Aug 30 AoE**).
Do not take this document's own "preliminary read" as ground truth — verify it.

**Repo layout you are auditing.**
- Kit (provided, "do not need changes"): `re-takehome-main/src/re_harness/`,
  `re-takehome-main/RULES.md`, `re-takehome-main/docs/AGENT_API.md`,
  `re-takehome-main/scripts/`, the Lean comparator (Docker image), `submission/agent.py`
  (the graded entry point), `sample-problems/`.
- Our work (allowed): `re-takehome-main/experiments_agents/*` (applicant arms),
  dev drivers (`fastdrive.py`, `multisample_combine.py`, `probe_*.py`), and the docs
  under `experiments/` + `PROJECT_STATE.md`.
- Task spec of record: `take-home.md` (mirror of `research-engineer-take-home.pdf`) and
  `re-takehome-main/RULES.md`.

The graded deliverable is **`re-takehome-main/submission/agent.py`**: the judge clones the
repo and runs *that* agent on a private holdout (~a dozen problems, same format as
`sample-problems`, difficulty varies), 1 point per Lean-comparator-accepted proof, hard
caps **$1 and 8 h wall-clock per problem**. The 9-problem dev set is a *test bench*, not
the deliverable.

---

## Premise 1 — Was the original (kit) repo modified?

**What to check.** Diff every kit file against the initial snapshot and against upstream.

```bash
cd "<repo root>"
FIRST=$(git rev-list --max-parents=0 HEAD | tail -1)   # 86e5ebd "initial snapshot"
# real (non-whitespace) changes to kit files only:
git diff -w --stat "$FIRST" HEAD -- \
  re-takehome-main/src re-takehome-main/RULES.md re-takehome-main/docs/AGENT_API.md \
  re-takehome-main/scripts re-takehome-main/submission
# full semantic diffs of the integrity-critical files:
git diff -w "$FIRST" HEAD -- re-takehome-main/src/re_harness/lean.py     # comparator path
git diff -w "$FIRST" HEAD -- re-takehome-main/src/re_harness/llm.py      # model/endpoint gate
git diff -w "$FIRST" HEAD -- re-takehome-main/src/re_harness/runner.py
```

**Preliminary read (verify, don't trust):**
- `src/re_harness/lean.py` (+16): the only change is a `_container_memory()` helper that
  reads `LEAN_CONTAINER_MEMORY` and **defaults to the kit's `5g`**; the hardened
  `docker run` flags (`--network`, `--user 65532`, `--cap-drop=ALL`, `no-new-privileges`,
  pids/tmpfs) are unchanged. Docstring asserts "judging uses the default." → **benign IF
  the judge does not set that env var.** Auditor: confirm the comparator invocation and
  permitted-axioms list (`propext, Classical.choice, Quot.sound`) are untouched.
- `RULES.md` (+8) and `docs/AGENT_API.md` (+13): the added text ("harness may allow
  OpenRouter to use a different provider…", rate-limit/budget-ledger wording) **matches
  the newer upstream wording in `take-home.md`/the PDF** → looks like a sync to a newer
  kit, not a self-serving rule edit. Auditor: confirm against upstream
  `github.com/VerifiedMechanisms/re-takehome` `RULES.md`/`AGENT_API.md` at the pinned
  Mathlib rev. **A modified `RULES.md` is a red flag by default — clear it explicitly.**
- `src/re_harness/llm.py` (+54): **not yet characterized here — audit it.** It enforces
  the two-model / openrouter-only policy and the budget ledger. Confirm no relaxation of
  `ALLOWED_MODELS`, the `provider`/`max_price` gate, or the per-problem budget accounting.
- `runner.py` (+10), `artifacts.py` (+4): small; characterize.
- **Runtime drift:** the execution host (`sshrun`) has *uncommitted* local edits
  (`git status` there shows `M src/re_harness/llm.py`, `M experiments_agents/common.py`,
  `M experiments_agents/repair.py`, `M tests/test_llm.py`, `M RULES.md`). These are NOT in
  git and will NOT ship. Confirm the graded path depends only on committed, upstream-equal
  kit code. **Reconcile sshrun ↔ committed tree** (`scp` the committed files or re-diff).

**Verdict to produce:** *(a) kit modified: yes/no per file; (b) any change that could
affect grading or relax a rule: yes/no with the diff hunk.*

---

## Premise 2 — Is it following what `research-engineer-take-home.pdf` requires?

**Requirements (from the PDF / RULES):** (i) two fixed models only
(`qwen/qwen3.5-flash-02-23`, `openai/gpt-oss-120b`), no variant suffixes, only
`openrouter.ai`; (ii) Part One: a **coordination layer in `submission/agent.py`** turning
each problem folder into a comparator-accepted Lean file with the statement unchanged;
(iii) Part Two: a **scientific comparison** of Qwen-solo vs GPT-OSS-solo vs collaboration,
per-problem, with transcripts; (iv) run `scripts/judge_check.sh` before submitting; (v) a
1–10 page writeup (PDF).

**What to check.**
```bash
sed -n '1,40p' re-takehome-main/submission/agent.py       # is it implemented?
bash re-takehome-main/scripts/judge_check.sh              # does it pass?
ls re-takehome-main/submission/ docs/AGENT_API.md
grep -rn "ALLOWED_MODELS\|qwen3.5-flash\|gpt-oss-120b" re-takehome-main/src/re_harness/models.py
# Part Two evidence:
ls experiments/ | grep -iE "solo|matrix|ablation|EXPERIMENT_S"
```

**Preliminary read (verify):**
- 🔴 **`submission/agent.py` is still the stub — `solve()` raises `NotImplementedError`.**
  The graded artifact is **empty**; as of now the holdout score is **0**, independent of
  the 7/9 dev reachability. This is the single most important finding. All working
  mechanisms live in `experiments_agents/` and dev drivers and are **not wired into the
  submission**. Confirm and rank this #1.
- Part Two (collaboration science) has substantial dev evidence
  (`experiments/EXPERIMENT_S_*`, per-problem grid in `IDEAS_AND_RESULTS.md §2`), but check
  it actually reports **Qwen-solo / GPT-OSS-solo / collab** per-problem with transcripts,
  not just aggregate arm scores.
- `scripts/judge_check.sh`: confirm it runs and what it fails on today.

**Verdict to produce:** *per requirement (i)-(v): met / partial / missing, with the check
that shows it.*

---

## Premise 3 — Is the attack universal (no per-problem / per-category keying)?

**Rule:** mechanisms must behave identically on every input. Triggers may inspect the
**goal/error shape** (Lean diagnostics) but never the problem id or a dev-observed
category ("this one is Diophantine ⇒ use interval_cases"). No hardcoded answers; no proof
smuggled in from a dev solve. Comparator-permitted axioms only (avoid `native_decide` —
it adds `Lean.ofReduceBool` and the comparator rejects it even when the REPL accepts).

**What to check.**
```bash
# any routing on problem identity / dev ids?
grep -rniE "rmo_2000|p09|imo1964|putnam|if .*problem.id|== *\"p0" \
  re-takehome-main/submission re-takehome-main/experiments_agents
# hardcoded answers or vendored dev proofs in the submission path:
grep -rniE "x = 9|y = 11|native_decide" re-takehome-main/submission
# reachability probes must stay OUT of the graded path:
ls experiments/reachability/    # hand-built proofs live here — they are PROBES, not submission
```

**Preliminary read (verify):**
- The arms (`nm_pf`, `hintedprover`, `multitheorem`, `nearmiss`, `sketchfill`,
  `lemmabank`) are written to be problem-agnostic (prompt + fixed tactic battery + goal-
  shape triggers). Confirm none branch on `problem.id`.
- ⚠️ **`experiments/reachability/rmo_2000_2_reachable.lean`** is a hand-built,
  problem-specific proof used to establish that a comparator-passing proof *exists* inside
  the nlinarith-hint interface (it PASSES the comparator). It is a **reachability probe**,
  legitimate as evidence, **but must never be pasted into `submission/agent.py` or keyed
  to the id** — that would be overfitting and invalid on the holdout. Confirm it is not in
  the submission path.
- New arm `experiments_agents/hintedprover.py`: audit that its system prompt teaches a
  *universal idiom* (cast ℕ→ℤ on truncated subtraction; polynomial `have`s closed by
  `nlinarith [hints]`; squeeze+omega) with **no rmo-specific numbers**.

**Verdict to produce:** *is any mechanism keyed to a problem/category? Is any dev-derived
proof reachable from the submission? yes/no with grep evidence.*

---

## Premise 4 — Are we on track?

**Frame it against the Aug 30 deadline and the two parts.**

**Preliminary read (verify):**
- **Science / understanding:** strong. Dev frontier 7/9 by universal mechanisms; a clean
  harness-limit vs capability-limit separation (p09 solved by scale; rmo pair now shown
  *reachable* for #2). Good Part-Two material.
- **Deliverable:** 🔴 **behind.** The graded `submission/agent.py` is unimplemented, so the
  most valuable next work is **not** more dev proofs but **wiring a universal agent** that
  the judge can run. Recommended design: a **budget-aware escalation ladder** (cheap →
  aggressive, stop when the REPL accepts + integrity holds), the verifier itself acting as
  the difficulty classifier — no problem-specific routing. Tiers, cheap→dear:
  0) zero-model tactic sweep (battery incl. `grind`);
  1) plan→formalize best-of-small-N;
  2) HintedProver idiom + NearMiss rescue, multi-theorem split;
  3) heavy per-theorem sampling (both models, high temp) + NearMiss/lemma-bank;
  4) MenuTree / premise-by-type + `suffices` cuts for the hardest.
  Escalate while `$ < $1` and `time < 8h` remain. This uses the ample budget headroom
  (~$1.5 spent of $50; per-problem model cost is cents) and the full time cap, instead of
  optimizing token-efficiency we were not asked to optimize.
- **Risk:** time. One Lean container serialises all checks (~30–40 s each); an over-eager
  ladder can blow the 8 h wall cap on a single problem via too many probes. Budget Lean
  checks explicitly (cap checks/tier), not just dollars.

**Verdict to produce:** *on track for a passing submission by Aug 30? What is the critical
path? (expected: implement + judge_check the universal ladder agent; freeze S_eval run.)*

---

## How to report
Return a short markdown verdict: one paragraph per premise (met/partial/missing + the
command output that proves it), then a ranked risk list. Flag anything that could **zero**
the submission (empty agent, a rule-relaxing kit edit, a smuggled hardcoded proof,
`native_decide`) at the top.
