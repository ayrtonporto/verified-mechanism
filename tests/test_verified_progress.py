from __future__ import annotations

import json

import pytest

from experiments_agents.bridgeportfolio import BridgePortfolioAgent
from experiments_agents.verified_progress import RouteState, VerifiedProgressGraph
from re_harness import Problem


CHALLENGE = """import Mathlib

theorem locked (n : ℕ) :
  n + 0 + 0 = n := by
  sorry
"""


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.requests: list[dict] = []

    async def complete(self, **kwargs):
        self.requests.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return FakeResponse(self.responses.pop(0))


class FakeCheck:
    def __init__(self, accepted: bool):
        self.accepted = accepted
        self.has_sorry = False
        self.timed_out = False
        self.messages = [] if accepted else [{"severity": "error", "data": "unsolved goals"}]


class HarvestReuseLean:
    """Semantic oracle for a failed route followed by bank-only closure."""

    def __init__(self):
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        type_probe = ":\n  True := by\n  trivial" in source
        bridge = (
            "(bp_d0_2 : n = n)" in source
            and "exact bp_d0_2" in source
            and "apply bp_d0_2" not in source
        )
        lemma_one = ":\n  n + 0 = n := by" in source and source.rstrip().endswith("rfl")
        bank_hypothesis = "(vp_" in source and ": n + 0 = n)" in source
        bank_certificate = "have vp_" in source and ": n + 0 = n := by" in source
        bank_closer = "first" in source and (bank_hypothesis or bank_certificate)
        return FakeCheck(type_probe or bridge or lemma_one or bank_closer)


class FakeServices:
    def __init__(self, llm, lean):
        self.llm = llm
        self.lean = lean
        self.checkpoints: list[tuple[str, dict]] = []

    def checkpoint(self, source, metadata=None):
        self.checkpoints.append((source, metadata or {}))


def _portfolio() -> str:
    return json.dumps({
        "routes": [{
            "id": "route_1",
            "summary": "two-step normalization",
            "lemmas": [
                {"name": "bp_1", "statement": "n + 0 = n"},
                {"name": "bp_2", "statement": "n = n"},
            ],
        }]
    })


def _agent(graph: VerifiedProgressGraph) -> BridgePortfolioAgent:
    return BridgePortfolioAgent(
        progress_graph=graph,
        max_depth=0,
        portfolio_calls=1,
        routes_per_call=2,
        max_routes_checked=2,
        max_routes_tried=1,
        max_lemmas=3,
        q_attempts=1,
        g_attempts=0,
        check_timeout_s=10,
        min_time_s=0,
        search_waves=1,
    )


@pytest.mark.asyncio
async def test_harvests_from_failed_route_then_reuses_executable_certificate():
    graph = VerifiedProgressGraph()
    lean = HarvestReuseLean()
    problem = Problem(id="generic", description="normalize additions", challenge=CHALLENGE)
    first_services = FakeServices(
        FakeLLM([
            _portfolio(),
            "```lean\nexact bp_d0_2\n```",
            "```lean\nrfl\n```",
            "```lean\nexact False.elim (by contradiction)\n```",
        ]),
        lean,
    )

    failed = await _agent(graph).solve(problem, first_services)

    assert failed.metadata["accepted_by_repl"] is False
    assert graph.metadata()["nodes_saved"] == 1
    assert any(route.state is RouteState.SUFFICIENT_INCOMPLETE for route in graph.routes)
    node = next(iter(graph.nodes.values()))
    assert node.statement == "n + 0 = n"
    assert node.proof == "rfl"

    second_services = FakeServices(FakeLLM([]), lean)
    solved = await _agent(graph).solve(problem, second_services)

    assert solved.metadata["accepted_by_repl"] is True
    assert second_services.llm.requests == []
    assert "have vp_" in solved.solution
    assert graph.metadata()["nodes_reused"] == 1
    assert graph.metadata()["decisive_reuses"] == 1
    assert any(route.state is RouteState.COMPLETE for route in graph.routes)


def test_rejects_unverified_restatements_and_dependency_cycles():
    graph = VerifiedProgressGraph()
    assert graph.add_verified(
        statement="n = n",
        proof="rfl",
        certificate="rfl",
        context=CHALLENGE,
        original_goal="n = n",
        lean_accepted=True,
    ) is None
    assert graph.add_verified(
        statement="n + 0 = n",
        proof="sorry",
        certificate="sorry",
        context=CHALLENGE,
        original_goal="n + 0 + 0 = n",
        lean_accepted=False,
    ) is None

    first = graph.add_verified(
        node_id="first",
        statement="n + 0 = n",
        proof="rfl",
        certificate="rfl",
        context=CHALLENGE,
        original_goal="n + 0 + 0 = n",
        lean_accepted=True,
    )
    assert first is not None
    second = graph.add_verified(
        node_id="second",
        statement="n + 0 + 0 = n + 0",
        proof="simpa using first",
        certificate="simpa",
        context=CHALLENGE,
        dependencies=["first"],
        original_goal="False",
        lean_accepted=True,
    )
    assert second is not None
    assert graph.add_dependency("first", "second") is False
    assert graph.rejected_cycles == 1


