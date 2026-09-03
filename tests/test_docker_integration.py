from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest

from experiments_agents.candidate_guard import validate_solution_candidate
from experiments_agents.bridgeportfolio import build_goal_source
from re_harness import Problem, Services
from re_harness.events import EventLogger
from re_harness.config import HarnessSettings
from re_harness.lean import LeanClient, compare_solution
from re_harness.manifest import ProblemSpec
from re_harness.runner import run


IMAGE = os.environ.get("LEAN_INTEGRATION_IMAGE")
pytestmark = pytest.mark.skipif(not IMAGE, reason="set LEAN_INTEGRATION_IMAGE to test Docker")


def test_real_repl_valid_invalid_timeout_and_restart(tmp_path):
    async def exercise() -> None:
        client = LeanClient(
            image=IMAGE or "",
            events=EventLogger(tmp_path / "events.jsonl", problem_id="integration"),
            timeout_s=5,
        )
        try:
            valid = await client.check_file(
                "import Mathlib\n\ntheorem repl_ok : True := by exact True.intro"
            )
            assert valid.accepted
            invalid = await client.check_file(
                "import Mathlib\n\ntheorem repl_bad : False := by trivial"
            )
            assert not invalid.accepted
            runaway = await client.check_file(
                "import Mathlib\n\nrun_cmd IO.sleep 60000", timeout_s=1
            )
            assert runaway.timed_out
            recovered = await client.check_file(
                "import Mathlib\n\ntheorem repl_recovered : True := by exact True.intro"
            )
            assert recovered.accepted and recovered.container_restarted
        finally:
            client.close()

    asyncio.run(exercise())


def test_real_guard_rejects_transparently_rephrased_solution_set(tmp_path):
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

    async def exercise() -> None:
        client = LeanClient(
            image=IMAGE or "",
            events=EventLogger(tmp_path / "guard-events.jsonl", problem_id="guard"),
            timeout_s=45,
        )
        try:
            problem = Problem(
                id="generic_inverse_characterisation",
                description="Compute a closed solution set.",
                challenge=challenge,
                metadata={"__manifest__": {
                    "definition_names": ["answer"],
                    "numeric_answer_names": [],
                }},
            )
            result = await validate_solution_candidate(
                problem,
                Services(llm=None, lean=client, checkpoint=lambda *_a, **_k: None),
                candidate,
                timeout_s=45,
            )
            assert not result.accepted
            assert "tautological" in result.errors[0]
        finally:
            client.close()

    asyncio.run(exercise())


def test_real_generated_goal_rejects_free_autoimplicit_names(tmp_path):
    challenge = """import Mathlib

theorem locked (n : ℕ) : n = n := by
  sorry
"""
    source = build_goal_source(
        challenge,
        extra_hypotheses=[("bp_d0_1", "(u : ℤ) = u")],
        goal_override="True",
        proof_body="trivial",
    )
    assert source is not None

    async def exercise() -> None:
        client = LeanClient(
            image=IMAGE or "",
            events=EventLogger(tmp_path / "implicit-events.jsonl", problem_id="implicit"),
            timeout_s=45,
        )
        try:
            result = await client.check_file(source, timeout_s=45)
            assert not result.accepted
            assert any("Unknown identifier `u`" in str(message.get("data", ""))
                       for message in result.messages)
        finally:
            client.close()

    asyncio.run(exercise())


def test_real_comparator_accepts_proof_and_rejects_statement_or_axiom():
    spec = ProblemSpec("smoke", ("smoke",), (), (), {})
    challenge = "import Mathlib\n\ntheorem smoke : True := by sorry\n"
    accepted = compare_solution(
        image=IMAGE or "",
        session_id=uuid.uuid4().hex,
        challenge=challenge,
        solution="import Mathlib\n\ntheorem smoke : True := by exact True.intro\n",
        spec=spec,
        timeout_s=180,
    )
    assert accepted.passed
    changed = compare_solution(
        image=IMAGE or "",
        session_id=uuid.uuid4().hex,
        challenge=challenge,
        solution="import Mathlib\n\ntheorem smoke : 1 = 1 := by rfl\n",
        spec=spec,
        timeout_s=180,
    )
    assert not changed.passed
    axiom = compare_solution(
        image=IMAGE or "",
        session_id=uuid.uuid4().hex,
        challenge=challenge,
        solution=(
            "import Mathlib\n\naxiom forbidden : False\n"
            "theorem smoke : True := False.elim forbidden\n"
        ),
        spec=spec,
        timeout_s=180,
    )
    assert not axiom.passed


def _one_problem_set(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "sample-problems" / "p01_linear"
    root = tmp_path / "problems"
    problem = root / "p01_linear"
    problem.mkdir(parents=True)
    for name in ("problem.md", "challenge.lean"):
        (problem / name).write_bytes((source / name).read_bytes())
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "set": "integration",
        "problems": [{
            "id": "p01_linear",
            "theorem_names": ["p01_linear"],
            "definition_names": [],
            "numeric_answer_names": [],
        }],
    }))
    return root


def test_real_worker_scores_checkpoint_after_agent_crash(tmp_path):
    problems = _one_problem_set(tmp_path)
    summary = run(
        problems_dir=problems,
        out_dir=tmp_path / "out-crash",
        settings=HarnessSettings("", IMAGE or "", 1.0, 60, 1, 5, 60, 10),
        agent="tests.fixture_agent:create_checkpoint_crash_agent",
    )
    assert summary["total_points"] == 1


def test_outer_hard_timeout_preserves_checkpoint_and_cleans_container(tmp_path):
    problems = _one_problem_set(tmp_path)
    out = tmp_path / "out-timeout"
    run(
        problems_dir=problems,
        out_dir=out,
        settings=HarnessSettings("", IMAGE or "", 1.0, 3, 1, 5, 20, 1),
        agent="tests.fixture_agent:create_hard_hang_agent",
    )
    result = json.loads((out / "p01_linear" / "result.json").read_text())
    assert result["status"] == "timed_out"
    assert "linarith" in (out / "p01_linear" / "solution.lean").read_text()
