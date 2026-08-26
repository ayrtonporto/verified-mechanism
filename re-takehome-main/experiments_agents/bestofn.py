"""Idea C — diverse best-of-N sampling (universal).

N independent complete proposals (no repair), each nudged by a rotating hint from
a FIXED universal strategy menu, at higher temperature; take the first Lean-
accepted + integrity-preserving one. A zero-model-cost tactic sweep runs first.

This is the clean "broaden the search" counterpart to repair: same call budget
spent on independent, strategy-diverse attempts rather than sequential edits. The
strategy menu is identical for every problem — nothing routes on problem identity.
"""

from __future__ import annotations

from re_harness import AgentResult, Problem, Services

from .common import (
    SWEEP_CHECK_TIMEOUT_S,
    TACTIC_MENU,
    candidate_rank,
    count_model_calls,
    diagnostic_category,
    env_float,
    env_int,
    extract_lean_ex,
    integrity_check,
    require_model,
    sha16,
    tactic_sweep_variants,
)

STRATEGIES: tuple[str, ...] = (
    "Close it directly with a Mathlib automation tactic (omega/decide/norm_num/simp_all/nlinarith/aesop).",
    "Prove it by induction on a natural-number parameter.",
    "Reformulate before proving: cast types or move to an equivalent statement (e.g. work in ZMod).",
    "Split into cases (by parity, by a modular residue, or by the disjuncts of the goal).",
    "Introduce intermediate `have` lemmas, prove each, then combine them.",
    "Use a `calc` chain for the main equality/inequality.",
)


class BestOfNAgent:
    def __init__(
        self,
        *,
        arm: str,
        model: str,
        n: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        self.arm = arm
        self.model = require_model(model)
        self.n = n if n is not None else env_int("BON_N", 8, minimum=1, maximum=24)
        self.temperature = (
            temperature
            if temperature is not None
            else env_float("BON_TEMPERATURE", 0.8, minimum=0.0, maximum=2.0)
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else env_int("BON_MAX_TOKENS", 12000, minimum=1000, maximum=32000)
        )

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        challenge = problem.challenge
        calls_q = calls_g = lean_checks = 0
        attempts: list[dict] = []
        best_candidate = challenge
        best_rank: list[int] | None = None

        for tactic, variant in tactic_sweep_variants(challenge):
            services.checkpoint(variant, {"arm": self.arm, "stage": "tactic_sweep", "tactic": tactic})
            check = await services.lean.check_file(variant, timeout_s=SWEEP_CHECK_TIMEOUT_S)
            lean_checks += 1
            if check.accepted and integrity_check(variant, challenge)[0]:
                return self._result(variant, True, "tactic_sweep", attempts, calls_q, calls_g, lean_checks, winning_tactic=tactic)

        for i in range(self.n):
            strategy = STRATEGIES[i % len(STRATEGIES)]
            response = await services.llm.complete(
                model=self.model,
                messages=self._messages(problem, strategy, i + 1),
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            calls_q, calls_g = count_model_calls(self.model, calls_q, calls_g)
            candidate, extracted_ok = extract_lean_ex(response.content, fallback=challenge)
            services.checkpoint(candidate, {"arm": self.arm, "stage": "sample", "turn": i + 1})
            check = await services.lean.check_file(candidate)
            lean_checks += 1
            integ_ok = integrity_check(candidate, challenge)[0]
            error_count = sum(1 for m in check.messages if m.get("severity") == "error")
            rank = candidate_rank(
                accepted=check.accepted, integrity_ok=integ_ok, extracted_ok=extracted_ok,
                timed_out=check.timed_out, error_count=error_count, message_count=len(check.messages),
            )
            attempts.append({
                "turn": i + 1, "strategy": strategy, "accepted": check.accepted,
                "integrity_ok": integ_ok, "extracted_ok": extracted_ok,
                "category": diagnostic_category(check.messages),
                "candidate_hash": sha16(candidate), "rank": rank,
            })
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best_candidate = candidate
            if check.accepted and integ_ok:
                return self._result(candidate, True, "accepted", attempts, calls_q, calls_g, lean_checks, winning_sample=i + 1)

        return self._result(best_candidate, False, "exhausted", attempts, calls_q, calls_g, lean_checks)

    def _result(self, solution, accepted, stop_reason, attempts, calls_q, calls_g, lean_checks, **extra):
        return AgentResult(
            solution,
            {
                "arm": self.arm, "protocol": "best_of_n", "model": self.model,
                "n": self.n, "temperature": self.temperature,
                "accepted_by_repl": accepted, "stop_reason": stop_reason,
                "calls_q": calls_q, "calls_g": calls_g, "lean_checks": lean_checks,
                "attempts": attempts, **extra,
            },
        )

    def _messages(self, problem: Problem, strategy: str, turn: int) -> list[dict[str, str]]:
        system = "\n".join(
            [
                "You are writing a complete Lean 4 file using Mathlib.",
                "Return only the complete Lean code in one ```lean code block.",
                "Preserve the theorem names and statements from the challenge.",
                "Do not use sorry, admit, axioms, or unsafe escapes.",
                "The file must compile as-is.",
                TACTIC_MENU,
            ]
        )
        user = "\n".join(
            [
                f"Problem id: {problem.id}",
                f"Arm: {self.arm}",
                f"Independent attempt: {turn}/{self.n}",
                f"Strategy to try this attempt: {strategy}",
                "",
                "Problem description:",
                problem.description,
                "",
                "Challenge Lean file:",
                "```lean",
                problem.challenge,
                "```",
            ]
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
