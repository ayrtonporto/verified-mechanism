"""No-key end-to-end check of the published image and Comparator."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path

from .config import HarnessSettings
from .lean import _hardened_docker_args, compare_solution
from .manifest import load_problem_set


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problems", type=Path, default=Path("sample-problems"))
    args = parser.parse_args(argv)
    settings = HarnessSettings.from_env(n_workers=1)
    health_session = uuid.uuid4().hex
    health = subprocess.run(
        _hardened_docker_args(
            session_id=health_session,
            name=f"re-takehome-health-{health_session[:12]}",
            image=settings.lean_image,
        ) + ["health"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if health.returncode != 0:
        print(health.stderr or health.stdout)
        return 1
    print(f"image health: {health.stdout.strip()}")
    problem_set = load_problem_set(args.problems)
    spec = next(problem for problem in problem_set.problems if problem.id == "p01_linear")
    _description, challenge_path = problem_set.paths(spec)
    solution = challenge_path.read_text(encoding="utf-8").replace("  sorry", "  linarith")
    verdict = compare_solution(
        image=settings.lean_image,
        session_id=uuid.uuid4().hex,
        challenge=challenge_path.read_text(encoding="utf-8"),
        solution=solution,
        spec=spec,
        timeout_s=settings.comparator_timeout_s,
    )
    print(json.dumps(verdict.output, indent=2))
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

