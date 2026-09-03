from __future__ import annotations

from re_harness.artifacts import build_transcript
from re_harness.events import EventLogger, read_events


def test_events_are_redacted_and_truncated_tail_is_ignored(tmp_path):
    path = tmp_path / "events.jsonl"
    logger = EventLogger(path, problem_id="p", secrets=("secret-key",))
    logger.emit(
        "llm_request",
        call_id="c",
        request={"model": "m", "messages": [{"content": "secret-key"}]},
        authorization="Bearer secret-key",
    )
    logger.emit(
        "llm_response", call_id="c", response={"usage": {"cost": 0.1}}, actual_cost_usd=0.1
    )
    with path.open("ab") as handle:
        handle.write(b'{"incomplete":')
    assert "secret-key" not in path.read_text()
    assert len(read_events(path)) == 2
    transcript = build_transcript(path, problem_id="p")
    assert transcript["actual_cost_usd"] == 0.1
    assert transcript["calls"][0]["request"]["messages"][0]["content"] == "[REDACTED]"

