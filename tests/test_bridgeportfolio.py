from __future__ import annotations

import json

import pytest

from experiments_agents.bridgeportfolio import (
    BridgeRoute,
    BridgePortfolioAgent,
    RouteLemma,
    bridge_used_lemmas,
    build_goal_source,
    closing_battery_body,
    extract_proof_body,
    failure_kind,
    goal_shape,
    locked_parameter_names,
    parse_routes,
    restatement_probe_body,
    statement_rebinds_locked_parameter,
)
from experiments_agents.common import GPT_OSS, QWEN
from re_harness import Problem


CHALLENGE = """import Mathlib

theorem locked
  (n : ℕ)
  (h : ∀ k, k ≤ n → k ≤ n) :
  n = n := by
  sorry
"""


QUANTIFIED_CHALLENGE = """import Mathlib

theorem locked_quantified :
  ∀ k, k = k := by
  sorry
"""


RECURSIVE_CHALLENGE = """import Mathlib

theorem locked_recursive
  (n : ℕ)
  (h : ∀ k, k ≤ n → k ≤ n) :
  n + 0 + 0 = n := by
  sorry
"""


PARAMETERIZED_CHALLENGE = """import Mathlib

theorem locked_parameters (a b : ℝ) :
  a + b = a + b := by
  sorry
"""


