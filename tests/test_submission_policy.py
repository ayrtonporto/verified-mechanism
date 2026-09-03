from __future__ import annotations

import pytest

from re_harness import AgentResult, Problem
from experiments_agents.common import integrity_check, strict_integrity_check
from experiments_agents.multitheorem import split_declarations
from submission.agent import SubmissionAgent, _locked_slot_body


MULTI = """import Mathlib

theorem first_part : True := by
  sorry

theorem second_part : True := by
  sorry
"""

DEPENDENT = """import Mathlib

abbrev computed_answer : Nat := sorry

theorem dependent_target : 2 + 2 = computed_answer := by
  sorry
"""


class FakeServices:
    def __init__(self):
        self.llm = object()
        self.lean = object()
        self.checkpoints = []

    def checkpoint(self, source, metadata=None):
        self.checkpoints.append((source, metadata or {}))


class OrderedProgram:
    def __init__(self, events, time_left):
        self.events = events
        self.time_left = time_left

    async def solve(self, problem, services):
        self.events.append(("experiment", self.time_left()))
        return AgentResult(problem.challenge, {"accepted_by_repl": False})


class OrderedPolicy(SubmissionAgent):
    def __init__(self, events, **kwargs):
        self.events = events
        super().__init__(
            min_slot_time_s=0,
            t2_batch=0,
            t3_batch=0,
            slot_t2_batch=0,
            slot_t3_batch=0,
            experimental_cap_s=kwargs.pop("experimental_cap_s", 120),
            program_factory=lambda **kw: OrderedProgram(events, kw["time_left"]),
            **kwargs,
        )

    async def _sweep(self, services, challenge, time_left, *, tag):
        self.events.append((f"sweep:{tag}", time_left()))
        return None

    async def _run_champion_portfolio(self, problem, services, time_left):
        self.events.append(("champion", time_left()))
        return None, None

    async def _solve_slot(self, prob, services, time_left, **kwargs):
        self.events.append(("fallback", time_left()))
        return None


class ResidualTrackingPolicy(OrderedPolicy):
    """Records residual recursion entry after the capped experiment stage."""

    def __init__(self, events, residual_result=None, **kwargs):
        self.residual_result = residual_result
        super().__init__(events, **kwargs)

    async def _residual_recursion(self, problem, services, time_left, *, open_blocks):
        self.events.append(("residual", time_left(), tuple(open_blocks)))
        return self.residual_result


@pytest.mark.asyncio
async def test_experiment_runs_only_after_every_prior_fallback_and_is_time_capped():
    events = []
    policy = ResidualTrackingPolicy(events, residual_result=None)
    problem = Problem(id="generic_multi", description="prove both", challenge=MULTI)

    result = await policy.solve(problem, FakeServices())

    labels = [label for label, *_rest in events]
    assert labels[0:2] == ["sweep:whole", "champion"]
    assert labels.count("fallback") == 3  # two slots plus whole-file last resort
    assert "experiment" in labels
    assert labels.index("experiment") > max(
        index for index, label in enumerate(labels) if label == "fallback"
    )
    exp_idx = labels.index("experiment")
    assert labels[exp_idx + 1] == "residual"
    experimental_remaining = events[exp_idx][1]
    assert 0 < experimental_remaining <= 120
    residual_remaining = events[exp_idx + 1][1]
    assert residual_remaining >= 0
    assert result.metadata["accepted_by_repl"] is False


@pytest.mark.asyncio
async def test_residual_recursion_runs_after_failed_ladder_when_wall_remains():
    events = []
    won = AgentResult(
        "import Mathlib\n\ntheorem first_part : True := by trivial\n\n"
        "theorem second_part : True := by trivial\n",
        {
            "tier": "residual_recursion_program",
            "stage_winner": "residual_recursion_program",
            "accepted_by_repl": True,
            "substantive_closure": True,
        },
    )
    policy = ResidualTrackingPolicy(events, residual_result=won)
    problem = Problem(id="generic_multi", description="prove both", challenge=MULTI)

    result = await policy.solve(problem, FakeServices())

    labels = [label for label, *_rest in events]
    assert labels[-1] == "residual"
    assert labels.index("residual") > labels.index("experiment")
    assert result.metadata["stage_winner"] == "residual_recursion_program"
    assert result.metadata["accepted_by_repl"] is True


@pytest.mark.asyncio
async def test_residual_recursion_skipped_when_early_stage_already_passes():
    events = []

    class EarlyWin(ResidualTrackingPolicy):
        async def _sweep(self, services, challenge, time_left, *, tag):
            self.events.append((f"sweep:{tag}", time_left()))
            return (
                "import Mathlib\n\ntheorem only : True := by trivial\n"
                if tag == "whole"
                else None
            )

        async def _guard_candidate(self, problem, services, source):
            from experiments_agents.candidate_guard import GuardResult

            return GuardResult(True, lean_checks=0)

    policy = EarlyWin(events, residual_result=AgentResult("should-not-run", {}))
    problem = Problem(
        id="easy",
        description="easy",
        challenge="import Mathlib\n\ntheorem only : True := by\n  sorry\n",
    )
    result = await policy.solve(problem, FakeServices())

    labels = [label for label, *_rest in events]
    assert labels == ["sweep:whole"]
    assert "residual" not in labels
    assert result.metadata["tier"] == "T0_sweep"
    assert result.metadata["accepted_by_repl"] is True


