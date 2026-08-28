"""HintedProver (HP) — universal nlinarith-hint idiom + cast-to-ℤ + goal-fed repair.

Motivation (validated 2026-08-28): a comparator-PASSING proof of `rmo_2000_2` exists
entirely inside the "cast the ℕ hypothesis to ℤ, then discharge polynomial-bound
`have`s with `nlinarith [<square/product hints>]`, squeeze the integer variable between
two cubes, pin it with `omega`" idiom. The free-form proving policy (5 strings + repair)
never emits this idiom, so the frontier stalled at the crux (§2.9). HP changes the
*action interface*, not the sample count: it steers both models to the hint idiom, hands
them the ℤ-cast trigger, and on failure feeds back the exact Lean goal-at-error together
with the model's own maximum Lean-verified prefix, so it extends a solid partial proof
instead of restarting.

Universal: the same system prompt and the same loop apply to every problem — nothing is
keyed to a problem id, an answer, or a dev-observed category. The ℤ-cast is *offered*
(the model decides whether the goal-shape needs it); the nlinarith hints are *authored by
the model*, never by us. On failure the NearMiss composed-finisher rescue is attempted,
exactly as for every other arm. Diversity across samples comes from temperature.
"""

from __future__ import annotations

from re_harness import AgentResult, Problem, Services

from .common import (
    QWEN,
    GPT_OSS,
    count_model_calls,
    extract_lean_ex,
    format_messages,
    integrity_check,
    normalize_diagnostics,
    require_model,
)
from .nearmiss import rescue, split_header_body, _base_prefixes, _reindent

_SYSTEM = (
    "You are an expert Lean 4 + Mathlib proof engineer. Return ONE complete Lean file: "
    "the imports first, then the given theorem verbatim, then a proof after `:= by`. "
    "Never use `sorry`, `admit`, or new axioms; never weaken or rename the statement.\n\n"
    "Prove it with this disciplined idiom (it is what makes hard arithmetic goals close):\n"
    "1. NATURAL-NUMBER SUBTRACTION TRAP: `a - b` over ℕ truncates at 0, so `nlinarith`/"
    "`ring` misbehave. If any hypothesis or the goal contains ℕ subtraction, FIRST prove "
    "the guard `have hnn : b ≤ a := by nlinarith [...]` (or `positivity`/`omega`), then "
    "lift the hypothesis to ℤ with `zify [hnn] at h` and do the real work over ℤ, where "
    "subtraction is exact. Cast small facts with `exact_mod_cast`/`push_cast`.\n"
    "2. POLYNOMIAL HAVES WITH HINTS: introduce intermediate `have` facts that are "
    "polynomial equalities or (strict) inequalities, and close EACH with "
    "`nlinarith [HINTS]`. You choose HINTS: a list of nonnegativity/product witnesses such "
    "as `sq_nonneg (E)`, `mul_nonneg hA hB`, `mul_pos hA hB`, or explicit products "
    "`(A) * (B)` of sign-known factors. Choosing the right squares of DIFFERENCES of the "
    "key quantities, and products of factors whose signs you have proven, is the whole "
    "game — that is the certificate nlinarith needs.\n"
    "3. SQUEEZE AN INTEGER: to show an integer `t` equals a specific value, prove strict "
    "bounds `have : lo < t := by nlinarith [...]` and `have : t < hi := by nlinarith [...]` "
    "with `hi = lo + 2`, then `omega` forces `t = lo + 1`. For `t^k < s^k → t < s` use the "
    "same nlinarith-with-product-hints trick via `by_contra`.\n"
    "4. Split `∧` with `refine ⟨?_, ?_⟩`; a factored product `A * B = 0` gives cases via "
    "`mul_eq_zero`.\n"
    "5. Close leftovers with `omega`, `norm_num`, `positivity`, `ring`, `simp_all`.\n"
    "Return ONLY the Lean file inside a single ```lean code block."
)


def _user_initial(problem: Problem, plan: str) -> str:
    parts = [
        f"Problem id: {problem.id}",
        "",
        "Problem description:",
        problem.description,
        "",
        "Target Lean theorem (prove exactly this; keep imports):",
        "```lean",
        problem.challenge,
        "```",
    ]
    if plan:
        parts += ["", "A correct mathematical plan to formalize:", plan]
    return "\n".join(parts)


def _user_repair(problem: Problem, plan: str, verified_prefix: str, diag: str) -> str:
    parts = [
        "Your previous Lean file did not compile. The Lean diagnostics (errors first, "
        "they show the exact remaining goal state) are:",
        "```",
        diag,
        "```",
    ]
    if verified_prefix:
        parts += [
            "",
            "GOOD NEWS: this leading block of your proof already type-checks in Lean "
            "(every step below elaborated). KEEP it verbatim and only continue AFTER it — "
            "do not rewrite what already works:",
            "```lean",
            verified_prefix,
            "```",
        ]
    parts += [
        "",
        "Fix the FIRST error using the hint idiom (cast ℕ→ℤ over truncated subtraction; "
        "polynomial `have`s closed by `nlinarith [square/product hints]`; squeeze+omega). "
        "Return the ONE complete corrected Lean file in a ```lean block. "
        "Target theorem again:",
        "```lean",
        problem.challenge,
        "```",
    ]
    if plan:
        parts += ["", "Plan to follow:", plan]
    return "\n".join(parts)


