from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments_agents.common import GPT_OSS, QWEN
from experiments_agents.repair import TargetedRepairAgent
from re_harness import Problem


CHALLENGE = """import Mathlib

theorem generic_target : True := by
  sorry
"""

SEED = """import Mathlib

theorem generic_target : True := by
  exact False.elim (by contradiction)
"""

SOLVED = """import Mathlib

theorem generic_target : True := by
  trivial
"""


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=f"```lean\n{SOLVED}```")


class FakeLean:
    def __init__(self):
        self.sources = []

    async def check_file(self, source, **_kwargs):
        self.sources.append(source)
        accepted = "trivial" in source
        messages = [] if accepted else [
            {"severity": "error", "data": "seed proof does not close"}
        ]
        return SimpleNamespace(
            accepted=accepted,
            has_sorry=False,
            timed_out=False,
            messages=messages,
        )


class FakeServices:
    def __init__(self):
        self.llm = FakeLLM()
        self.lean = FakeLean()
        self.checkpoints = []

    def checkpoint(self, source, metadata=None):
        self.checkpoints.append((source, metadata or {}))


@pytest.mark.asyncio
async def test_seeded_handoff_repairs_the_prior_candidate_without_a_new_proposal():
    services = FakeServices()
    agent = TargetedRepairAgent(
        arm="SEEDED-QG",
        propose_model=QWEN,
        repair_model=GPT_OSS,
        max_repair_turns=3,
        initial_candidate=SEED,
    )

    result = await agent.solve(
        Problem(id="generic", description="prove it", challenge=CHALLENGE),
        services,
    )

    assert result.metadata["accepted_by_repl"] is True
    assert result.metadata["seeded"] is True
    assert result.metadata["calls_q"] == 0
    assert result.metadata["calls_g"] == 1
    assert result.metadata["lean_checks"] == 2  # seed revalidation + repaired file
    assert len(services.llm.calls) == 1
    request = services.llm.calls[0]
    assert request["model"] == GPT_OSS
    assert "Best failed proof so far" in request["messages"][1]["content"]
    assert SEED.strip() in request["messages"][1]["content"]
    assert result.solution == SOLVED