PREFIXED_CHALLENGE = """import Mathlib

theorem solved_prefix : True := by
  have h : True := by
    trivial
  exact h

theorem locked_after_prefix (n : ℕ) :
  n = n := by
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
        self.messages = [] if accepted else [
            {"severity": "error", "data": "unsolved goals"}
        ]


class RuleLean:
    """Tiny semantic oracle for the bridge/recursion control-flow tests."""

    def __init__(self, *, recursive: bool = False):
        self.recursive = recursive
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        is_type_probe = ":\n  True := by\n  trivial" in source
        has_root_bridge = "(bp_d0_1 : n + 0 = n)" in source
        has_child_bridge = "(bp_d1_1 : n = n)" in source
        root_final = "have bp_d0_1 : n + 0 = n := by" in source
        child_final = "have bp_d1_1 : n = n := by" in source
        goal_is_child_leaf = ":\n  n = n := by" in source and not has_root_bridge
        goal_is_root_lemma = ":\n  n + 0 = n := by" in source

        accepted = False
        if is_type_probe:
            accepted = True
        elif has_root_bridge and "simpa using bp_d0_1" in source:
            accepted = True
        elif has_child_bridge and "simpa using bp_d1_1" in source:
            accepted = True
        elif root_final and "simpa using bp_d0_1" in source:
            accepted = True
        elif child_final and "simpa using bp_d1_1" in source:
            accepted = True
        elif not self.recursive and goal_is_root_lemma and "simp_all" in source:
            accepted = True
        elif self.recursive and goal_is_child_leaf and "simp_all" in source:
            accepted = True
        return FakeCheck(accepted)


class RestatementLean:
    """Accept only the semantic target-restatement probe."""

    def __init__(self):
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        accepted = ":\n  True := by\n  trivial" in source or (
            "(bp_d0_1 : ∀ k : ℕ, k = k)" in source
            and "exact bp_d0_1" in source
        )
        return FakeCheck(accepted)


class GeneralizedRestatementLean:
    """Recognize a stronger milestone whose binders specialize to the root target."""

    def __init__(self):
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        accepted = ":\n  True := by\n  trivial" in source or (
            "(bp_d0_1 : ∀ x y : ℝ, x + y = x + y)" in source
            and "(apply bp_d0_1 <;> done)" in source
        )
        return FakeCheck(accepted)


class RootCloserLean:
    """Accept the combined deterministic closer and its strict final replay."""

    def __init__(self):
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        accepted = (
            "first\n    | (simp_all <;> done)" in source
            and "(bp_" not in source
        )
        return FakeCheck(accepted)


class RejectAllLean:
    def __init__(self):
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        return FakeCheck(False)


class FakeServices:
    def __init__(self, llm: FakeLLM, lean):
        self.llm = llm
        self.lean = lean
        self.checkpoints: list[tuple[str, dict]] = []

    def checkpoint(self, source, metadata=None):
        self.checkpoints.append((source, metadata or {}))


def _portfolio(statement: str) -> str:
    return json.dumps({
        "routes": [{
            "id": "route_1",
            "summary": "reduce to a smaller normalization fact",
            "lemmas": [{
                "name": "bp_1",
                "statement": statement,
                "purpose": "normalizes the left side",
                "proof_hint": "simplify the neutral addition",
            }],
        }]
    })


def _agent(*, max_depth: int) -> BridgePortfolioAgent:
    return BridgePortfolioAgent(
        max_depth=max_depth,
        portfolio_calls=1,
        routes_per_call=2,
        max_routes_checked=2,
        max_routes_tried=1,
        max_lemmas=3,
        q_attempts=0,
        g_attempts=0,
        check_timeout_s=10,
        min_time_s=0,
        search_waves=1,
    )


def test_goal_builder_locks_multiline_statement_and_adds_hypotheses():
    shape = goal_shape(CHALLENGE)
    assert shape is not None
    assert shape.theorem_name == "locked"
    assert shape.goal == "n = n"

    built = build_goal_source(
        CHALLENGE,
        extra_hypotheses=[("bp_d0_1", "n + 0 = n")],
        proof_body="simpa using bp_d0_1",
    )
    assert built is not None
    assert "(h : ∀ k, k ≤ n → k ≤ n)" in built
    assert "(bp_d0_1 : n + 0 = n)" in built
    assert "set_option autoImplicit false in\ntheorem locked" in built
    assert ":\n  n = n := by" in built
    assert "sorry" not in built


def test_goal_builder_disables_free_autoimplicit_milestone_names():
    built = build_goal_source(
        CHALLENGE,
        extra_hypotheses=[("bp_d0_1", "(u : ℤ) = u")],
        goal_override="True",
        proof_body="trivial",
    )

    assert built is not None
    assert "set_option autoImplicit false in" in built
    assert "(bp_d0_1 : (u : ℤ) = u)" in built


def test_locked_parameter_rebinding_is_detected_before_lean_search():
    locked = locked_parameter_names(PARAMETERIZED_CHALLENGE)
    assert {"a", "b"} <= locked
    assert statement_rebinds_locked_parameter("∀ a b : ℝ, a + b = a + b", locked)
    assert not statement_rebinds_locked_parameter("a + b = a + b", locked)
    assert not statement_rebinds_locked_parameter("∀ x : ℝ, x = x", locked)


def test_failure_kind_distinguishes_timeout_elaboration_and_local_goal():
    assert failure_kind("TIMEOUT after 300s") == "timeout"
    assert failure_kind("unexpected token 'by'; expected command") == "elaboration"
    assert failure_kind("unsolved goals\ncase mp") == "local_goal"
    assert failure_kind("") == "no_candidate"


def test_goal_builder_selects_last_open_theorem_after_a_solved_prefix():
    shape = goal_shape(PREFIXED_CHALLENGE)
    assert shape is not None
    assert shape.theorem_name == "locked_after_prefix"
    assert shape.goal == "n = n"
    built = build_goal_source(PREFIXED_CHALLENGE, proof_body="rfl")
    assert built is not None
    assert "theorem solved_prefix : True := by" in built
    assert "theorem locked_after_prefix (n : ℕ)" in built
    assert built.rstrip().endswith("rfl")


def test_route_parser_rejects_restatements_future_dependencies_and_duplicates():
    payload = {"routes": [
        {
            "id": "good",
            "summary": "good",
            "lemmas": [{"name": "bp_1", "statement": "n + 0 = n"}],
        },
        {
            "id": "duplicate",
            "summary": "same route",
            "lemmas": [{"name": "bp_1", "statement": "n + 0 = n"}],
        },
        {
            "id": "circular",
            "summary": "restates goal",
            "lemmas": [{"name": "bp_1", "statement": "n = n"}],
        },
        {
            "id": "future",
            "summary": "illegal dependency",
            "lemmas": [
                {"name": "bp_1", "statement": "bp_2 → n = n"},
                {"name": "bp_2", "statement": "n + 0 = n"},
            ],
        },
    ]}
    routes = parse_routes(json.dumps(payload), goal="n = n", max_routes=8, max_lemmas=5)
    assert [route.route_id for route in routes] == ["good"]


def test_proof_body_extraction_ignores_returned_header_and_refuses_escapes():
    assert extract_proof_body("```lean\nsimpa using h\n```") == "simpa using h"
    assert extract_proof_body(
        "```lean\nby\n  have h : True := by\n    trivial\n  exact h\n```"
    ) == "have h : True := by\n  trivial\nexact h"
    assert extract_proof_body("```lean\nsorry\n```") is None
    # If a model returns a complete, altered theorem despite the prompt, only its body
    # survives. The host later grafts `trivial` under the original locked statement.
    assert extract_proof_body(
        "```lean\ntheorem replacement : True := by trivial\n```"
    ) == "trivial"
    assert extract_proof_body(
        "```lean\ntheorem replacement : True := by\n  have h : True := by\n    trivial\n  exact h\n```"
    ) == "have h : True := by\n  trivial\nexact h"
    assert extract_proof_body("```lean\nnative_decide\n```") is None


def test_bridge_may_consume_final_milestone_without_naming_preparatory_ones():
    route = BridgeRoute(
        route_id="chain",
        summary="two-stage chain",
        lemmas=[
            RouteLemma("bp_d0_1", "n + 0 = n"),
            RouteLemma("bp_d0_2", "n = n"),
        ],
    )
    assert bridge_used_lemmas(route, "exact bp_d0_2") == {"bp_d0_2"}
    assert bridge_used_lemmas(route, "trivial") == set()


def test_combined_probes_require_a_fully_closed_branch():
    closing = closing_battery_body(("simp_all", "omega"))
    assert closing == (
        "first\n"
        "  | (simp_all <;> done)\n"
        "  | (omega <;> done)"
    )
    route = BridgeRoute(
        route_id="general",
        summary="generalized target",
        lemmas=[RouteLemma("bp_d0_1", "∀ x y : ℝ, x + y = x + y")],
    )
    probe = restatement_probe_body(route)
    assert "exact bp_d0_1" in probe
    assert "(apply bp_d0_1 <;> done)" in probe
    assert "(solve_by_elim [bp_d0_1] <;> done)" in probe


@pytest.mark.asyncio
async def test_route_rebinding_locked_parameters_is_rejected_without_bridge_spend():
    problem = Problem(
        id="locked_parameters",
        description="prove a parameterized target",
        challenge=PARAMETERIZED_CHALLENGE,
    )
    services = FakeServices(
        FakeLLM([_portfolio("∀ a b : ℝ, a + b = a + b")]),
        RejectAllLean(),
    )

    result = await _agent(max_depth=0).solve(problem, services)

    assert result.metadata["accepted_by_repl"] is False
    assert result.metadata["routes_rejected_rebinding"] == 1
    assert result.metadata["bridges_checked"] == 0
    assert len(services.llm.requests) == 1


@pytest.mark.asyncio
async def test_bridge_is_verified_before_milestone_and_strict_final_is_checkpointed():
    problem = Problem(id="locked", description="prove the reflexive target", challenge=CHALLENGE)
    services = FakeServices(
        FakeLLM([_portfolio("n + 0 = n"), "```lean\nsimpa using bp_d0_1\n```"]),
        RuleLean(recursive=False),
    )

    result = await _agent(max_depth=0).solve(problem, services)

    assert result.metadata["accepted_by_repl"] is True
    assert result.metadata["bridges_verified"] == 1
    assert "have bp_d0_1 : n + 0 = n := by" in result.solution
    assert "sorry" not in result.solution
    assert len(services.checkpoints) == 1
    bridge_index = next(
        i for i, source in enumerate(services.lean.sources)
        if "(bp_d0_1 : n + 0 = n)" in source
    )
    lemma_index = next(
        i for i, source in enumerate(services.lean.sources)
        if ":\n  n + 0 = n := by" in source and "(bp_d0_1" not in source
    )
    assert bridge_index < lemma_index


@pytest.mark.asyncio
async def test_semantic_restatement_with_explicit_binder_type_is_rejected():
    problem = Problem(
        id="locked_quantified",
        description="prove a quantified reflexive target",
        challenge=QUANTIFIED_CHALLENGE,
    )
    services = FakeServices(
        FakeLLM([_portfolio("∀ k : ℕ, k = k")]),
        RestatementLean(),
    )

    result = await _agent(max_depth=0).solve(problem, services)

    assert result.metadata["accepted_by_repl"] is False
    assert result.metadata["routes_rejected_restatement"] == 1
    assert result.metadata["bridges_checked"] == 0
    assert services.checkpoints == []
    assert any("exact bp_d0_1" in source for source in services.lean.sources)
    assert len(services.llm.requests) == 1


@pytest.mark.asyncio
async def test_binder_generalized_target_restatement_is_rejected_before_bridge_call():
    problem = Problem(
        id="locked_parameters",
        description="prove a parameterized reflexive target",
        challenge=PARAMETERIZED_CHALLENGE,
    )
    services = FakeServices(
        FakeLLM([_portfolio("∀ x y : ℝ, x + y = x + y")]),
        GeneralizedRestatementLean(),
    )

    result = await _agent(max_depth=0).solve(problem, services)

    assert result.metadata["accepted_by_repl"] is False
    assert result.metadata["routes_rejected_restatement"] == 1
    assert result.metadata["bridges_checked"] == 0
    assert len(services.llm.requests) == 1


@pytest.mark.asyncio
async def test_root_closer_solves_easy_problem_without_any_model_call():
    problem = Problem(id="locked", description="prove the easy target", challenge=CHALLENGE)
    services = FakeServices(FakeLLM([]), RootCloserLean())

    result = await _agent(max_depth=0).solve(problem, services)

    assert result.metadata["accepted_by_repl"] is True
    assert result.metadata["root_direct"] == 1
    assert result.metadata["portfolio_calls"] == 0
    assert len(services.llm.requests) == 0
    assert len(services.lean.sources) == 2
    assert "first" in result.solution


@pytest.mark.asyncio
async def test_second_wave_receives_the_cross_route_failure_ledger():
    problem = Problem(id="locked", description="prove the target", challenge=CHALLENGE)
    llm = FakeLLM(["{}", _portfolio("n + 0 = n")])
    services = FakeServices(llm, RejectAllLean())
    agent = BridgePortfolioAgent(
        max_depth=0,
        portfolio_calls=1,
        routes_per_call=2,
        max_routes_checked=2,
        max_routes_tried=1,
        max_lemmas=3,
        q_attempts=0,
        g_attempts=0,
        check_timeout_s=10,
        min_time_s=0,
        search_waves=2,
    )

    result = await agent.solve(problem, services)

    assert result.metadata["accepted_by_repl"] is False
    assert result.metadata["waves_started"] == 2
    assert result.metadata["retry_waves"] == 1
    assert len(llm.requests) == 2
    assert llm.requests[0]["model"] == GPT_OSS
    assert llm.requests[1]["model"] == GPT_OSS
    assert llm.requests[0]["seed"] != llm.requests[1]["seed"]
    retry_prompt = llm.requests[1]["messages"][1]["content"]
    assert "Previous portfolio wave 0 failed" in retry_prompt
    assert "Portfolio wave: 1" in retry_prompt


@pytest.mark.asyncio
async def test_route_reviewer_is_independent_from_the_gpt_oss_planner():
    ranking = json.dumps({
        "ranking": [
            {"id": "second", "score": 90, "verdict": "accept", "reason": "smaller"},
            {"id": "first", "score": 40, "verdict": "accept", "reason": "usable"},
        ]
    })
    llm = FakeLLM([ranking])
    services = FakeServices(llm, RejectAllLean())
    routes = [
        BridgeRoute("first", "first route", [RouteLemma("bp_1", "True")]),
        BridgeRoute("second", "second route", [RouteLemma("bp_1", "1 = 1")]),
    ]

    ranked = await _agent(max_depth=0)._rank_routes(
        Problem(id="locked", description="prove", challenge=CHALLENGE),
        services,
        routes,
        depth=0,
    )

    assert [route.route_id for route in ranked] == ["second", "first"]
    assert llm.requests[0]["model"] == QWEN
    assert "independent critic" in llm.requests[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_well_formed_reviewer_can_reject_the_entire_portfolio():
    ranking = json.dumps({
        "ranking": [
            {"id": "first", "score": 5, "verdict": "reject", "reason": "false"},
            {"id": "second", "score": 10, "verdict": "reject", "reason": "too strong"},
        ]
    })
    llm = FakeLLM([ranking])
    routes = [
        BridgeRoute("first", "first route", [RouteLemma("bp_1", "True")]),
        BridgeRoute("second", "second route", [RouteLemma("bp_1", "1 = 1")]),
    ]

    ranked = await _agent(max_depth=0)._rank_routes(
        Problem(id="locked", description="prove", challenge=CHALLENGE),
        FakeServices(llm, RejectAllLean()),
        routes,
        depth=0,
    )

    assert ranked == []


@pytest.mark.asyncio
async def test_route_reviewer_retries_one_malformed_audit_before_fallback():
    valid = json.dumps({
        "ranking": [
            {"id": "first", "score": 80, "verdict": "accept", "reason": "usable"},
            {"id": "second", "score": 5, "verdict": "reject", "reason": "false"},
        ]
    })
    llm = FakeLLM(["long analysis without final json", valid])
    routes = [
        BridgeRoute("first", "first route", [RouteLemma("bp_1", "True")]),
        BridgeRoute("second", "second route", [RouteLemma("bp_1", "1 = 1")]),
    ]

    ranked = await _agent(max_depth=0)._rank_routes(
        Problem(id="locked", description="prove", challenge=CHALLENGE),
        FakeServices(llm, RejectAllLean()),
        routes,
        depth=0,
    )

    assert [route.route_id for route in ranked] == ["first"]
    assert len(llm.requests) == 2
    assert "did not produce parseable JSON" in llm.requests[1]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_failed_frontier_critic_is_batched_and_cannot_override_lean_facts():
    assessment = json.dumps({
        "assessment": "near",
        "reason": "one certified prefix remains and only the second lemma is blocked",
        "recommended_action": "deepen_blocked",
        "feedback_for_planner": "split the blocked arithmetic milestone",
    })
    llm = FakeLLM([assessment])
    services = FakeServices(llm, RejectAllLean())
    agent = _agent(max_depth=0)
    reports = [{
        "route": "d0_w0_1_route_1",
        "score": 80,
        "bank": ["saved_1"],
        "lemmas": [
            {"name": "bp_d0_1", "status": "proved", "node_id": "saved_2"},
            {"name": "bp_d0_2", "status": "blocked", "diagnostics": "unsolved goals"},
        ],
    }]

    result = await agent._assess_failed_frontier(
        Problem(id="locked", description="prove", challenge=CHALLENGE),
        services,
        depth=0,
        wave=0,
        reason="milestone attempts exhausted",
        reports=reports,
    )

    assert result is not None
    assert result["assessment"] == "near"
    assert result["recommended_action"] == "deepen_blocked"
    assert agent.stats.critic_calls == 1
    assert len(agent.stats.critic_assessments) == 1
    assert len(llm.requests) == 1
    assert llm.requests[0]["model"] == QWEN
    prompt = llm.requests[0]["messages"][1]["content"]
    assert '"bridge_verified": true' in prompt
    assert '"status": "proved"' in prompt
    assert "saved_2" in prompt


@pytest.mark.asyncio
async def test_ill_typed_route_is_rejected_before_any_bridge_call():
    problem = Problem(id="locked", description="prove the target", challenge=CHALLENGE)
    services = FakeServices(
        FakeLLM([_portfolio("UnknownNamespace.missing n")]),
        RejectAllLean(),
    )

    result = await _agent(max_depth=0).solve(problem, services)

    assert result.metadata["accepted_by_repl"] is False
    assert result.metadata["routes_rejected_illtyped"] == 1
    assert result.metadata["bridges_checked"] == 0
    assert len(services.llm.requests) == 1


@pytest.mark.asyncio
async def test_blocked_milestone_is_recursively_decomposed_with_fresh_names():
    problem = Problem(
        id="locked_recursive",
        description="prove the recursively normalized target",
        challenge=RECURSIVE_CHALLENGE,
    )
    services = FakeServices(
        FakeLLM([
            _portfolio("n + 0 = n"),
            "```lean\nsimpa using bp_d0_1\n```",
            _portfolio("n = n"),
            "```lean\nsimpa using bp_d1_1\n```",
        ]),
        RuleLean(recursive=True),
    )

    result = await _agent(max_depth=1).solve(problem, services)

    assert result.metadata["accepted_by_repl"] is True
    assert result.metadata["recursive_calls"] == 1
    assert result.metadata["max_depth_seen"] == 1
    assert "have bp_d0_1 : n + 0 = n := by" in result.solution
    assert "have bp_d1_1 : n = n := by" in result.solution
    assert "(bp_d0_1" not in "\n".join(
        source for source in services.lean.sources if "(bp_d1_1" in source
    )
