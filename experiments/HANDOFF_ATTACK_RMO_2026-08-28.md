# Handoff — attack the last two problems (rmo_2000_2, rmo_2000_3)

**Paste this to bring a fresh chat into context.** Frontier is now **7/9**. Two
problems remain and current evidence says they are a **real capability limit** of the
two fixed models — your job is to decide whether that verdict holds or find the
mechanism that breaks it.

---

## 1. Where we are (2026-08-28)

- **Frontier = 7/9.** Solved: `p01, p03, p05, p06, p10, putnam_2018_a1` **+ `p09_imo1964`**.
- **`p09` was just solved** (6/9 → 7/9) by a **universal** mechanism, nothing hardcoded:
  per-theorem heavy sampling + combine. See §4. This proves the pipeline works.
- **Unsolved: `rmo_2000_2`, `rmo_2000_3`.** Heavy sampling (N=16 each, plan→formalize +
  NearMiss, temp 0.9) produced **0/16 accepted** for both. Unlike p09 (~1/10 per
  theorem), the per-sample accept rate here looks ~0.

## 2. Hard constraints (any idea MUST respect all)

- Two fixed models only via OpenRouter: **Q = `qwen/qwen3.5-flash-02-23`**,
  **G = `openai/gpt-oss-120b`**. **No fine-tuning, no other models.**
- **Universal mechanisms only** — identical behaviour on every input; nothing keyed to a
  problem id or a dev-observed category ("Diophantine ⇒ interval_cases"). Triggers may
  look at the **goal/error shape** (Lean diagnostics), never the problem identity.
- **Lean/Mathlib is the only verifier/tool.** Lean's own `exact?/apply?/simp?/aesop?/
  grind?/#check/#find` are allowed; no web/Loogle/LeanSearch.
- No weakening statements/names; no `sorry`/`admit`/new axioms in a returned file.
  Comparator permits only axioms `propext, Classical.choice, Quot.sound` — **avoid
  `native_decide`** (adds `Lean.ofReduceBool` → comparator rejects even though the REPL
  accepts).
- Budget ≤ $1 and ≤ 8 h per problem. Cost is a non-issue (~$1.5 total spent). Wall time
  is the real limit, but a **~10× parallel dev driver** exists (§5).

## 3. The two cruxes (reason about actual Lean here)

### rmo_2000_2 — cubic Diophantine (single theorem)
```lean
theorem rmo_2000_2 (x y : ℕ) (hx : 0 < x) (hy : 0 < y)
  (h : y ^ 3 = x ^ 3 + 8 * x ^ 2 - 6 * x + 8) : x = 9 ∧ y = 11 := by sorry
```
Human proof: **squeeze** `y` between consecutive cubes — for large `x`,
`(x+1)^3 < y^3 < (x+3)^3`, so `y = x+2`; substitute → a quadratic that pins `x=9`.
Needs `nlinarith` with the **right auxiliary cube terms** + a bounded case check.
Best model verified prefix ever = **2/4** (just a bare case split; the crux never
appears). ℕ truncated subtraction `- 6*x` is a real trap — may need a cast to ℤ.

### rmo_2000_3 — harmonic-weighted sums (single theorem; hardest)
```lean
open Finset
theorem rmo_2000_3 (x : ℕ → ℝ) (hpos : ∀ n, 0 < x n) (hmono : ∀ n, x n ≥ x (n+1))
  (hsq : ∀ N, (Ico 1 (N+1)).sum (fun i => x (i*i) / i) ≤ 1) :
  ∀ k, (Ico 1 (k+1)).sum (fun i => x i / i) ≤ 3 := by sorry
```
Needs **Abel summation / block-grouping**: group `i ∈ [m², (m+1)²)` and bound each
block using the `x(i²)` terms and monotonicity. Best model prefix = **4/5** but that is
only setup (deriving monotonicity); the Abel argument never appears. Real-analysis over
`Finset` — the likeliest genuine ceiling.

## 4. The mechanism that solved p09 (reuse it; understand why it worked)

