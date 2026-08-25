"""S arms: kit baseline loop with pinned model (not the R protocol)."""

from __future__ import annotations

from baselines.simple_agent import SimpleBaselineAgent

from .common import GPT_OSS, QWEN, require_model


class SoloBaselineAgent(SimpleBaselineAgent):
    """Thin pin of baselines.simple_agent.SimpleBaselineAgent to a fixed model."""

    def __init__(self, *, model: str, arm: str):
        super().__init__(model=require_model(model))
        self.arm = arm

    async def solve(self, problem, services):
        result = await super().solve(problem, services)
        meta = dict(result.metadata)
        meta["arm"] = self.arm
        meta["calls_q"] = 1 if self.model == QWEN else 0
        meta["calls_g"] = 1 if self.model == GPT_OSS else 0
        # Baseline may do multiple turns; recount from attempts if present.
        attempts = meta.get("attempts") or []
        n = len(attempts) if attempts else int(meta.get("turns") or 1)
        if self.model == QWEN:
            meta["calls_q"] = n
            meta["calls_g"] = 0
        else:
            meta["calls_q"] = 0
            meta["calls_g"] = n
        meta["lean_checks"] = n
        return type(result)(result.solution, meta)


def create_s_q() -> SoloBaselineAgent:
    return SoloBaselineAgent(model=QWEN, arm="S-Q")


def create_s_g() -> SoloBaselineAgent:
    return SoloBaselineAgent(model=GPT_OSS, arm="S-G")
