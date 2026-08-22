from __future__ import annotations

import json
from datetime import datetime

from re_harness.config import HarnessSettings
from re_harness.runner import resolve_output_dir, run


def _make_set(root):
    entries = []
    for problem_id in ("p1", "p2"):
        directory = root / problem_id
        directory.mkdir(parents=True)
        (directory / "problem.md").write_text("Show True.")
        (directory / "challenge.lean").write_text(
            f"import Mathlib\n\ntheorem {problem_id} : True := by\n  sorry\n"
        )
        entries.append({
            "id": problem_id,
            "theorem_names": [problem_id],
            "definition_names": [],
            "numeric_answer_names": [],
            "metadata": {"sleep_s": 0.3},
        })
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "set": "two", "problems": entries
    }))


def test_n_workers_runs_isolated_problem_processes_and_writes_contract(tmp_path):
    problems = tmp_path / "problems"
    out = tmp_path / "outputs"
    _make_set(problems)
    (out / "p1").mkdir(parents=True)
    (out / "p1" / "events.jsonl").write_text('{"event":"stale"}\n')
    (out / "p1" / "result.json").write_text('{"passed":true}\n')
    settings = HarnessSettings(
        api_key="",
        lean_image="example.invalid/missing:never",
        budget_usd=1.0,
        time_limit_s=5.0,
        n_workers=2,
        lean_check_timeout_s=1,
        comparator_timeout_s=1,
        verify_reserve_s=1,
    )
    summary = run(
        problems_dir=problems,
        out_dir=out,
        settings=settings,
        agent="tests.fixture_agent:create_agent",
    )
    assert summary["max_points"] == 2
    assert (out / "run.json").exists()
    assert (out / "summary.json").exists()
    starts = []
    sessions = []
    for problem_id in ("p1", "p2"):
        problem_out = out / problem_id
        for name in ("solution.lean", "result.json", "transcript.json", "events.jsonl"):
            assert (problem_out / name).exists()
        config = json.loads((problem_out / "worker-config.json").read_text())
        assert "api_key" not in config
        sessions.append(config["session_id"])
        events = [json.loads(line) for line in (problem_out / "events.jsonl").read_text().splitlines()]
        assert all(event.get("event") != "stale" for event in events)
        started = next(event for event in events if event["event"] == "problem_started")
        starts.append(datetime.fromisoformat(started["timestamp"]))
    assert sessions[0] != sessions[1]
    assert abs((starts[0] - starts[1]).total_seconds()) < 0.3


def test_resume_latest_finds_renamed_nested_run(tmp_path):
    root = tmp_path / "outputs"
    run_dir = root / "baseline" / "qwen" / "qwen3.5-flash-02-23"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text("{}")

    resolved, agent_name, run_name, resume = resolve_output_dir(
        root,
        agent="baselines.simple_agent:create_agent",
        resume="latest",
    )

    assert resolved == run_dir
    assert agent_name == "baseline"
    assert run_name == "qwen/qwen3.5-flash-02-23"
    assert resume is True
