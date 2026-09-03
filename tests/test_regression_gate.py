from __future__ import annotations

import json

from scripts.regression_gate import collect, markdown


def test_regression_gate_reports_comparator_substance_cost_and_stage(tmp_path):
    problem = tmp_path / "generic"
    problem.mkdir()
    (problem / "result.json").write_text(json.dumps({
        "problem_id": "generic",
        "comparator": {"passed": True},
        "wall_s": 12.5,
        "budget": {"spent_usd": 0.004},
        "agent_metadata": {
            "substantive_closure": True,
            "stage_winner": "champion_r_q",
            "progress_graph": {"nodes_saved": 2, "nodes_reused": 1},
        },
    }), encoding="utf-8")
    (problem / "events.jsonl").write_text(
        "\n".join([
            json.dumps({"event": "llm_request"}),
            json.dumps({"event": "lean_check"}),
            json.dumps({"event": "lean_check"}),
        ]) + "\n",
        encoding="utf-8",
    )

    rows = collect(tmp_path)
    report = markdown(rows, expected=1)

    assert rows[0]["comparator"] is True
    assert rows[0]["substantive"] is True
    assert rows[0]["calls"] == 1
    assert rows[0]["lean_checks"] == 2
    assert rows[0]["winner"] == "champion_r_q"
    assert "Gate: **PASS**" in report