`re-takehome-main/multisample_combine.py` + arm `experiments_agents/nm_pf.py`
(plan→formalize G/Q + NearMiss rescue). For a problem it: splits into theorems, solves
**each independently across N parallel samples** (shared Lean queue, per-agent budget),
keeps the **best accepted proof per theorem**, **combines** the winners, runs the
comparator. p09 worked because each theorem is independently solvable at ~1/10, and
per-theorem sampling **breaks the conjunction** (both needn't be clean in one run). Two
fixes were load-bearing: NearMiss (`nearmiss.py`, truncate to max verified prefix +
composed finisher) and `_merge_preambles` emitting **all imports first**.

**Why this may not save the rmo problems:** for p09 the per-sample rate was >0; here it
is ~0 at N=16. Scaling N only helps a nonzero rate. So the open question is whether a
**different action interface** raises the rate above zero, not whether more samples help.

## 5. What's already tried — DO NOT re-propose as new (full log: `experiments/IDEAS_AND_RESULTS.md`)

S/R/H baselines, AT (tactic sweep + `grind`), SK (skeleton), BON (best-of-N), PF
(plan→formalize), StateTree v1/v2 (verified proof-state search + `apply?/exact?`
premises), MT (multi-theorem split), SF/MT-SF (sketch-and-fill), NearMiss (truncate +
composed finisher), lemma bank (cross-slot), StepRepair (per-`have` battery repair),
StepRepair+model, and **per-theorem heavy sampling ×16** (this doc). On the two rmo:
**all 0.** The verified-prefix probes show the models produce easy scaffolding and stall
at the ONE hard step; no repair/rescue reached the crux.

## 6. Untested levers with a real mechanistic reason (evaluate, don't assume)

- **HintedCloser (rmo_2000_2, highest EV):** the model proposes only the **hint terms**
  for a fixed strong tactic — `nlinarith [sq_nonneg (y-x-2), (x+1)^3, (x+3)^3, …]` — and
  Lean checks each hint list. Collapses the whole proof to one verified tactic call;
  much lower-dimensional than free-form. Universal (same "propose hints for nlinarith/
  polyrith" procedure on every goal). Kill: 0 goal-state change after ~20 hint batches.
- **Cast-to-ℤ normaliser** before nlinarith (the ℕ subtraction is likely why nlinarith
  never fires on rmo_2000_2).
- **MenuTree / premise-by-type (`#find`)** — Lean builds validated candidate actions;
  the model only selects. Separates "can't write Lean" from "can't find the lemma". More
  relevant to rmo_2000_3's missing Abel lemmas.
- **Representation graph / `suffices` cuts** with an anti-triviality + fillability score
  (fixes sketch-and-fill's two known defects). For rmo_2000_3's block decomposition.
- Honest option: **confirm the ceiling.** If HintedCloser + a cast-normaliser + ~50
  diverse samples still give 0 on rmo_2000_2, and MenuTree menus are infertile on
  rmo_2000_3, that clinches the capability-limit verdict for these two cruxes.

## 7. Substrate + how to run

- Code: `re-takehome-main/experiments_agents/` (arms + `nearmiss.py`, `multitheorem.py`,
  `lemmabank.py`, `sketchfill.py`, `statetree.py`, `leanprobe.py`, `common.py` [battery
  incl. `grind`, integrity gate]). Drivers: `fastdrive.py` (parallel, `--repeat N`),
  `multisample_combine.py` (per-theorem sampling + combine). Probes: `probe_*.py`.
- Runtime: **sshrun** over SSH + tmux (only runtime that survives; WSL/Docker-Desktop
  don't). One Lean container (~8 GB) → **one Lean check at a time**; model calls are
  parallel/cheap. `LEAN_CONTAINER_MEMORY=8g`, `COMPARATOR_TIMEOUT_S=900`, `N_WORKERS=1`.
  Repo on sshrun: `~/Documentos/verified-mechanism/re-takehome-main`; sync by `scp`
  (it can't `git fetch`). Lean **v4.32.0**, Mathlib `81a5d25`.
- Run a heavy sample: `python multisample_combine.py --set sets/mt_sf_hard --id
  rmo_2000_2 --agent experiments_agents.nm_pf:create_agent --n 16`.

## 8. Discipline

Verify against `experiments/IDEAS_AND_RESULTS.md` before calling anything new. Every
proposal ships a first experiment + a kill signal. Distinguish a *capability* limit from
a *harness* limit with a measurable observable (the per-theorem accept rate is the clean
one — it separated p09 from the rmo problems). Don't touch `S_eval`. Comparator is the
sole authority (REPL-accepted ≠ passed — an import-after-open or `native_decide` fools
the REPL but not the build).