async def _max_verified_prefix(services: Services, source: str, *, timeout_s: int) -> str:
    """Largest leading block of the proof body that elaborates (goals stubbed)."""
    sh = split_header_body(source)
    if not sh:
        return ""
    header, body = sh
    best = ""
    for pref in _base_prefixes(body):
        probe = _reindent(header, pref, "all_goals sorry")
        c = await services.lean.check_file(probe, timeout_s=timeout_s)
        if not c.timed_out and not any(m.get("severity") == "error" for m in c.messages):
            best = _reindent(header, pref).rstrip()
        else:
            break
    return best


class HintedProver:
    def __init__(
        self,
        *,
        arm: str,
        prove_model: str,
        planner_model: str | None = None,
        turns: int = 3,
        temperature: float = 0.9,
        max_tokens: int = 4096,
        check_timeout_s: int = 150,
        rescue_timeout_s: int = 75,
        rescue: bool = True,
        rescue_max_errors: int = 4,
    ):
        self.arm = arm
        self.prove_model = require_model(prove_model)
        self.planner_model = require_model(planner_model) if planner_model else None
        self.turns = turns
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.check_timeout_s = check_timeout_s
        self.rescue_timeout_s = rescue_timeout_s
        self.rescue = rescue
        self.rescue_max_errors = rescue_max_errors

    async def _plan(self, problem: Problem, services: Services) -> tuple[str, int, int]:
        if not self.planner_model:
            return "", 0, 0
        sys = (
            "You are a proof strategist. Give a concise, correct step-by-step MATHEMATICAL "
            "plan to prove the target theorem: the key bounds/lemmas, the case or squeeze "
            "structure, and which polynomial identities pin the answer. Do NOT write Lean."
        )
        user = _user_initial(problem, "")
        r = await services.llm.complete(
            model=self.planner_model,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            max_tokens=self.max_tokens, temperature=self.temperature)
        q, g = count_model_calls(self.planner_model, 0, 0)
        return (r.content or "").strip()[:4000], q, g

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        calls_q = calls_g = 0
        plan, q, g = await self._plan(problem, services)
        calls_q += q; calls_g += g

        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _user_initial(problem, plan)},
        ]
        best_source = problem.challenge
        best_errs = 10_000
        best_cand = problem.challenge

        for turn in range(self.turns):
            resp = await services.llm.complete(
                model=self.prove_model, messages=messages,
                max_tokens=self.max_tokens, temperature=self.temperature)
            q, g = count_model_calls(self.prove_model, 0, 0)
            calls_q += q; calls_g += g
            cand, ok = extract_lean_ex(resp.content or "", best_source)
            if ok:
                best_source = cand

            # ONE Lean check per turn (the container is the serial bottleneck).
            check = await services.lean.check_file(cand, timeout_s=self.check_timeout_s)
            services.checkpoint(cand, {"arm": self.arm, "turn": turn})
            if check.accepted and not check.has_sorry and integrity_check(cand, problem.challenge)[0]:
                return AgentResult(cand, self._md(calls_q, calls_g, True, "solved", turn, bool(plan)))

            n_err = sum(1 for m in check.messages if m.get("severity") == "error")
            if ok and n_err < best_errs and not check.timed_out:
                best_errs, best_cand = n_err, cand

            if turn == self.turns - 1:
                break
            # Repair: feed the raw diagnostics back (errors-first already carry the goal
            # state at the failure). No per-turn prefix reconstruction — too many checks.
            diag = format_messages(check.messages)
            messages = [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _user_repair(problem, plan, "", diag)},
            ]

        # ONE NearMiss composed-finisher rescue at the end, only on a genuine near-miss
        # (few residual errors) so the prefix/finisher probing cost is spent wisely.
        if self.rescue and best_errs <= self.rescue_max_errors:
            rescued = await rescue(services, best_cand, timeout_s=self.rescue_timeout_s,
                                   integrity=integrity_check, challenge=problem.challenge)
            if rescued is not None:
                return AgentResult(rescued, self._md(calls_q, calls_g, True, "nearmiss_rescue",
                                                     self.turns, bool(plan), best_errs))
        # return the lowest-error candidate (best near-miss), with its residual error count
        return AgentResult(best_cand, self._md(calls_q, calls_g, False, "exhausted",
                                               self.turns, bool(plan), best_errs))

    def _md(self, q, g, ok, reason, turn, has_plan, residual_errors=0):
        return {
            "arm": self.arm, "protocol": "hinted_prover", "prove_model": self.prove_model,
            "planner_model": self.planner_model or "", "accepted_by_repl": ok,
            "stop_reason": reason, "turns_used": turn, "has_plan": has_plan,
            "residual_errors": int(residual_errors), "calls_q": q, "calls_g": g,
        }


def create_agent():
    # default: GPT-OSS proves directly with the hint idiom (strongest reasoner).
    return HintedProver(arm="HP-G", prove_model=GPT_OSS, turns=3)


def create_g():
    return HintedProver(arm="HP-G", prove_model=GPT_OSS, turns=3)


def create_q():
    return HintedProver(arm="HP-Q", prove_model=QWEN, turns=3)


def create_pf():
    # G plans the mathematics, Q formalizes with the hint idiom.
    return HintedProver(arm="HP-PF", prove_model=QWEN, planner_model=GPT_OSS, turns=3)


def create_gp():
    # G plans and G proves (strongest end-to-end).
    return HintedProver(arm="HP-GP", prove_model=GPT_OSS, planner_model=GPT_OSS, turns=3)


def create_g5():
    # deeper repair budget + hotter sampling for the hardest cruxes.
    return HintedProver(arm="HP-G5", prove_model=GPT_OSS, turns=5, temperature=1.0)


def create_gp5():
    return HintedProver(arm="HP-GP5", prove_model=GPT_OSS, planner_model=GPT_OSS,
                        turns=5, temperature=1.0)
