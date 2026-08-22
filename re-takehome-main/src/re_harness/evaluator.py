"""Mechanically re-run final Comparator checks over existing solutions."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .artifacts import atomic_write_json, aggregate_results
from .config import HarnessSettings
from .lean import compare_solution, numeric_answers_are_literals
from .manifest import ProblemSet, ProblemSpec, load_problem_set


def _rescore_one(
    problem_set: ProblemSet,
    spec: ProblemSpec,
    out_dir: Path,
    settings: HarnessSettings,
) -> None:
    problem_out = out_dir / spec.id
    result_path = problem_out / "result.json"
    previous = {}
    if result_path.exists():
        try:
            previous = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    solution_path = problem_out / "solution.lean"
    _description_path, challenge_path = problem_set.paths(spec)
    if not solution_path.exists():
        previous.update({"status": "missing", "passed": False, "points": 0})
        atomic_write_json(result_path, previous)
        return
    solution = solution_path.read_text(encoding="utf-8")
    answer_ok, answer_errors = numeric_answers_are_literals(solution, spec.numeric_answer_names)
    verdict = compare_solution(
        image=settings.lean_image,
        session_id=uuid.uuid4().hex,
        challenge=challenge_path.read_text(encoding="utf-8"),
        solution=solution,
        spec=spec,
        timeout_s=settings.comparator_timeout_s,
    )
    budget = previous.get("budget", {})
    budget_ok = bool(
        budget.get("accounting_complete")
        and float(budget.get("spent_usd", float("inf"))) <= settings.budget_usd
    )
    within_time = bool(previous.get("within_time", False))
    passed = verdict.passed and answer_ok and budget_ok and within_time
    previous.update({
        "schema_version": 1,
        "problem_id": spec.id,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "points": 1 if passed else 0,
        "comparator": {
            "passed": verdict.passed,
            "exit_code": verdict.exit_code,
            "timed_out": verdict.timed_out,
            "duration_ms": verdict.duration_ms,
            "output": verdict.output,
        },
        "answer_shape": {"passed": answer_ok, "errors": answer_errors},
    })
    atomic_write_json(result_path, previous)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problems", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n-workers", type=int, default=1)
    args = parser.parse_args(argv)
    if args.n_workers < 1:
        parser.error("--n-workers must be >= 1")
    settings = HarnessSettings.from_env(n_workers=args.n_workers)
    problem_set = load_problem_set(args.problems)
    with ThreadPoolExecutor(max_workers=args.n_workers) as pool:
        futures = {
            pool.submit(_rescore_one, problem_set, spec, args.out, settings): spec
            for spec in problem_set.problems
        }
        for future in as_completed(futures):
            spec = futures[future]
            try:
                future.result()
            except BaseException as exc:
                result_path = args.out / spec.id / "result.json"
                try:
                    previous = json.loads(result_path.read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError):
                    previous = {}
                previous.update({
                    "schema_version": 1,
                    "problem_id": spec.id,
                    "status": "harness_error",
                    "passed": False,
                    "points": 0,
                    "comparator": {"passed": False, "output": {"error": str(exc)}},
                })
                atomic_write_json(result_path, previous)
    summary = aggregate_results(
        args.out, [spec.id for spec in problem_set.problems], set_name=problem_set.name
    )
    atomic_write_json(args.out / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
