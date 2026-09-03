"""Offline unit tests for residual hygiene (P0)."""

from __future__ import annotations

import pytest

from experiments_agents.residual_hygiene import (
    FailedAttemptNotebook,
    build_fail_telemetry,
    is_goal_shaped,
    locked_goal_text,
    promote_goal_shaped_from_text,
)
from experiments_agents.verified_progress import VerifiedProgressGraph
from re_harness import AgentResult, Problem
from submission.agent import SubmissionAgent


def test_notebook_caps_and_english_ascii():
    nb = FailedAttemptNotebook(max_bullets=3, max_chars=40)
    assert nb.add("bridge_no_accept; kind=needs_lemma") is True
    assert nb.add("bridge_no_accept; kind=needs_lemma") is False  # dedupe
    long = "x" * 200
    assert nb.add(long) is True
    assert len(nb.bullets[-1]) <= 40
    nb.add("second fail")
    nb.add("third fail")
    nb.add("fourth fail")  # drops oldest
    assert nb.size() == 3
    block = nb.as_prompt_block()
    assert "Avoid repeating" in block
    assert "fourth fail" in block


def test_is_goal_shaped_overlap_and_reject_restatement():
    goal = "theorem t : IsLeast {n : Nat | n > 0} 1 := by sorry"
    assert is_goal_shaped(
        "IsLeast {n : Nat | n > 0} 1",
        goal_text=goal,
        answer_names=(),
    )
    assert is_goal_shaped(
        "0 < (solution_set).1",
        goal_text=goal,
        answer_names=["solution_set"],
    )
    assert not is_goal_shaped(
        "True",
        goal_text=goal,
        answer_names=(),
    )


def test_promote_goal_shaped_have_into_bank():
    graph = VerifiedProgressGraph()
    goal = "theorem t (n : Nat) : n + 0 = n := by sorry"
    source = """
have h_add : n + 0 = n := by
  exact Nat.add_zero n
have h_noise : True := by
  trivial
"""
    n = promote_goal_shaped_from_text(
        graph,
        source=source,
        goal_text=goal,
        context=goal,
        answer_names=(),
        lean_accepted=True,
    )
    assert n >= 1
    assert len(graph.nodes) >= 1
    assert any("n + 0" in node.statement or "n+0" in node.statement.replace(" ", "")
               for node in graph.nodes.values())


def test_build_fail_telemetry_keys_english():
    graph = VerifiedProgressGraph()
    graph.add_verified(
        statement="True",
        proof="trivial",
        certificate="trivial",
        context="import Mathlib",
        original_goal="False",
        lean_accepted=True,
    )
    tel = build_fail_telemetry(
        failure_kind="def_circular",
        residual_route_mode="program",
        progress_graph=graph,
        residual_rounds_ran=2,
        residual_stall_reason="bank_flat",
        extracts_promoted=3,
        greedy_close_attempted=1,
        notebook_size=2,
        last_residual_detail="bridge_no_accept",
        stages=[{"stage": "x"}],
    )
    for key in (
        "failure_kind",
        "residual_route_mode",
        "progress_graph",
        "residual_rounds_ran",
        "extracts_promoted",
        "greedy_close_attempted",
        "notebook_size",
        "last_residual_detail",
        "bank_nodes_saved",
    ):
        assert key in tel
    assert tel["failure_kind"] == "def_circular"
    assert tel["greedy_close_attempted"] == 1
    assert tel["extracts_promoted"] == 3
    assert tel["residual_rounds_ran"] == 2


@pytest.mark.asyncio
async def test_exhausted_metadata_includes_p0_telemetry(monkeypatch):
    """solve() → exhausted always carries English P0 keys (no Lean)."""

    events = []

    class ExhaustPolicy(SubmissionAgent):
        def __init__(self):
            super().__init__(
                min_slot_time_s=0,
                t2_batch=0,
                t3_batch=0,
                slot_t2_batch=0,
                slot_t3_batch=0,
                experimental_cap_s=30,
            )

        async def _sweep(self, services, challenge, time_left, *, tag):
            return None

        async def _run_champion_portfolio(self, problem, services, time_left):
            return None, None

        async def _solve_slot(self, prob, services, time_left, **kwargs):
            return None

        async def _residual_recursion(self, problem, services, time_left, *, open_blocks):
            # Simulate residual work + greedy flag without Lean.
            self._residual_rounds_ran = 1
            self._greedy_close_attempted = 2
            self._extracts_promoted = 1
            self._lab_notebook.add("r0 residual_recursion_bridge_r0: kind=goal_stuck")
            self._residual_fail_kind = "goal_stuck"
            self._residual_route_mode = "bridge"
            self._last_residual_detail = "bridge_no_accept"
            events.append("residual")
            return None

    import submission.agent as agent_mod

    monkeypatch.setattr(agent_mod, "_time_budget_s", lambda: 900.0)
    policy = ExhaustPolicy()
    problem = Problem(
        id="one",
        description="one",
        challenge="import Mathlib\n\ntheorem only : True := by\n  sorry\n",
    )

    class FakeServices:
        def __init__(self):
            self.llm = object()
            self.lean = object()
            self.checkpoints = []

        def checkpoint(self, source, metadata=None):
            self.checkpoints.append((source, metadata or {}))

    result = await policy.solve(problem, FakeServices())
    assert events == ["residual"]
    assert result.metadata["tier"] == "exhausted"
    assert result.metadata["failure_kind"] == "goal_stuck"
    assert result.metadata["residual_route_mode"] == "bridge"
    assert result.metadata["greedy_close_attempted"] == 2
    assert result.metadata["extracts_promoted"] == 1
    assert result.metadata["notebook_size"] == 1
    assert result.metadata["residual_rounds_ran"] == 1
    assert "last_residual_detail" in result.metadata


