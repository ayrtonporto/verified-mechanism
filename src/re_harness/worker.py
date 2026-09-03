"""One-problem worker process used by the outer scheduler."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from .agent import AgentResult, Problem, Services
from .artifacts import atomic_write_json, atomic_write_text, build_transcript
from .budget import BudgetLedger
from .events import EventLogger, read_events
from .lean import (
    LeanClient,
    compare_solution,
    cleanup_session_containers,
    numeric_answers_are_literals,
)
from .llm import LLMClient
from .manifest import ProblemSpec
from .models import MODEL_A, MODEL_B


def _load_factory(reference: str):
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("agent reference must look like module:factory")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute)
    if not callable(factory):
        raise TypeError(f"{reference} is not callable")
    return factory


def _models_used(events_path: Path) -> list[str]:
    models = {
        event.get("request", {}).get("model")
        for event in read_events(events_path)
        if event.get("event") == "llm_request"
    }
    return sorted(model for model in models if isinstance(model, str))


async def _run(config: dict[str, Any]) -> int:
    out_dir = Path(config["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / "events.jsonl"
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    events = EventLogger(events_path, problem_id=config["problem_id"], secrets=(api_key,))
    budget = BudgetLedger(float(config["budget_usd"]))
    llm = LLMClient(api_key=api_key, budget=budget, events=events)
    lean = LeanClient(
        image=config["lean_image"],
        events=events,
        session_id=config["session_id"],
        timeout_s=int(config["lean_check_timeout_s"]),
    )
    challenge = config["challenge"]
    solution_path = out_dir / "solution.lean"
    checkpoint_metadata: dict[str, Any] = {}

    def checkpoint(source: str, metadata: dict[str, Any]) -> None:
        if not isinstance(source, str) or len(source.encode("utf-8")) > 1_000_000:
            raise ValueError("checkpoint must be Lean source no larger than 1,000,000 bytes")
        # Validate metadata before changing the recoverable solution.
        json.dumps(metadata, allow_nan=False)
        atomic_write_text(solution_path, source)
        atomic_write_json(out_dir / "checkpoint.json", {"metadata": metadata})
        checkpoint_metadata.clear()
        checkpoint_metadata.update(metadata)
        events.emit("checkpoint", source_bytes=len(source.encode("utf-8")), metadata=metadata)

    problem_metadata = dict(config["problem_metadata"])
    # Agents coordinating multi-declaration programs need the answer-shape contract
    # before the final comparator runs. Keep it under one reserved namespace so public
    # problem metadata remains unchanged and future manifest fields can be extended.
    problem_metadata["__manifest__"] = {
        "theorem_names": list(config["theorem_names"]),
        "definition_names": list(config["definition_names"]),
        "numeric_answer_names": list(config["numeric_answer_names"]),
    }
    problem = Problem(
        id=config["problem_id"],
        description=config["description"],
        challenge=challenge,
        metadata=problem_metadata,
    )
    services = Services(llm=llm, lean=lean, checkpoint=checkpoint)
    started = time.monotonic()
    status = "failed"
    agent_error: dict[str, Any] | None = None
    agent_metadata: dict[str, Any] = {}
    reserve = min(float(config["verify_reserve_s"]), float(config["time_limit_s"]) * 0.25)
    agent_time = max(1.0, float(config["time_limit_s"]) - reserve)
    events.emit("problem_started", agent=config["agent"], agent_time_limit_s=agent_time)
    try:
        factory = _load_factory(config["agent"])
        agent = factory()
        result = await asyncio.wait_for(agent.solve(problem, services), timeout=agent_time)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, AgentResult):
            raise TypeError("Agent.solve must return AgentResult")
        if not isinstance(result.solution, str) or not result.solution.strip():
            raise ValueError("AgentResult.solution must be non-empty Lean source")
        agent_metadata = dict(result.metadata)
        json.dumps(agent_metadata, allow_nan=False)
        checkpoint(result.solution, agent_metadata)
        status = "completed"
    except asyncio.TimeoutError:
        status = "agent_timeout"
        agent_error = {"type": "TimeoutError", "message": f"agent exceeded {agent_time:.1f}s"}
        events.emit("agent_error", **agent_error)
    except BaseException as exc:
        status = "harness_error"
        agent_error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(traceback.format_exception(exc))[-12_000:],
        }
        events.emit("agent_error", **agent_error)

    if not solution_path.exists():
        atomic_write_text(solution_path, challenge)
    solution = solution_path.read_text(encoding="utf-8")
    # Final verification never reuses the agent's environment. Stop the warm
    # REPL first, then launch Comparator in a separately created clean image.
    lean.close()
    spec = ProblemSpec(
        id=config["problem_id"],
        theorem_names=tuple(config["theorem_names"]),
        definition_names=tuple(config["definition_names"]),
        numeric_answer_names=tuple(config["numeric_answer_names"]),
        metadata=config["problem_metadata"],
    )
    answer_ok, answer_errors = numeric_answers_are_literals(solution, spec.numeric_answer_names)
    comparator: dict[str, Any]
    try:
        remaining = max(1, int(float(config["time_limit_s"]) - (time.monotonic() - started)))
        verdict = await asyncio.to_thread(
            compare_solution,
            image=config["lean_image"],
            session_id=config["session_id"],
            challenge=challenge,
            solution=solution,
            spec=spec,
            timeout_s=min(int(config["comparator_timeout_s"]), remaining),
        )
        comparator = {
            "passed": verdict.passed,
            "exit_code": verdict.exit_code,
            "timed_out": verdict.timed_out,
            "duration_ms": verdict.duration_ms,
            "output": verdict.output,
        }
    except BaseException as exc:
        comparator = {
            "passed": False,
            "exit_code": None,
            "timed_out": False,
            "duration_ms": 0,
            "output": {"error": f"{type(exc).__name__}: {exc}"},
        }
        if status == "completed":
            status = "harness_error"
        events.emit("comparator_error", error_type=type(exc).__name__, message=str(exc))
    finally:
        lean.close()
        await llm.aclose()
        cleanup_session_containers(config["session_id"])

    wall_s = round(time.monotonic() - started, 3)
    snapshot = budget.snapshot()
    models_used = _models_used(events_path)
    within_time = wall_s <= float(config["time_limit_s"])
    passed = bool(comparator["passed"] and answer_ok and snapshot.within_limit and within_time)
    if snapshot.spent_usd > snapshot.limit_usd:
        status = "over_budget"
    elif not snapshot.accounting_complete:
        status = "cost_unknown"
    elif not within_time:
        status = "timed_out"
    elif passed:
        status = "passed"
    elif status == "completed":
        status = "failed"
    result_json = {
        "schema_version": 1,
        "problem_id": config["problem_id"],
        "status": status,
        "passed": passed,
        "points": 1 if passed else 0,
        "comparator": comparator,
        "answer_shape": {"passed": answer_ok, "errors": answer_errors},
        "budget": snapshot.__dict__,
        "within_time": within_time,
        "wall_s": wall_s,
        "models_used": models_used,
        "both_required_models_used": {MODEL_A, MODEL_B} <= set(models_used),
        "agent_error": agent_error,
        "agent_metadata": agent_metadata or checkpoint_metadata,
    }
    events.emit("problem_finished", status=status, passed=passed, wall_s=wall_s)
    atomic_write_json(out_dir / "result.json", result_json)
    atomic_write_json(
        out_dir / "transcript.json",
        build_transcript(events_path, problem_id=config["problem_id"]),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    try:
        return asyncio.run(_run(config))
    except BaseException as exc:
        # The outer scheduler reconstructs artifacts from events/checkpoints.
        print(f"worker fatal error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
