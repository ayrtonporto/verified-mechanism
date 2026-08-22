from __future__ import annotations

import pytest

from baselines.simple_agent import SimpleBaselineAgent, _extract_lean
from re_harness import Problem


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.requests = []

    async def complete(self, **kwargs):
        self.requests.append(kwargs)
        return FakeResponse(self.responses.pop(0))


class FakeCheck:
    def __init__(self, accepted: bool, messages=None, timed_out: bool = False):
        self.accepted = accepted
        self.messages = messages or []
        self.timed_out = timed_out


class FakeLean:
    def __init__(self, checks: list[FakeCheck]):
        self.checks = list(checks)
        self.sources = []

    async def check_file(self, source: str):
        self.sources.append(source)
        return self.checks.pop(0)


class FakeServices:
    def __init__(self, llm: FakeLLM, lean: FakeLean):
        self.llm = llm
        self.lean = lean
        self.checkpoints = []

    def checkpoint(self, source, metadata=None):
        self.checkpoints.append((source, metadata or {}))


def test_extracts_lean_fence():
    assert _extract_lean("words\n```lean\nimport Mathlib\n#check Nat\n```", "fallback") == (
        "import Mathlib\n#check Nat\n"
    )


def test_extracts_from_first_import_without_fence():
    assert _extract_lean("Here is code:\nimport Mathlib\n#check Nat", "fallback") == (
        "import Mathlib\n#check Nat\n"
    )


@pytest.mark.asyncio
async def test_simple_baseline_repairs_and_stops_on_acceptance():
    problem = Problem(
        id="p",
        description="prove True",
        challenge="import Mathlib\n\ntheorem p : True := by\n  sorry\n",
    )
    services = FakeServices(
        FakeLLM([
            "```lean\nimport Mathlib\n\ntheorem p : True := by\n  exact False.elim\n```",
            "```lean\nimport Mathlib\n\ntheorem p : True := by\n  trivial\n```",
        ]),
        FakeLean([
            FakeCheck(False, [{"severity": "error", "data": "type mismatch"}]),
            FakeCheck(True),
        ]),
    )
    agent = SimpleBaselineAgent(max_turns=3, model="qwen/qwen3.5-flash-02-23")
    result = await agent.solve(problem, services)

    assert "trivial" in result.solution
    assert result.metadata["accepted_by_repl"] is True
    assert result.metadata["turns"] == 2
    assert len(services.checkpoints) == 2
    assert "type mismatch" in services.llm.requests[1]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_simple_baseline_marks_last_turn():
    problem = Problem(id="p", description="prove True", challenge="import Mathlib\n")
    services = FakeServices(
        FakeLLM(["import Mathlib\n", "import Mathlib\n"]),
        FakeLean([
            FakeCheck(False, [{"severity": "error", "data": "still bad"}]),
            FakeCheck(False, [{"severity": "error", "data": "still bad"}]),
        ]),
    )
    agent = SimpleBaselineAgent(max_turns=2, model="qwen/qwen3.5-flash-02-23")
    result = await agent.solve(problem, services)

    assert result.metadata["accepted_by_repl"] is False
    assert "final attempt" in services.llm.requests[1]["messages"][0]["content"].lower()

