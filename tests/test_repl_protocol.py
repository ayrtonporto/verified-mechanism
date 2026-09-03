from __future__ import annotations

import io
import os
import threading

from re_harness.events import EventLogger
from re_harness.lean import LeanClient


class _PipeProcess:
    def __init__(self, payload: bytes):
        read_fd, write_fd = os.pipe()
        self.stdin = io.BytesIO()
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self._killed = False

        def writer() -> None:
            try:
                os.write(write_fd, payload)
            finally:
                os.close(write_fd)

        self.thread = threading.Thread(target=writer)
        self.thread.start()

    def kill(self) -> None:
        self._killed = True


def _client(tmp_path, payload: bytes) -> tuple[LeanClient, _PipeProcess]:
    client = LeanClient(
        image="unused",
        events=EventLogger(tmp_path / "events.jsonl", problem_id="p"),
    )
    process = _PipeProcess(payload)
    client._proc = process  # type: ignore[assignment]
    return client, process


def test_repl_protocol_accepts_one_bounded_json_frame(tmp_path):
    client, process = _client(tmp_path, b'{"env":7,"messages":[]}\n\n')
    env, messages, timed_out = client._send("#check Nat", None, 1)
    process.thread.join()
    assert (env, messages, timed_out) == (7, [], False)


def test_repl_protocol_error_discards_container(tmp_path):
    client, process = _client(tmp_path, b"not-json\n\n")
    env, messages, timed_out = client._send("#check Nat", None, 1)
    process.thread.join()
    assert env is None and not timed_out
    assert "protocol error" in messages[0]["data"]
    assert process._killed
    assert client._proc is None


def test_repl_response_cap_applies_before_newline_allocation(tmp_path, monkeypatch):
    monkeypatch.setattr("re_harness.lean.MAX_REPL_RESPONSE_BYTES", 128)
    client, process = _client(tmp_path, b"x" * 129)
    env, messages, timed_out = client._send("#check Nat", None, 1)
    process.thread.join()
    assert env is None and not timed_out
    assert "size limit" in messages[0]["data"]
    assert process._killed

