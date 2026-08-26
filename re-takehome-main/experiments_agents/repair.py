"""Shared R/H targeted-repair agent. H differs only by repair_model.

Hardened per the post-S_dev review (all changes are problem-agnostic / universal):
- best-so-far candidate seed: repair the best candidate seen, not the latest, and
  return the best at the end (never regress an elaborating proof into a parse error
  and then repair the regression);
- integrity gate: a REPL-accepted candidate only counts as success if it still
  declares every theorem/def named in the challenge and uses no sorry/admit/axiom;
- tolerant stall detection: stop after two consecutive non-improving attempts
  (rank-based), not one repeated diagnostic;
- root-diagnostic preservation and explicit extraction-failure signal (see common);
- full per-attempt provenance (hashes, category, integrity, rank, stop reason).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from re_harness import AgentResult, Problem, Services

from .common import (
    REPAIR_INVARIANTS,
    candidate_rank,
    count_model_calls,
    diagnostic_category,
    env_float,
    env_int,
    extract_lean_ex,
    format_messages,
    integrity_check,
    normalize_diagnostics,
    require_model,
    sha16,
)

DEFAULT_MAX_PROPOSE_TURNS = 1
DEFAULT_MAX_REPAIR_TURNS = 3
DEFAULT_MAX_TOKENS = 12000
DEFAULT_TEMPERATURE = 0.2


@dataclass(frozen=True)
class Attempt:
    stage: str  # propose | repair
    turn: int
    model: str
    accepted: bool
    timed_out: bool
    message_count: int
    diagnostics_norm: str
    candidate_hash: str
    parent_hash: str
    extracted_ok: bool
    integrity_ok: bool
    integrity_errors: str
    category: str
    rank: list[int]


@dataclass
class _Assessment:
    diagnostics: str
    integrity_ok: bool
    integrity_errors: list[str]
    rank: list[int]
    category: str


class TargetedRepairAgent:
    """Propose → Lean → repair with structured failure context.

    R: propose_model == repair_model
    H: propose_model != repair_model (only difference)
    """

    def __init__(
        self,
        *,
        arm: str,
        propose_model: str,
        repair_model: str,
        max_propose_turns: int | None = None,
        max_repair_turns: int | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        self.arm = arm
        self.propose_model = require_model(propose_model)
        self.repair_model = require_model(repair_model)
        self.max_propose_turns = (
            max_propose_turns
            if max_propose_turns is not None
            else env_int(
                "REPAIR_MAX_PROPOSE_TURNS",
                DEFAULT_MAX_PROPOSE_TURNS,
                minimum=1,
                maximum=5,
            )
        )
        self.max_repair_turns = (
            max_repair_turns
            if max_repair_turns is not None
            else env_int(
                "REPAIR_MAX_REPAIR_TURNS",
                DEFAULT_MAX_REPAIR_TURNS,
                minimum=0,
                maximum=24,
            )
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else env_int("REPAIR_MAX_TOKENS", DEFAULT_MAX_TOKENS, minimum=1000, maximum=32000)
        )
        self.temperature = (
            temperature
            if temperature is not None
            else env_float(
                "REPAIR_TEMPERATURE", DEFAULT_TEMPERATURE, minimum=0.0, maximum=2.0
            )
        )

    def _assess(self, candidate: str, extracted_ok: bool, challenge: str, check) -> _Assessment:
        diagnostics = format_messages(check.messages)
        if check.timed_out and not diagnostics:
            diagnostics = "Lean timed out while checking the previous candidate."
        integrity_ok, integrity_errors = integrity_check(candidate, challenge)
        error_count = sum(1 for m in check.messages if m.get("severity") == "error")
        rank = candidate_rank(
            accepted=check.accepted,
            integrity_ok=integrity_ok,
            extracted_ok=extracted_ok,
            timed_out=check.timed_out,
            error_count=error_count,
            message_count=len(check.messages),
        )
        return _Assessment(
            diagnostics=diagnostics,
            integrity_ok=integrity_ok,
            integrity_errors=integrity_errors,
            rank=rank,
            category=diagnostic_category(check.messages),
        )

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        challenge = problem.challenge
        candidate = challenge
        attempts: list[Attempt] = []
        calls_q = 0
        calls_g = 0
        lean_checks = 0

        best_candidate = challenge
        best_diagnostics = ""
        best_integrity_errors: list[str] = []
        best_rank: list[int] | None = None
        consecutive_no_improve = 0
        stop_reason = "exhausted"

        plan = [
            ("propose", self.propose_model, t, t == self.max_propose_turns)
            for t in range(1, self.max_propose_turns + 1)
        ] + [
            ("repair", self.repair_model, t, t == self.max_repair_turns)
            for t in range(1, self.max_repair_turns + 1)
        ]

        parent_hash = sha16(challenge)
        for stage, model, turn, is_last in plan:
            if stage == "propose":
                messages = self._propose_messages(problem, turn=turn)
            else:
                messages = self._repair_messages(
                    problem,
                    failed_proof=best_candidate,
                    diagnostics=best_diagnostics,
                    integrity_errors=best_integrity_errors,
                    turn=turn,
                    is_last=is_last,
                )
            response = await services.llm.complete(
                model=model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            calls_q, calls_g = count_model_calls(model, calls_q, calls_g)
            candidate, extracted_ok = extract_lean_ex(response.content, fallback=candidate)
            candidate_hash = sha16(candidate)
            services.checkpoint(
                candidate,
                {"arm": self.arm, "stage": stage, "turn": turn, "model": model},
            )
            check = await services.lean.check_file(candidate)
            lean_checks += 1
            a = self._assess(candidate, extracted_ok, challenge, check)
            attempts.append(
                Attempt(
                    stage=stage,
                    turn=turn,
                    model=model,
                    accepted=check.accepted,
                    timed_out=check.timed_out,
                    message_count=len(check.messages),
                    diagnostics_norm=normalize_diagnostics(a.diagnostics)[:500],
                    candidate_hash=candidate_hash,
                    parent_hash=parent_hash,
                    extracted_ok=extracted_ok,
                    integrity_ok=a.integrity_ok,
                    integrity_errors="; ".join(a.integrity_errors)[:300],
                    category=a.category,
                    rank=a.rank,
                )
            )
            parent_hash = candidate_hash

            improved = best_rank is None or a.rank > best_rank
            if improved:
                best_candidate = candidate
                best_diagnostics = a.diagnostics
                best_integrity_errors = a.integrity_errors
                best_rank = a.rank
                consecutive_no_improve = 0
            else:
                consecutive_no_improve += 1

            # Success only if Lean accepts AND the challenge's declarations are intact.
            if check.accepted and a.integrity_ok:
                return self._result(
                    candidate,
                    accepted=True,
                    attempts=attempts,
                    calls_q=calls_q,
                    calls_g=calls_g,
                    lean_checks=lean_checks,
                    stop_reason="accepted",
                    best_hash=candidate_hash,
                )

            # No-progress stop: two consecutive non-improving repair attempts.
            if stage == "repair" and consecutive_no_improve >= 2:
                stop_reason = "stalled"
                break

        return self._result(
            best_candidate,
            accepted=False,
            attempts=attempts,
            calls_q=calls_q,
            calls_g=calls_g,
            lean_checks=lean_checks,
            stop_reason=stop_reason,
            best_hash=sha16(best_candidate),
        )

    def _result(
        self,
        solution: str,
        *,
        accepted: bool,
        attempts: list[Attempt],
        calls_q: int,
        calls_g: int,
        lean_checks: int,
        stop_reason: str,
        best_hash: str,
    ) -> AgentResult:
        return AgentResult(
            solution,
            {
                "arm": self.arm,
                "protocol": "targeted_repair",
                "propose_model": self.propose_model,
                "repair_model": self.repair_model,
                "max_propose_turns": self.max_propose_turns,
                "max_repair_turns": self.max_repair_turns,
                "accepted_by_repl": accepted,
                "stop_reason": stop_reason,
                "best_hash": best_hash,
                "calls_q": calls_q,
                "calls_g": calls_g,
                "lean_checks": lean_checks,
                "attempts": [asdict(a) for a in attempts],
            },
        )

    def _propose_messages(self, problem: Problem, *, turn: int) -> list[dict[str, str]]:
        system = "\n".join(
            [
                "You are the proposer. Write a complete Lean 4 file using Mathlib.",
                "Return only the complete Lean code, preferably in one ```lean code block.",
                "Preserve the theorem names and statements from the challenge.",
                "Do not use sorry, admit, axioms, or unsafe escapes.",
                "The file must compile as-is.",
            ]
        )
        user = "\n".join(
            [
                f"Problem id: {problem.id}",
                f"Arm: {self.arm}",
                f"Propose turn: {turn}/{self.max_propose_turns}",
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

    def _repair_messages(
        self,
        problem: Problem,
        *,
        failed_proof: str,
        diagnostics: str,
        integrity_errors: list[str],
        turn: int,
        is_last: bool,
    ) -> list[dict[str, str]]:
        instructions = [
            "You are the repairer. Fix the failed Lean proof using the compiler diagnostics.",
            "Return only the complete corrected Lean code, preferably in one ```lean code block.",
            *REPAIR_INVARIANTS,
        ]
        if is_last:
            instructions.append(
                "This is your final repair attempt. Return the best complete Lean file only."
            )
        user_lines = [
            f"Problem id: {problem.id}",
            f"Arm: {self.arm}",
            f"Repair turn: {turn}/{self.max_repair_turns}",
            "",
            "Problem description:",
            problem.description,
            "",
            "Original challenge Lean file:",
            "```lean",
            problem.challenge,
            "```",
            "",
            "Best failed proof so far:",
            "```lean",
            failed_proof,
            "```",
            "",
            "Exact Lean diagnostics:",
            "```text",
            diagnostics,
            "```",
        ]
        if integrity_errors:
            user_lines += [
                "",
                "Integrity violations you MUST fix (restore the exact challenge "
                "declarations and statements — do not rename or weaken them):",
                *[f"- {e}" for e in integrity_errors],
            ]
        return [
            {"role": "system", "content": "\n".join(instructions)},
            {"role": "user", "content": "\n".join(user_lines)},
        ]


def make_repair_agent(
    *,
    arm: str,
    propose_model: str,
    repair_model: str,
) -> TargetedRepairAgent:
    return TargetedRepairAgent(
        arm=arm,
        propose_model=propose_model,
        repair_model=repair_model,
    )
