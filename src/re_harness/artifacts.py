"""Atomic artifact writers and transcript/summary derivation."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .events import read_events


def atomic_write_text(path: Path, content: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        # os.fchmod is POSIX-only; Windows uses os.chmod on the path instead.
        if hasattr(os, "fchmod"):
            os.fchmod(fd, mode)
        else:
            os.chmod(tmp_name, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(
        path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )


def build_transcript(events_path: Path, *, problem_id: str) -> dict[str, Any]:
    calls: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for event in read_events(events_path):
        if event.get("event") not in {"llm_request", "llm_response", "llm_error"}:
            continue
        call_id = str(event.get("call_id", ""))
        if not call_id:
            continue
        if call_id not in calls:
            calls[call_id] = {"call_id": call_id}
            order.append(call_id)
        record = calls[call_id]
        if event["event"] == "llm_request":
            record["request"] = event.get("request")
            record["started_at"] = event.get("timestamp")
            record["reserved_cost_usd"] = event.get("reserved_cost_usd")
        elif event["event"] == "llm_response":
            record["response"] = event.get("response")
            record["actual_cost_usd"] = event.get("actual_cost_usd")
            record["latency_ms"] = event.get("latency_ms")
            record["status"] = "ok"
        else:
            record["error"] = {
                k: v for k, v in event.items()
                if k not in {"schema_version", "seq", "timestamp", "problem_id", "event", "call_id"}
            }
            record["status"] = "error"
    actual = sum(float(c.get("actual_cost_usd") or 0.0) for c in calls.values())
    return {
        "schema_version": 1,
        "problem_id": problem_id,
        "calls": [calls[call_id] for call_id in order],
        "actual_cost_usd": round(actual, 10),
    }


def aggregate_results(out_dir: Path, problem_ids: list[str], *, set_name: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for problem_id in sorted(problem_ids):
        path = out_dir / problem_id / "result.json"
        if path.exists():
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                result = {"problem_id": problem_id, "status": "harness_error", "passed": False}
        else:
            result = {"problem_id": problem_id, "status": "missing", "passed": False}
        failure_reason = None
        if not result.get("passed"):
            agent_error = result.get("agent_error") or {}
            comparator_output = result.get("comparator", {}).get("output", {})
            answer_errors = result.get("answer_shape", {}).get("errors", [])
            comparator_detail = None
            if isinstance(comparator_output, dict):
                comparator_detail = (
                    comparator_output.get("error")
                    or comparator_output.get("stderr")
                    or comparator_output.get("stdout")
                )
                if isinstance(comparator_detail, str):
                    comparator_detail = comparator_detail[-2_000:]
            failure_reason = (
                agent_error.get("message")
                or comparator_detail
                or (answer_errors[0] if answer_errors else None)
                or result.get("status", "unknown")
            )
        rows.append({
            "problem_id": problem_id,
            "status": result.get("status", "unknown"),
            "passed": bool(result.get("passed")),
            "points": 1 if result.get("passed") else 0,
            "actual_cost_usd": float(result.get("budget", {}).get("spent_usd", 0.0)),
            "wall_s": float(result.get("wall_s", 0.0)),
            "models_used": result.get("models_used", []),
            "failure_reason": failure_reason,
        })
    return {
        "schema_version": 1,
        "set": set_name,
        "problems": rows,
        "total_points": sum(row["points"] for row in rows),
        "max_points": len(rows),
        "actual_cost_usd": round(sum(row["actual_cost_usd"] for row in rows), 10),
        "wall_s_sum": round(sum(row["wall_s"] for row in rows), 3),
    }
