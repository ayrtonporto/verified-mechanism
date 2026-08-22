"""Crash-resistant, secret-redacting JSONL event logging."""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


def _redact(value: Any, secrets: Iterable[str]) -> Any:
    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "[REDACTED]")
        return result
    if isinstance(value, dict):
        return {
            str(k): ("[REDACTED]" if str(k).lower() in {"authorization", "api_key"} else _redact(v, secrets))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item, secrets) for item in value]
    return value


class EventLogger:
    def __init__(self, path: Path, *, problem_id: str, secrets: Iterable[str] = ()):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.problem_id = problem_id
        self.secrets = tuple(s for s in secrets if s)
        self._lock = threading.Lock()
        self._seq = self._existing_count()

    def _existing_count(self) -> int:
        if not self.path.exists():
            return 0
        with self.path.open("rb") as handle:
            return sum(1 for line in handle if line.strip())

    def emit(self, event_type: str, **payload: Any) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            event = {
                "schema_version": 1,
                "seq": self._seq,
                "timestamp": datetime.now(UTC).isoformat(),
                "problem_id": self.problem_id,
                "event": event_type,
                **payload,
            }
            event = _redact(event, self.secrets)
            encoded = (
                json.dumps(
                    event, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                )
                + "\n"
            ).encode("utf-8")
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                view = memoryview(encoded)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise OSError("event log write made no progress")
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            return event


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # A killed writer can leave only its final line incomplete.
            continue
    return events
