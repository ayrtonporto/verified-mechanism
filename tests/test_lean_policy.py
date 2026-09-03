from __future__ import annotations

from re_harness.lean import _hardened_docker_args, numeric_answers_are_literals


def test_container_arguments_enforce_boundary_and_contain_no_key():
    argv = _hardened_docker_args(
        session_id="a" * 32, name="test", image="example.invalid/image@sha256:" + "b" * 64
    )
    joined = " ".join(argv)
    assert "--network=none" in argv
    assert "--read-only" in argv
    assert "--cap-drop=ALL" in joined
    assert "no-new-privileges=true" in argv
    assert "OPENROUTER" not in joined
    assert "Authorization" not in joined
    assert "-v" not in argv and "--volume" not in argv


def test_numeric_answers_reject_expressions_and_comments():
    name = ("answer",)
    assert numeric_answers_are_literals("abbrev answer : ℕ := 49\ntheorem x : True := by trivial", name)[0]
    assert not numeric_answers_are_literals(
        "abbrev answer : ℕ := 7 ^ 2\ntheorem x : True := by trivial", name
    )[0]
    assert not numeric_answers_are_literals(
        "-- abbrev answer : ℕ := 49\nabbrev answer : ℕ := 7 ^ 2", name
    )[0]
    assert not numeric_answers_are_literals(
        "abbrev answer : ℕ := 49 + 0\ntheorem x : True := by trivial", name
    )[0]
