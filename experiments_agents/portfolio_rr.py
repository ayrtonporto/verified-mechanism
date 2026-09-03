"""portfolio_RR: non-collaborative routing baseline R-Q then R-G.

Thin composition only — no T0, no cross-model handoff, no slot fallback, no residual.
Policy: run same-model R-Q up to half the per-problem USD budget; on first
substantive accept return; else run R-G on the remainder. First substantive win wins.
"""

from __future__ import annotations

from typing import Any

from re_harness import AgentResult, Problem, Services
from re_harness.budget import BudgetExceeded

from .candidate_guard import validate_solution_candidate
from .common import GPT_OSS, QWEN
from .repair import TargetedRepairAgent


def _budget_ledger(services: Services):
    return services.llm._budget  # harness-private; intentional thin probe


class PortfolioRRAgent:
    """Sequential same-model repair portfolio: R-Q half → R-G remainder."""

    def __init__(self) -> None:
        self.arm = "portfolio_RR"

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        budget = _budget_ledger(services)
        start = budget.snapshot()
        start_spent = float(start.spent_usd)
        limit = float(start.limit_usd)
        remaining = max(0.0, limit - start_spent)
        half_cap = start_spent + (remaining / 2.0)

        stages: list[dict[str, Any]] = []
        calls_q = 0
        calls_g = 0
        lean_checks = 0
        best_solution = problem.challenge
        best_meta: dict[str, Any] = {}

        # --- R-Q on the first half of the USD budget ---
        q_result, q_err = await self._run_arm(
            problem,
            services,
            arm_name="R-Q",
            propose_model=QWEN,
            repair_model=QWEN,
            temp_limit=half_cap,
        )
        if q_result is not None:
            mq = dict(q_result.metadata or {})
            calls_q += int(mq.get("calls_q", 0) or 0)
            calls_g += int(mq.get("calls_g", 0) or 0)
            lean_checks += int(mq.get("lean_checks", 0) or 0)
            stages.append(
                {
                    "stage": "R-Q",
                    "stop_reason": mq.get("stop_reason"),
                    "accepted_by_repl": bool(mq.get("accepted_by_repl")),
                    "spent_after_usd": float(budget.snapshot().spent_usd),
                }
            )
            best_solution = q_result.solution
            best_meta = mq
            if mq.get("accepted_by_repl"):
                return self._win(
                    best_solution,
                    stage_winner="R-Q",
                    stages=stages,
                    calls_q=calls_q,
                    calls_g=calls_g,
                    lean_checks=lean_checks,
                    inner=best_meta,
                )
        else:
            stages.append(
                {
                    "stage": "R-Q",
                    "stop_reason": "error",
                    "error": q_err,
                    "spent_after_usd": float(budget.snapshot().spent_usd),
                }
            )

        # --- R-G on the remainder of the original limit ---
        g_result, g_err = await self._run_arm(
            problem,
            services,
            arm_name="R-G",
            propose_model=GPT_OSS,
            repair_model=GPT_OSS,
            temp_limit=None,  # restore full remaining headroom
        )
        if g_result is not None:
            mg = dict(g_result.metadata or {})
            calls_q += int(mg.get("calls_q", 0) or 0)
            calls_g += int(mg.get("calls_g", 0) or 0)
            lean_checks += int(mg.get("lean_checks", 0) or 0)
            stages.append(
                {
                    "stage": "R-G",
                    "stop_reason": mg.get("stop_reason"),
                    "accepted_by_repl": bool(mg.get("accepted_by_repl")),
                    "spent_after_usd": float(budget.snapshot().spent_usd),
                }
            )
            best_solution = g_result.solution
            best_meta = mg
            if mg.get("accepted_by_repl"):
                return self._win(
                    best_solution,
                    stage_winner="R-G",
                    stages=stages,
                    calls_q=calls_q,
                    calls_g=calls_g,
                    lean_checks=lean_checks,
                    inner=best_meta,
                )
        else:
            stages.append(
                {
                    "stage": "R-G",
                    "stop_reason": "error",
                    "error": g_err,
                    "spent_after_usd": float(budget.snapshot().spent_usd),
                }
            )

        return AgentResult(
            best_solution,
            {
                "arm": self.arm,
                "protocol": "portfolio_RR",
                "stage_winner": "exhausted",
                "substantive_closure": False,
                "accepted_by_repl": False,
                "stages": stages,
                "calls_q": calls_q,
                "calls_g": calls_g,
                "lean_checks": lean_checks,
                "half_budget_usd": half_cap - start_spent,
                "inner": best_meta,
            },
        )

    async def _run_arm(
        self,
        problem: Problem,
        services: Services,
        *,
        arm_name: str,
        propose_model: str,
        repair_model: str,
        temp_limit: float | None,
    ) -> tuple[AgentResult | None, str]:
        budget = _budget_ledger(services)
        old_limit = float(budget.limit_usd)
        try:
            if temp_limit is not None:
                # Keep limit >= already spent so settle stays valid; clamp to half.
                budget.limit_usd = max(float(budget.snapshot().spent_usd), float(temp_limit))
            agent = TargetedRepairAgent(
                arm=arm_name,
                propose_model=propose_model,
                repair_model=repair_model,
                solution_guard=validate_solution_candidate,
            )
            result = await agent.solve(problem, services)
            return result, ""
        except BudgetExceeded as exc:
            return None, f"BudgetExceeded: {exc}"
        except Exception as exc:  # noqa: BLE001 — baseline must not crash the portfolio
            return None, f"{type(exc).__name__}: {exc}"
        finally:
            budget.limit_usd = old_limit

    def _win(
        self,
        solution: str,
        *,
        stage_winner: str,
        stages: list[dict[str, Any]],
        calls_q: int,
        calls_g: int,
        lean_checks: int,
        inner: dict[str, Any],
    ) -> AgentResult:
        return AgentResult(
            solution,
            {
                "arm": self.arm,
                "protocol": "portfolio_RR",
                "stage_winner": stage_winner,
                "substantive_closure": True,
                "accepted_by_repl": True,
                "stages": stages,
                "calls_q": calls_q,
                "calls_g": calls_g,
                "lean_checks": lean_checks,
                "inner": inner,
            },
        )


def create_agent() -> PortfolioRRAgent:
    return PortfolioRRAgent()
