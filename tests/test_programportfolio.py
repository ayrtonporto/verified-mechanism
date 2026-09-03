from __future__ import annotations

import json
import re

import pytest

from experiments_agents.candidate_guard import validate_solution_candidate
from experiments_agents.programportfolio import (
    DefinitionPortfolio,
    DefinitionStats,
    ProgramPortfolioAgent,
    _replace_single_sorry,
    declaration_info,
    parse_definition_candidates,
)
from experiments_agents.multitheorem import split_declarations
from re_harness import AgentResult, Problem


DEPENDENT_CHALLENGE = """import Mathlib

/-- Must be a numeric literal. -/
abbrev answer : ℕ := sorry

theorem answer_is_correct : answer = 49 := by
  sorry
"""


SIBLING_CHALLENGE = """import Mathlib

theorem hard_part : True := by
  sorry

theorem helper_part : True := by
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
            raise AssertionError("unexpected LLM request")
        return FakeResponse(self.responses.pop(0))


class FakeCheck:
    def __init__(self, accepted: bool, message: str = "unsolved goals"):
        self.accepted = accepted
        self.has_sorry = False
        self.timed_out = False
        self.messages = [] if accepted else [{"severity": "error", "data": message}]


class NoSorryLean:
    def __init__(self):
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        return FakeCheck("sorry" not in source)


class TransparentMembershipLean:
    """Accept only the stronger, name-agnostic membership-normalisation probe."""

    def __init__(self):
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        accepted = (
            "change _ ↔ answer _" in source
            and "unfold answer" in source
            and "simp_all [one_div]" in source
        )
        return FakeCheck(accepted)


class CircularOnlyProbeLean:
    """Elaborate candidates, but close semantic probes only for predicate copies."""

    def __init__(self):
        self.sources: list[str] = []

    async def check_file(self, source: str, timeout_s=None):
        self.sources.append(source)
        is_probe = "change _ ↔ answer _" in source
        if is_probe:
            return FakeCheck("p.1 + p.2 = 17" in source)
        return FakeCheck("sorry" not in source)


class FakeServices:
    def __init__(self, llm=None, lean=None):
        self.llm = llm or FakeLLM([])
        self.lean = lean or NoSorryLean()
        self.checkpoints: list[tuple[str, dict]] = []

    def checkpoint(self, source, metadata=None):
        self.checkpoints.append((source, metadata or {}))


class FixedDefinitionPortfolio:
    def __init__(self, replacements: dict[str, list[str]]):
        self.replacements = replacements
        self.stats = DefinitionStats()

    async def solve(
        self, problem, services, *, preamble, context_blocks, block, time_left,
        dependent_blocks=None,
    ):
        info = declaration_info(block)
        assert info is not None
        solved = []
        for replacement in self.replacements.get(info[1], []):
            candidate = _replace_single_sorry(block, replacement)
            assert candidate is not None
            solved.append(candidate)
        self.stats.proposed += len(solved)
        self.stats.accepted += len(solved)
        return solved


def _solve_last_hole(challenge: str, body: str = "trivial") -> str:
    matches = list(re.finditer(r"\bsorry\b", challenge))
    assert matches
    hole = matches[-1]
    return challenge[: hole.start()] + body + challenge[hole.end() :]


class DependencyTheoremAgent:
    def __init__(self, attempts: list[tuple[str, str]]):
        self.attempts = attempts

    async def solve(self, problem, services):
        name = "answer_is_correct"
        self.attempts.append((name, problem.challenge))
        ok = "abbrev answer : ℕ := 49" in problem.challenge
        solution = _solve_last_hole(problem.challenge) if ok else problem.challenge
        return AgentResult(solution, {
            "accepted_by_repl": ok,
            "calls_q": 0,
            "calls_g": 0,
            "lean_checks": 1,
        })


class SiblingTheoremAgent:
    def __init__(self, attempts: list[tuple[str, str]]):
        self.attempts = attempts

    async def solve(self, problem, services):
        name = "hard_part" if "theorem hard_part" in problem.challenge.split("sorry")[-2] else "helper_part"
        # The current theorem is always the final declaration in the mini program.
        current = re.findall(r"theorem\s+([A-Za-z_][A-Za-z0-9_]*)", problem.challenge)[-1]
        self.attempts.append((current, problem.challenge))
        ok = current == "helper_part" or (
            current == "hard_part"
            and "theorem helper_part : True := by\n  trivial" in problem.challenge
        )
        solution = _solve_last_hole(problem.challenge) if ok else problem.challenge
        return AgentResult(solution, {
            "accepted_by_repl": ok,
            "calls_q": 0,
            "calls_g": 0,
            "lean_checks": 1,
        })


def test_definition_candidate_parser_enforces_literal_contract_and_locked_hole():
    response = json.dumps({
        "candidates": [
            {"replacement": "7 ^ 2"},
            {"replacement": "49"},
            {"replacement": "49"},
        ]
    })
    assert parse_definition_candidates(response, numeric=True, maximum=4) == ["49"]
    block = "abbrev solution : Set ℕ := by\n  sorry\n"
    solved = _replace_single_sorry(block, "exact {1, 2}")
    assert solved == "abbrev solution : Set ℕ := by\n  exact {1, 2}\n"


def test_definition_graft_strips_only_redundant_owned_by_wrapper():
    direct = "abbrev solution : Set ℕ := by\n  sorry\n"
    assert _replace_single_sorry(direct, "by\n  exact {1, 2}") == (
        "abbrev solution : Set ℕ := by\n  exact {1, 2}\n"
    )
    assert _replace_single_sorry(direct, "({1, 2} : Set ℕ)") == (
        "abbrev solution : Set ℕ := by\n  exact (({1, 2} : Set ℕ))\n"
    )

    nested = "abbrev answer : ℕ := by\n  exact (sorry : ℕ)\n"
    assert "by\n" in (_replace_single_sorry(nested, "by\n  exact 7") or "")


@pytest.mark.asyncio
async def test_real_definition_portfolio_grafts_only_a_verified_numeric_literal():
    problem = Problem(
        id="answer",
        description="Find the answer. It must be a numeric literal.",
        challenge="import Mathlib\n\nabbrev answer : ℕ := sorry\n",
        metadata={"__manifest__": {"numeric_answer_names": ["answer"]}},
    )
    response = json.dumps({"candidates": [
        {"replacement": "7 ^ 2"},
        {"replacement": "49"},
    ]})
    services = FakeServices(llm=FakeLLM([response]), lean=NoSorryLean())
    portfolio = DefinitionPortfolio(
        portfolio_calls=1, max_candidates=4, max_accepted=2, check_timeout_s=10
    )

    solved = await portfolio.solve(
        problem,
        services,
        preamble="import Mathlib\n",
        context_blocks=[],
        block="abbrev answer : ℕ := sorry\n",
        time_left=lambda: 1000,
    )

    assert len(solved) == 1
    assert "abbrev answer : ℕ := 49" in solved[0]
    assert portfolio.stats.accepted == 1


@pytest.mark.asyncio
async def test_definition_portfolio_rejects_tautological_solution_set():
    challenge = """import Mathlib

