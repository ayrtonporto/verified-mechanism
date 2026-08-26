"""Idea A — auto-tactics arm (universal).

A hardened targeted-repair agent augmented with, for *every* problem:
1. a zero-model-cost **finisher sweep**: before spending any model call, try to
   close the challenge with each tactic in the fixed `CLOSING_TACTICS` battery
   (Mathlib decision procedures / automation). If Lean accepts one and integrity
   holds, we win for free;
2. a **tactic menu** appended to the proposer/repairer prompts, so the models
   reach for `omega`/`decide`/`norm_num`/`nlinarith`/`aesop`/… instead of hand
   proofs.

Both are problem-agnostic: the same battery and the same menu apply to any
problem. Nothing here routes on problem identity or category.
"""

from __future__ import annotations

from re_harness import AgentResult, Problem, Services

from .common import (
    TACTIC_MENU,
    integrity_check,
    tactic_sweep_variants,
)
from .repair import TargetedRepairAgent


class TacticAugmentedRepairAgent(TargetedRepairAgent):
    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        challenge = problem.challenge
        sweep_checks = 0
        for tactic, variant in tactic_sweep_variants(challenge):
            services.checkpoint(
                variant,
                {"arm": self.arm, "stage": "tactic_sweep", "tactic": tactic},
            )
            check = await services.lean.check_file(variant)
            sweep_checks += 1
            if check.accepted and integrity_check(variant, challenge)[0]:
                return AgentResult(
                    variant,
                    {
                        "arm": self.arm,
                        "protocol": "tactic_sweep",
                        "propose_model": self.propose_model,
                        "repair_model": self.repair_model,
                        "accepted_by_repl": True,
                        "stop_reason": "tactic_sweep",
                        "winning_tactic": tactic,
                        "calls_q": 0,
                        "calls_g": 0,
                        "lean_checks": sweep_checks,
                        "tactic_sweep_checks": sweep_checks,
                        "attempts": [],
                    },
                )

        # No single tactic closed it → hardened propose/repair with the menu.
        result = await super().solve(problem, services)
        merged = dict(result.metadata)
        merged["protocol"] = "tactic_augmented_repair"
        merged["tactic_sweep_checks"] = sweep_checks
        merged["lean_checks"] = int(merged.get("lean_checks", 0)) + sweep_checks
        return AgentResult(result.solution, merged)

    def _propose_messages(self, problem: Problem, *, turn: int) -> list[dict[str, str]]:
        messages = super()._propose_messages(problem, turn=turn)
        messages[0]["content"] += "\n" + TACTIC_MENU
        return messages

    def _repair_messages(self, problem: Problem, **kwargs) -> list[dict[str, str]]:
        messages = super()._repair_messages(problem, **kwargs)
        messages[0]["content"] += "\n" + TACTIC_MENU
        return messages


def make_tactic_agent(
    *, arm: str, propose_model: str, repair_model: str
) -> TacticAugmentedRepairAgent:
    return TacticAugmentedRepairAgent(
        arm=arm, propose_model=propose_model, repair_model=repair_model
    )