@pytest.mark.asyncio
async def test_answer_shaped_champion_final_guard_reject_continues_to_residual(
    monkeypatch,
):
    """P0.1: champion that fails final finish() must not early-return as PASS."""

    events = []

    DEPENDENT = """import Mathlib

abbrev computed_answer : Nat := sorry

theorem dependent_target : 2 + 2 = computed_answer := by
  sorry
"""
    # Circular-looking candidate the stage might like but final guard rejects.
    BAD = """import Mathlib

abbrev computed_answer : Nat := 4

theorem dependent_target : 2 + 2 = computed_answer := by
  rfl
"""

    class GuardRejectPolicy(SubmissionAgent):
        def __init__(self):
            super().__init__(
                min_slot_time_s=0,
                t2_batch=0,
                t3_batch=0,
                slot_t2_batch=0,
                slot_t3_batch=0,
                experimental_cap_s=30,
            )

        async def _sweep(self, services, challenge, time_left, *, tag):
            return None

        async def _run_champion_portfolio(self, problem, services, time_left):
            events.append("champion")
            return BAD, "champion_r_g"

        async def _guard_candidate(self, problem, services, candidate):
            from experiments_agents.candidate_guard import GuardResult

            # Always reject so finish() returns None → residual path.
            return GuardResult(False, ("definitional/tautological probe",), 0)

        async def _solve_slot(self, prob, services, time_left, **kwargs):
            events.append("fallback")
            return None

        async def _residual_recursion(self, problem, services, time_left, *, open_blocks):
            events.append("residual")
            self._residual_rounds_ran = 1
            self._greedy_close_attempted = 1
            return None

    import submission.agent as agent_mod

    monkeypatch.setattr(agent_mod, "_time_budget_s", lambda: 900.0)
    policy = GuardRejectPolicy()
    problem = Problem(
        id="dep",
        description="dep",
        challenge=DEPENDENT,
        metadata={
            "__manifest__": {
                "definition_names": ["computed_answer"],
                "numeric_answer_names": ["computed_answer"],
                "theorem_names": ["dependent_target"],
            }
        },
    )

    class FakeServices:
        def checkpoint(self, *a, **k):
            return None

        llm = object()
        lean = object()

    result = await policy.solve(problem, FakeServices())
    assert "champion" in events
    assert "residual" in events
    assert result.metadata["tier"] == "exhausted"
    assert result.metadata.get("accepted_by_repl") is False
    assert result.metadata["greedy_close_attempted"] >= 1


@pytest.mark.asyncio
async def test_residual_calls_greedy_close_each_round(monkeypatch):
    """P0.5: real residual loop marks greedy_close_attempted ≥ 1."""

    greedy_calls = {"n": 0}

    class GreedyPolicy(SubmissionAgent):
        def __init__(self):
            super().__init__(
                min_slot_time_s=0,
                t2_batch=0,
                t3_batch=0,
                slot_t2_batch=0,
                slot_t3_batch=0,
                experimental_cap_s=20,
            )

        async def _sweep(self, *a, **k):
            return None

        async def _run_champion_portfolio(self, *a, **k):
            return None, None

        async def _solve_slot(self, *a, **k):
            return None

        async def _experimental_bridge(self, problem, services, residual, *, stage, **kwargs):
            return None

        async def _greedy_bank_close(self, problem, services, time_left, *, stage):
            greedy_calls["n"] += 1
            self._greedy_close_attempted += 1
            self._record_stage(stage, 0.0, detail="greedy_no_accept")
            return None

    import submission.agent as agent_mod

    monkeypatch.setattr(agent_mod, "_time_budget_s", lambda: 900.0)
    monkeypatch.setenv("SUBMISSION_RESIDUAL_ROUNDS", "2")
    monkeypatch.setenv("SUBMISSION_RESIDUAL_STALL", "2")

    policy = GreedyPolicy()
    # Call residual directly to avoid experimental program factory noise.
    problem = Problem(
        id="one",
        description="one",
        challenge="import Mathlib\n\ntheorem only : True := by\n  sorry\n",
    )

    class FakeServices:
        def checkpoint(self, *a, **k):
            return None

        llm = object()
        lean = object()

    out = await SubmissionAgent._residual_recursion(
        policy, problem, FakeServices(), lambda: 500.0, open_blocks=[]
    )
    assert out is None
    assert greedy_calls["n"] >= 1
    assert policy._greedy_close_attempted >= 1
    assert policy._lab_notebook.size() >= 1


def test_locked_goal_text_finds_theorem():
    src = "import Mathlib\n\ntheorem foo (n : Nat) : n = n := by\n  sorry\n"
    g = locked_goal_text(src)
    assert "theorem foo" in g