abbrev answer : Set (ℤ × ℤ) := by
  sorry

theorem characterise (a b : ℤ) :
    ((1 : ℚ) / a + (1 : ℚ) / b = 3 / 2018) ↔ ((a, b) ∈ answer) := by
  sorry
"""
    circular = (
        "exact {p : ℤ × ℤ | "
        "((1 : ℚ) / p.1 + (1 : ℚ) / p.2 = 3 / 2018)}"
    )
    problem = Problem(
        id="generic_characterisation",
        description="Compute a closed solution set.",
        challenge=challenge,
        metadata={
            "__manifest__": {
                "definition_names": ["answer"],
                "numeric_answer_names": [],
            }
        },
    )
    _pre, blocks = split_declarations(challenge)
    response = json.dumps({"candidates": [{"replacement": circular}]})
    services = FakeServices(llm=FakeLLM([response]), lean=NoSorryLean())
    portfolio = DefinitionPortfolio(
        portfolio_calls=1, max_candidates=2, max_accepted=1, check_timeout_s=10,
        canonical_retry_calls=0,
    )

    solved = await portfolio.solve(
        problem,
        services,
        preamble="import Mathlib\n",
        context_blocks=[],
        block=blocks[0],
        dependent_blocks=[blocks[1]],
        time_left=lambda: 1000,
    )

    assert solved == []
    assert portfolio.stats.rejected_circular == 1


@pytest.mark.asyncio
async def test_definition_portfolio_canonicalizes_after_circular_rejection():
    challenge = """import Mathlib

abbrev answer : Set (ℤ × ℤ) := by
  sorry

theorem characterise (a b : ℤ) :
    (a + b = 17) ↔ ((a, b) ∈ answer) := by
  sorry
"""
    circular = "exact fun p => p.1 + p.2 = 17"
    canonical = "exact {(8, 9), (9, 8)}"
    response = lambda replacement: json.dumps({
        "candidates": [{"replacement": replacement}]
    })
    llm = FakeLLM([
        response(circular),  # initial portfolio
        response(circular),  # ordinary syntax/semantic repair
        response(canonical),  # canonicalization round
    ])
    lean = CircularOnlyProbeLean()
    problem = Problem(
        id="generic_finite_characterisation",
        description="Compute the finite answer extensionally.",
        challenge=challenge,
        metadata={"__manifest__": {
            "definition_names": ["answer"],
            "numeric_answer_names": [],
        }},
    )
    _pre, blocks = split_declarations(challenge)
    portfolio = DefinitionPortfolio(
        portfolio_calls=1,
        max_candidates=3,
        max_accepted=1,
        check_timeout_s=10,
        canonical_retry_calls=1,
    )

    solved = await portfolio.solve(
        problem,
        FakeServices(llm=llm, lean=lean),
        preamble="import Mathlib\n",
        context_blocks=[],
        block=blocks[0],
        dependent_blocks=[blocks[1]],
        time_left=lambda: 1000,
    )

    assert len(solved) == 1
    assert "{(8, 9), (9, 8)}" in solved[0]
    assert portfolio.stats.rejected_circular == 2
    assert portfolio.stats.canonical_retry_calls == 1
    assert "Downstream immutable characterisations" in llm.requests[-1]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_final_candidate_guard_rejects_putnam_style_definitional_pass():
    challenge = """import Mathlib

