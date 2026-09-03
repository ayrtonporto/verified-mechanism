"""Offline tests: Putnam-shaped tautologies must not pass the final guard."""

from __future__ import annotations

import pytest

from experiments_agents.candidate_guard import (
    challenge_definition_names,
    resolve_answer_definition_names,
    structurally_circular_definition,
    validate_solution_candidate,
)
from experiments_agents.multitheorem import split_declarations
from re_harness import Problem


PUTNAM_2018_CHALLENGE = """import Mathlib

abbrev putnam_2018_a1_solution : Set (ℤ × ℤ) := by
  sorry

theorem putnam_2018_a1
  (a b : ℤ)
  (h : 0 < a ∧ 0 < b) :
  ((1 : ℚ) / a + (1 : ℚ) / b = (3 : ℚ) / 2018) ↔
    (⟨a, b⟩ ∈ putnam_2018_a1_solution) := by
  sorry
"""

PUTNAM_2018_TAUT = """import Mathlib.Tactic

abbrev putnam_2018_a1_solution : Set (ℤ × ℤ) :=
  {p | (0 : ℤ) < p.1 ∧ (0 : ℤ) < p.2 ∧
        ((1 : ℚ) / p.1 + (1 : ℚ) / p.2 = (3 : ℚ) / 2018)}

theorem putnam_2018_a1
  (a b : ℤ)
  (h : 0 < a ∧ 0 < b) :
  ((1 : ℚ) / a + (1 : ℚ) / b = (3 : ℚ) / 2018) ↔
    (⟨a, b⟩ ∈ putnam_2018_a1_solution) := by
  change ((1 : ℚ) / a + (1 : ℚ) / b = (3 : ℚ) / 2018) ↔
        (0 < a ∧ 0 < b ∧ ((1 : ℚ) / a + (1 : ℚ) / b = (3 : ℚ) / 2018))
  constructor
  · intro h_eq
    exact ⟨h.1, h.2, h_eq⟩
  · intro h_mem
    exact h_mem.2.2
"""

PUTNAM_2020_CHALLENGE = """import Mathlib

abbrev putnam_2020_a2_solution : ℕ → ℕ := by
  sorry

theorem putnam_2020_a2
  (k : ℕ) :
  (∑ j ∈ Finset.Icc 0 k, 2 ^ (k - j) * Nat.choose (k + j) j) =
    putnam_2020_a2_solution k := by
  sorry
"""

PUTNAM_2020_TAUT = """import Mathlib

open Finset

abbrev putnam_2020_a2_solution : ℕ → ℕ :=
  fun k => ∑ j ∈ Icc 0 k, 2 ^ (k - j) * Nat.choose (k + j) j

theorem putnam_2020_a2
  (k : ℕ) :
  (∑ j ∈ Finset.Icc 0 k, 2 ^ (k - j) * Nat.choose (k + j) j) =
    putnam_2020_a2_solution k := by
  rfl
"""


class _NoLean:
    async def check_file(self, *_a, **_k):  # pragma: no cover
        raise AssertionError("structural reject must not need Lean")


class _Services:
    def __init__(self):
        self.lean = _NoLean()


def test_challenge_definition_names_infers_abbrevs():
    names = challenge_definition_names(PUTNAM_2018_CHALLENGE)
    assert "putnam_2018_a1_solution" in names
    names2 = challenge_definition_names(PUTNAM_2020_CHALLENGE)
    assert "putnam_2020_a2_solution" in names2


def test_resolve_defs_when_manifest_empty():
    problem = Problem(
        id="p",
        description="d",
        challenge=PUTNAM_2018_CHALLENGE,
        metadata={"__manifest__": {"definition_names": [], "numeric_answer_names": []}},
    )
    decls = challenge_definition_names(PUTNAM_2018_CHALLENGE)
    defs, nums = resolve_answer_definition_names(problem, challenge_decl_names=decls)
    assert "putnam_2018_a1_solution" in defs
    assert not nums


