"""Shared R/H targeted-repair agent. H differs only by repair_model."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from re_harness import AgentResult, Problem, Services

from .common import (
    REPAIR_INVARIANTS,
    count_model_calls,
    env_float,
    env_int,
    extract_lean,
    format_messages,
    normalize_diagnostics,
    require_model,
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

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        candidate = problem.challenge
        attempts: list[Attempt] = []
        calls_q = 0
        calls_g = 0
        lean_checks = 0
        last_diag_norm = ""
        stall_count = 0
        diagnostics = ""
        failed_proof = candidate

        for turn in range(1, self.max_propose_turns + 1):
            response = await services.llm.complete(
                model=self.propose_model,
                messages=self._propose_messages(problem, turn=turn),
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            calls_q, calls_g = count_model_calls(self.propose_model, calls_q, calls_g)
            candidate = extract_lean(response.content, fallback=candidate)
            services.checkpoint(
                candidate,
                {
                    "arm": self.arm,
                    "stage": "propose",
                    "turn": turn,
                    "model": self.propose_model,
                },
            )
            check = await services.lean.check_file(candidate)
            lean_checks += 1
            diagnostics = format_messages(check.messages)
            if check.timed_out and not diagnostics:
                diagnostics = "Lean timed out while checking the previous candidate."
            diag_norm = normalize_diagnostics(diagnostics)
            attempts.append(
                Attempt(
                    stage="propose",
                    turn=turn,
                    model=self.propose_model,
                    accepted=check.accepted,
                    timed_out=check.timed_out,
                    message_count=len(check.messages),
                    diagnostics_norm=diag_norm[:500],
                )
            )
            if check.accepted:
                return self._result(
                    candidate,
                    accepted=True,
                    attempts=attempts,
                    calls_q=calls_q,
                    calls_g=calls_g,
                    lean_checks=lean_checks,
                )
            if diag_norm and diag_norm == last_diag_norm:
                stall_count += 1
            else:
                stall_count = 0
            last_diag_norm = diag_norm
            failed_proof = candidate

        for turn in range(1, self.max_repair_turns + 1):
            response = await services.llm.complete(
                model=self.repair_model,
                messages=self._repair_messages(
                    problem,
                    failed_proof=failed_proof,
                    diagnostics=diagnostics,
                    turn=turn,
                    is_last=turn == self.max_repair_turns,
                ),
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            calls_q, calls_g = count_model_calls(self.repair_model, calls_q, calls_g)
            candidate = extract_lean(response.content, fallback=candidate)
            services.checkpoint(
                candidate,
                {
                    "arm": self.arm,
                    "stage": "repair",
                    "turn": turn,
                    "model": self.repair_model,
                },
            )
            check = await services.lean.check_file(candidate)
            lean_checks += 1
            diagnostics = format_messages(check.messages)
            if check.timed_out and not diagnostics:
                diagnostics = "Lean timed out while checking the previous candidate."
            diag_norm = normalize_diagnostics(diagnostics)
            attempts.append(
                Attempt(
                    stage="repair",
                    turn=turn,
                    model=self.repair_model,
                    accepted=check.accepted,
                    timed_out=check.timed_out,
                    message_count=len(check.messages),
                    diagnostics_norm=diag_norm[:500],
                )
            )
            if check.accepted:
                return self._result(
                    candidate,
                    accepted=True,
                    attempts=attempts,
                    calls_q=calls_q,
                    calls_g=calls_g,
                    lean_checks=lean_checks,
                )
            # identical normalized diagnostics twice in a row → no-progress stop
            if diag_norm and diag_norm == last_diag_norm:
                stall_count += 1
                if stall_count >= 1:
                    break
            else:
                stall_count = 0
            last_diag_norm = diag_norm
            failed_proof = candidate

        return self._result(
            candidate,
            accepted=False,
            attempts=attempts,
            calls_q=calls_q,
            calls_g=calls_g,
            lean_checks=lean_checks,
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
        user = "\n".join(
            [
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
                "Previous failed proof:",
                "```lean",
                failed_proof,
                "```",
                "",
                "Exact Lean diagnostics:",
                "```text",
                diagnostics,
                "```",
            ]
        )
        return [
            {"role": "system", "content": "\n".join(instructions)},
            {"role": "user", "content": user},
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