abbrev answer : Set (ℤ × ℤ) := by
  sorry

theorem characterise (a b : ℤ) :
    (a + b = 17) ↔ ((a, b) ∈ answer) := by
  sorry
"""
    candidate = """import Mathlib

abbrev answer : Set (ℤ × ℤ) := {p | p.1 + p.2 = 17}

theorem characterise (a b : ℤ) :
    (a + b = 17) ↔ ((a, b) ∈ answer) := by
  rfl
"""
    problem = Problem(
        id="generic_characterisation",
        description="Compute the solution set.",
        challenge=challenge,
        metadata={
            "__manifest__": {
                "definition_names": ["answer"],
                "numeric_answer_names": [],
            }
        },
    )

    guard = await validate_solution_candidate(
        problem, FakeServices(lean=NoSorryLean()), candidate
    )

    assert guard.accepted is False
    assert "tautological" in guard.errors[0]


@pytest.mark.asyncio
async def test_final_guard_rejects_inverse_and_positivity_reformulation():
    challenge = """import Mathlib

abbrev answer : Set (ℤ × ℤ) := by
  sorry

theorem characterise (a b : ℤ) (h : 0 < a ∧ 0 < b) :
    ((1 : ℚ) / a + (1 : ℚ) / b = (3 : ℚ) / 37) ↔
      ((a, b) ∈ answer) := by
  sorry
"""
    candidate = """import Mathlib

abbrev answer : Set (ℤ × ℤ) := by
  exact fun p => p.1 > 0 ∧ p.2 > 0 ∧
    ((p.1 : ℚ)⁻¹ + (p.2 : ℚ)⁻¹ = (3 : ℚ) / 37)

theorem characterise (a b : ℤ) (h : 0 < a ∧ 0 < b) :
    ((1 : ℚ) / a + (1 : ℚ) / b = (3 : ℚ) / 37) ↔
      ((a, b) ∈ answer) := by
  constructor <;> intro hx
  · exact ⟨h.1, h.2, by simpa [one_div] using hx⟩
  · simpa [one_div] using hx.2.2
"""
    problem = Problem(
        id="generic_inverse_characterisation",
        description="Compute a closed solution set.",
        challenge=challenge,
        metadata={"__manifest__": {
            "definition_names": ["answer"],
            "numeric_answer_names": [],
        }},
    )
    lean = TransparentMembershipLean()

    guard = await validate_solution_candidate(
        problem, FakeServices(lean=lean), candidate
    )

    assert guard.accepted is False
    assert guard.lean_checks == 1
    assert "tautological" in guard.errors[0]
    assert any("change _ ↔ answer _" in source for source in lean.sources)


@pytest.mark.asyncio
async def test_program_coordinator_solves_definition_before_dependent_theorem():
    attempts: list[tuple[str, str]] = []
    services = FakeServices()
    agent = ProgramPortfolioAgent(
        definition_portfolio=FixedDefinitionPortfolio({"answer": ["49"]}),
        theorem_factory=lambda _time_left: DependencyTheoremAgent(attempts),
        max_definition_states=2,
        theorem_passes=2,
        reserve_s=0,
    )
    problem = Problem(
        id="dependent",
        description="Find and prove the numeric answer.",
        challenge=DEPENDENT_CHALLENGE,
        metadata={"__manifest__": {"numeric_answer_names": ["answer"]}},
    )

    result = await agent.solve(problem, services)

    assert result.metadata["accepted_by_repl"] is True
    assert result.metadata["substantive_closure"] is True
    assert "abbrev answer : ℕ := 49" in result.solution
    assert "theorem answer_is_correct : answer = 49 := by\n  trivial" in result.solution
    assert "sorry" not in result.solution
    assert len(attempts) == 1
    assert len(services.checkpoints) == 1


@pytest.mark.asyncio
async def test_program_coordinator_retries_failed_theorem_after_sibling_solves():
    attempts: list[tuple[str, str]] = []
    services = FakeServices()
    agent = ProgramPortfolioAgent(
        definition_portfolio=FixedDefinitionPortfolio({}),
        theorem_factory=lambda _time_left: SiblingTheoremAgent(attempts),
        theorem_passes=2,
        reserve_s=0,
    )
    problem = Problem(
        id="siblings",
        description="Prove two related parts.",
        challenge=SIBLING_CHALLENGE,
    )

    result = await agent.solve(problem, services)

    assert result.metadata["accepted_by_repl"] is True
    assert [name for name, _source in attempts] == [
        "hard_part", "helper_part", "hard_part"
    ]
    assert "sorry" not in result.solution
    assert result.metadata["theorem_solved"] == 2