def test_prefilter_rejects_obviously_incompatible_import_context():
    graph = VerifiedProgressGraph()
    node = graph.add_verified(
        statement="x = x",
        proof="rfl",
        certificate="rfl",
        context="import Mathlib.Algebra.Group.Basic\n",
        original_goal="False",
        lean_accepted=True,
    )
    assert node is not None
    assert graph.candidates(
        goal="x = x", context="import Mathlib.Topology.Basic\n", limit=4
    ) == []
    assert graph.rejected_incompatible == 1


def test_certificate_body_always_materializes_bank_haves():
    graph = VerifiedProgressGraph()
    node = graph.add_verified(
        statement="n + 0 = n",
        proof="rfl",
        certificate="rfl",
        context=CHALLENGE,
        original_goal="n + 0 + 0 = n",
        lean_accepted=True,
    )
    assert node is not None
    body = BridgePortfolioAgent._certificate_body([node], [], "simpa using vp_dummy")
    assert f"have {node.alias} : n + 0 = n := by" in body
    assert "rfl" in body


@pytest.mark.asyncio
async def test_filter_drops_goal_restating_and_fully_banked_routes_without_lean():
    """Structural A2 filter must not spend Lean on obvious junk."""

    class NoLean:
        async def check_file(self, *_a, **_k):  # pragma: no cover
            raise AssertionError("structural filter should not call Lean")

    graph = VerifiedProgressGraph()
    node = graph.add_verified(
        statement="n + 0 = n",
        proof="rfl",
        certificate="rfl",
        context=CHALLENGE,
        original_goal="False",
        lean_accepted=True,
    )
    assert node is not None
    agent = BridgePortfolioAgent(progress_graph=graph, min_time_s=0, check_timeout_s=5)
    problem = Problem(id="x", description="d", challenge=CHALLENGE)
    services = FakeServices(FakeLLM([]), NoLean())
    from experiments_agents.bridgeportfolio import BridgeRoute, RouteLemma

    routes = [
        BridgeRoute(
            route_id="bad_goal",
            summary="restates",
            lemmas=[RouteLemma(name="bp_1", statement="n + 0 + 0 = n")],
        ),
        BridgeRoute(
            route_id="already_banked",
            summary="no new work",
            lemmas=[RouteLemma(name="bp_1", statement="n + 0 = n")],
        ),
    ]

    kept = await agent._filter_route_statements(
        problem, services, routes, bank=[node]
    )
    assert kept == []
    assert agent.stats.routes_rejected_restatement >= 2


@pytest.mark.asyncio
async def test_bank_path_combination_closes_with_size_two_subset():
    """Phase B: size-1/2 bank paths can close with decisive reuse."""

    class PathLean:
        async def check_file(self, source: str, timeout_s=None):
            if "first" not in source and "rfl" in source and (
                ":\n  n + 0 = n := by" in source or ":\n  n = n := by" in source
            ):
                return FakeCheck(True)
            type_ok = ":\n  True := by\n  trivial" in source
            both = ("n + 0 = n" in source) and ("n = n" in source)
            closer = "first" in source and both
            assembled = source.count("have vp_") >= 1 and "first" in source
            return FakeCheck(type_ok or closer or assembled)

    g = VerifiedProgressGraph()
    a = g.add_verified(
        statement="n + 0 = n",
        proof="rfl",
        certificate="rfl",
        context=CHALLENGE,
        original_goal="False",
        lean_accepted=True,
    )
    b = g.add_verified(
        statement="n = n",
        proof="rfl",
        certificate="rfl",
        context=CHALLENGE,
        original_goal="False",
        lean_accepted=True,
    )
    assert a and b
    agent = BridgePortfolioAgent(progress_graph=g, min_time_s=0, check_timeout_s=10)
    problem = Problem(id="path", description="d", challenge=CHALLENGE)
    services = FakeServices(FakeLLM([]), PathLean())
    bank = await agent._compatible_bank(problem, services)
    assert len(bank) >= 1
    closed = await agent._try_bank_path_combinations(problem, services, bank)
    assert closed is not None
    assert agent.stats.bank_path_tries >= 1
    assert g.metadata()["decisive_reuses"] >= 1

