"""Unit tests for Phase E failure routing (no Lean, no problem ids)."""

from __future__ import annotations

from types import SimpleNamespace

from experiments_agents.error_router import (
    classify_failure_text,
    classify_stage_report,
    preferred_residual_mode,
    problem_looks_answer_shaped,
)


def test_classify_failure_text_priority_and_labels():
    assert classify_failure_text("circular definition rejected") == "def_circular"
    assert (
        classify_failure_text("changed required declaration signature")
        == "signature_rewrite"
    )
    assert classify_failure_text("unknown identifier foo") == "syntax_name"
    assert classify_failure_text("unsolved goals\nnlinarith") == "needs_lemma"
    assert classify_failure_text("portfolio_exhausted") == "goal_stuck"
    assert classify_failure_text("") == "other"
    assert classify_failure_text("something vague") == "other"
    # first match wins: circular beats later exhausted noise
    assert (
        classify_failure_text("exhausted after circular definitional probe")
        == "def_circular"
    )


def test_classify_stage_report_reads_detail():
    assert (
        classify_stage_report(
            {"stage": "verified_progress_program", "detail": "tautological answer"}
        )
        == "def_circular"
    )
    assert classify_stage_report(None) == "other"


def test_preferred_residual_mode_maps_kinds():
    assert preferred_residual_mode("def_circular") == "program"
    assert preferred_residual_mode("signature_rewrite") == "program"
    assert preferred_residual_mode("needs_lemma") == "bridge"
    assert preferred_residual_mode("goal_stuck") == "bridge"
    assert preferred_residual_mode("syntax_name") == "bridge"
    assert preferred_residual_mode("other") == "either"


def test_problem_looks_answer_shaped_from_manifest_and_structure():
    bare = SimpleNamespace(challenge="theorem t : True := by sorry", metadata={})
    assert problem_looks_answer_shaped(bare) is False

    with_manifest = SimpleNamespace(
        challenge="theorem t : True := by sorry",
        metadata={"__manifest__": {"definition_names": ["solution"], "numeric_answer_names": []}},
    )
    assert problem_looks_answer_shaped(with_manifest) is True

    structural = SimpleNamespace(
        challenge=(
            "import Mathlib\n\n"
            "def solution : Set ℕ := sorry\n\n"
            "theorem characterisation : True := by sorry\n"
        ),
        metadata={},
    )
    assert problem_looks_answer_shaped(structural) is True