@pytest.mark.asyncio
async def test_residual_runs_multiple_rounds_when_bank_grows(monkeypatch):
    """Phase C: residual outer loop continues while the lemma bank grows."""
    events = []
    grow = {"n": 0}

    class GrowBank(ResidualTrackingPolicy):
        async def _residual_recursion(self, problem, services, time_left, *, open_blocks):
            # Call the real multi-round residual with a fake bridge that grows the bank.
            async def fake_bridge(problem, services, residual, *, stage, **kwargs):
                # Simulate harvest: add a node each odd round, never solve.
                if grow["n"] % 2 == 0:
                    self._progress_graph.add_verified(
                        statement=f"True_{grow['n']}",
                        proof="trivial",
                        certificate="trivial",
                        context=problem.challenge,
                        original_goal="False",
                        lean_accepted=True,
                    )
                grow["n"] += 1
                events.append(("bridge", stage, len(self._progress_graph.nodes), residual()))
                return None

            self._experimental_bridge = fake_bridge  # type: ignore
            return await SubmissionAgent._residual_recursion(
                self, problem, services, time_left, open_blocks=open_blocks
            )

    # Single-theorem challenge so residual takes the bridge branch.
    single = "import Mathlib\n\ntheorem only : True := by\n  sorry\n"
    policy = GrowBank(events, residual_result=None, experimental_cap_s=30)
    # Force plenty of outer wall for residual rounds.
    import submission.agent as agent_mod

    monkeypatch.setattr(agent_mod, "_time_budget_s", lambda: 900.0)
    monkeypatch.setenv("SUBMISSION_RESIDUAL_ROUNDS", "3")
    monkeypatch.setenv("SUBMISSION_RESIDUAL_STALL", "2")

    result = await policy.solve(
        Problem(id="one", description="one", challenge=single), FakeServices()
    )
    bridge_events = [e for e in events if e[0] == "bridge"]
    assert len(bridge_events) >= 2, bridge_events
    assert result.metadata.get("tier") == "exhausted"


@pytest.mark.asyncio
async def test_residual_recursion_aborts_when_less_than_two_minutes_remain(monkeypatch):
    events = []

    class ShortWall(ResidualTrackingPolicy):
        async def solve(self, problem, services):
            import submission.agent as agent_mod

            monkeypatch.setattr(agent_mod, "_time_budget_s", lambda: 90.0)
            return await SubmissionAgent.solve(self, problem, services)

    policy = ShortWall(events, residual_result=AgentResult("nope", {}))
    calls = []

    async def track(problem, services, time_left, *, open_blocks):
        remaining = time_left()
        calls.append(remaining)
        return await SubmissionAgent._residual_recursion(
            policy, problem, services, time_left, open_blocks=open_blocks
        )

    policy._residual_recursion = track  # type: ignore[method-assign]
    problem = Problem(id="generic_multi", description="prove both", challenge=MULTI)
    result = await policy.solve(problem, FakeServices())

    assert calls, "residual entry expected"
    assert calls[0] < 120
    assert result.metadata["tier"] == "exhausted"
    assert result.metadata["accepted_by_repl"] is False


def test_integrity_rejects_an_unfolded_or_rewritten_theorem_statement():
    rewritten = """import Mathlib

abbrev computed_answer : Nat := 4

theorem dependent_target : 2 + 2 = 4 := by
  norm_num
"""

    # Inner slot search may keep the elaborating body long enough for the host to graft
    # it, but final acceptance must reject the rewritten exported type.
    assert integrity_check(rewritten, DEPENDENT) == (True, [])
    accepted, errors = strict_integrity_check(rewritten, DEPENDENT)

    assert accepted is False
    assert errors == [
        "changed required declaration signature `dependent_target`"
    ]


@pytest.mark.asyncio
async def test_solution_guard_rejects_rewritten_signatures_before_circularity():
    """Production finish path must not treat an unfolded theorem as substantive."""

    class _FakeLean:
        async def check_file(self, *_a, **_k):  # pragma: no cover - should not run
            raise AssertionError("circularity probe must not run after signature fail")

    class _Services:
        def __init__(self):
            self.lean = _FakeLean()

    from experiments_agents.candidate_guard import validate_solution_candidate

    rewritten = """import Mathlib

abbrev computed_answer : Nat := 4

theorem dependent_target : 2 + 2 = 4 := by
  norm_num
"""
    problem = Problem(
        id="generic_dep",
        description="compute it",
        challenge=DEPENDENT,
        metadata={
            "__manifest__": {
                "definition_names": ["computed_answer"],
                "numeric_answer_names": ["computed_answer"],
                "theorem_names": ["dependent_target"],
            }
        },
    )
    guard = await validate_solution_candidate(problem, _Services(), rewritten)
    assert guard.accepted is False
    assert any("signature" in err for err in guard.errors)


def test_slot_rhs_is_grafted_under_the_original_machine_owned_header():
    _preamble, original_blocks = split_declarations(DEPENDENT)
    answer_block, theorem_block = original_blocks
    answer_candidate = """import Mathlib

abbrev computed_answer : Nat := 4
"""
    theorem_candidate = """import Mathlib

abbrev computed_answer : Nat := 4

lemma useful_helper : True := by
  trivial

theorem dependent_target : 2 + 2 = 4 := by
  norm_num
"""
    names = {"computed_answer", "dependent_target"}

    locked_answer = _locked_slot_body(answer_block, answer_candidate, names)
    locked_theorem = _locked_slot_body(theorem_block, theorem_candidate, names)
    assembled = f"import Mathlib\n\n{locked_answer}\n\n{locked_theorem}\n"

    assert "theorem dependent_target : 2 + 2 = computed_answer := by" in assembled
    assert "theorem dependent_target : 2 + 2 = 4" not in assembled
    assert "lemma useful_helper : True" in assembled
    assert assembled.count("abbrev computed_answer") == 1
    assert strict_integrity_check(assembled, DEPENDENT) == (True, [])
