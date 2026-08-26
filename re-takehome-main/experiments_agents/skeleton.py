"""Idea B — skeleton / sorry-first decomposition (universal).

Same hardened+tactic machinery, but the proposer is asked to work top-down: lay
out the full proof as `have … := by sorry` steps whose *structure* elaborates
(no Lean errors; unproved bodies may be `sorry` for now), then discharge the
holes. The repair loop then fills remaining `sorry` incrementally, preferring the
tactic menu, without breaking what already compiles.

Universal: the same "decompose then fill" instruction applies to every problem;
nothing routes on problem identity. Final success still requires a sorry-free,
integrity-preserving, comparator-accepted file.
"""

from __future__ import annotations

from re_harness import Problem

from .common import REPAIR_INVARIANTS, TACTIC_MENU
from .tactics import TacticAugmentedRepairAgent


class SkeletonAgent(TacticAugmentedRepairAgent):
    def _propose_messages(self, problem: Problem, *, turn: int) -> list[dict[str, str]]:
        system = "\n".join(
            [
                "You are proving a Lean 4 theorem using Mathlib, working top-down.",
                "First lay out the FULL proof as a skeleton of intermediate steps, each"
                " written as `have <name> : <statement> := by <tactic>` (you may leave"
                " an unproved body as `sorry` for now), arranged so the final goal"
                " follows by combining them.",
                "The skeleton's STRUCTURE must elaborate: no Lean errors are allowed"
                " (only `sorry` placeholders in the `have` bodies).",
                "Then discharge as many `have` bodies as you can with real proofs.",
                "Return only the complete Lean code in one ```lean code block.",
                "Preserve the theorem names and statements from the challenge.",
                "The final answer must contain no `sorry`, `admit`, or axioms.",
                TACTIC_MENU,
            ]
        )
        user = "\n".join(
            [
                f"Problem id: {problem.id}",
                f"Arm: {self.arm}",
                f"Skeleton turn: {turn}/{self.max_propose_turns}",
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

    def _repair_messages(self, problem: Problem, **kwargs) -> list[dict[str, str]]:
        messages = super()._repair_messages(problem, **kwargs)
        messages[1]["content"] += (
            "\n\nComplete the skeleton: replace remaining `sorry` holes with real"
            " proofs, a few per turn, and keep every step that already compiles."
            " Do not weaken or remove any `have` statement or the theorem itself."
        )
        return messages