def test_structural_set_builder_tautology():
    _pre, blocks = split_declarations(PUTNAM_2018_TAUT)
    by_name = {}
    thms = []
    from experiments_agents.candidate_guard import _info

    for b in blocks:
        info = _info(b)
        if info is None:
            continue
        if info[0] in {"def", "abbrev"}:
            by_name[info[1]] = b
        if info[0] in {"theorem", "lemma"}:
            thms.append(b)
    err = structurally_circular_definition(
        "putnam_2018_a1_solution", by_name["putnam_2018_a1_solution"], thms
    )
    assert err is not None
    assert "tautolog" in err.lower() or "set-builder" in err.lower()


def test_structural_lambda_rfl_tautology():
    _pre, blocks = split_declarations(PUTNAM_2020_TAUT)
    from experiments_agents.candidate_guard import _info

    by_name = {}
    thms = []
    for b in blocks:
        info = _info(b)
        if info is None:
            continue
        if info[0] in {"def", "abbrev"}:
            by_name[info[1]] = b
        if info[0] in {"theorem", "lemma"}:
            thms.append(b)
    err = structurally_circular_definition(
        "putnam_2020_a2_solution", by_name["putnam_2020_a2_solution"], thms
    )
    assert err is not None
    assert "tautolog" in err.lower() or "lambda" in err.lower()


@pytest.mark.asyncio
async def test_guard_rejects_putnam2018_tautology_with_empty_manifest():
    """Overnight failure mode: empty definition_names must NOT skip the probe."""

    problem = Problem(
        id="putnam_2018_a1",
        description="find pairs",
        challenge=PUTNAM_2018_CHALLENGE,
        metadata={
            "__manifest__": {
                "theorem_names": ["putnam_2018_a1"],
                "definition_names": [],
                "numeric_answer_names": [],
            }
        },
    )
    guard = await validate_solution_candidate(problem, _Services(), PUTNAM_2018_TAUT)
    assert guard.accepted is False
    assert guard.errors
    assert any("tautolog" in e.lower() or "set-builder" in e.lower() for e in guard.errors)


@pytest.mark.asyncio
async def test_guard_rejects_putnam2020_lambda_rfl_with_empty_manifest():
    problem = Problem(
        id="putnam_2020_a2",
        description="sum",
        challenge=PUTNAM_2020_CHALLENGE,
        metadata={
            "__manifest__": {
                "theorem_names": ["putnam_2020_a2"],
                "definition_names": [],
                "numeric_answer_names": [],
            }
        },
    )
    guard = await validate_solution_candidate(problem, _Services(), PUTNAM_2020_TAUT)
    assert guard.accepted is False
    assert guard.errors
    blob = " ".join(guard.errors).lower()
    assert "tautolog" in blob or "lambda" in blob or "definitional" in blob


@pytest.mark.asyncio
async def test_finish_path_does_not_return_putnam_tautology_as_pass(monkeypatch):
    """Submission finish() must fall through after guard reject (no false PASS)."""

    from submission.agent import SubmissionAgent
    from re_harness import AgentResult

    events = []

    class Pol(SubmissionAgent):
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
            events.append("champion")
            return PUTNAM_2018_TAUT, "champion_r_g"

        async def _solve_slot(self, *a, **k):
            events.append("fallback")
            return None

        async def _residual_recursion(self, *a, **k):
            events.append("residual")
            self._residual_rounds_ran = 1
            self._greedy_close_attempted = 1
            self._residual_fail_kind = "def_circular"
            self._lab_notebook.add("final_guard reject historical_champion")
            return None

    import submission.agent as am

    monkeypatch.setattr(am, "_time_budget_s", lambda: 900.0)

    class S:
        llm = object()
        lean = _NoLean()

        def checkpoint(self, *a, **k):
            pass

    problem = Problem(
        id="putnam_2018_a1",
        description="find pairs",
        challenge=PUTNAM_2018_CHALLENGE,
        metadata={
            "__manifest__": {
                "theorem_names": ["putnam_2018_a1"],
                "definition_names": [],
                "numeric_answer_names": [],
            }
        },
    )
    result = await Pol().solve(problem, S())
    assert "champion" in events
    assert "residual" in events
    assert result.metadata.get("tier") == "exhausted"
    assert result.metadata.get("accepted_by_repl") is False
    assert result.metadata.get("substantive_closure") is False
