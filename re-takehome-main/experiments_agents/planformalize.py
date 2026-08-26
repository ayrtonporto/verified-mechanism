"""Idea D — planner → formalizer (universal, heterogeneous division of labor).

One model acts as a *strategist*: it writes a natural-language mathematical plan
(key lemmas, induction/case structure) — no Lean. The other model *formalizes*
that plan into Lean and then runs the hardened tactic-augmented repair loop with
the plan kept in context. Distinct from handoff-repair (which edits the other
model's code): here the split is strategy vs formalization.

Universal: the same plan-then-formalize protocol applies to every problem.
"""

from __future__ import annotations

from re_harness import AgentResult, Problem, Services

from .common import count_model_calls, require_model
from .tactics import TacticAugmentedRepairAgent


class PlanFormalizeAgent(TacticAugmentedRepairAgent):
    def __init__(self, *, arm: str, planner_model: str, formalizer_model: str, **kwargs):
        super().__init__(
            arm=arm, propose_model=formalizer_model, repair_model=formalizer_model, **kwargs
        )
        self.planner_model = require_model(planner_model)
        self._plan = ""

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        response = await services.llm.complete(
            model=self.planner_model,
            messages=self._plan_messages(problem),
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        planner_q, planner_g = count_model_calls(self.planner_model, 0, 0)
        self._plan = (response.content or "").strip()[:4000]

        result = await super().solve(problem, services)
        merged = dict(result.metadata)
        merged["protocol"] = "plan_then_formalize"
        merged["planner_model"] = self.planner_model
        merged["formalizer_model"] = self.propose_model
        merged["calls_q"] = int(merged.get("calls_q", 0)) + planner_q
        merged["calls_g"] = int(merged.get("calls_g", 0)) + planner_g
        merged["has_plan"] = bool(self._plan)
        return AgentResult(result.solution, merged)

    def _plan_messages(self, problem: Problem) -> list[dict[str, str]]:
        system = (
            "You are a proof strategist. Give a concise, correct step-by-step "
            "MATHEMATICAL plan to prove the target theorem(s): the key lemmas, the "
            "induction or case structure, and which standard facts to use. Do NOT "
            "write Lean code — only the mathematical plan."
        )
        user = "\n".join(
            [
                f"Problem id: {problem.id}",
                "",
                "Problem description:",
                problem.description,
                "",
                "Target Lean theorem(s):",
                "```lean",
                problem.challenge,
                "```",
            ]
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _propose_messages(self, problem: Problem, *, turn: int) -> list[dict[str, str]]:
        messages = super()._propose_messages(problem, turn=turn)
        if self._plan:
            messages[1]["content"] += "\n\nFollow this proof plan:\n" + self._plan
        return messages

    def _repair_messages(self, problem: Problem, **kwargs) -> list[dict[str, str]]:
        messages = super()._repair_messages(problem, **kwargs)
        if self._plan:
            messages[1]["content"] += "\n\nProof plan to follow:\n" + self._plan
        return messages
