"""Fast dev driver: parallel model calls, one serialized Lean/Mathlib queue.

The memory limit is the *Lean check* (each REPL/comparator container needs ~8 GB;
the box holds one). Model calls are just HTTP — no memory, embarrassingly parallel,
and they are the real wall-time hog (~70 s each, many of them, serialized today).

So this driver decouples the two: it runs every problem's agent **concurrently**
on one event loop (their model calls overlap) while a **single shared LeanClient**
serializes all Lean checks through one warm container (its internal lock already
enforces one-at-a-time). The authoritative comparator runs sequentially at the end.

Net effect vs the stock runner (one worker, one container, one problem at a time):
wall time drops from ~sum of per-problem times toward ~max, because the dominant
model-call latency now overlaps across problems (and across repeats).

Universal: it changes only *scheduling*, not the agent or the verifier. Not for the
final graded S_eval run (use the kit runner); this is the dev fast-path.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import time
from pathlib import Path

from re_harness.config import HarnessSettings
from re_harness.events import EventLogger
from re_harness.lean import LeanClient, compare_solution
from re_harness.llm import LLMClient
from re_harness.budget import BudgetLedger
from re_harness.manifest import load_problem_set
from re_harness.agent import Problem, Services


def _load_factory(spec: str):
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn or "create_agent")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--problems", type=Path, required=True)
    ap.add_argument("--agent", required=True, help="module:factory")
    ap.add_argument("--out", type=Path, default=Path("outputs_fast"))
    ap.add_argument("--repeat", type=int, default=1, help="runs per problem (variance)")
    ap.add_argument("--max-parallel", type=int, default=0,
                    help="cap concurrent agents (0 = all at once)")
    args = ap.parse_args()

    settings = HarnessSettings.from_env()
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    pset = load_problem_set(args.problems)
    run_dir = args.out / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir.mkdir(parents=True, exist_ok=True)
    events = EventLogger(run_dir / "events.jsonl", problem_id="fastdrive", secrets=(api_key,))
    budget = BudgetLedger(settings.budget_usd)
    llm = LLMClient(api_key=api_key, budget=budget, events=events)
    lean = LeanClient(image=settings.lean_image, events=events, session_id="fastdrive",
                      timeout_s=settings.lean_check_timeout_s)
    factory = _load_factory(args.agent)

    gate = asyncio.Semaphore(args.max_parallel) if args.max_parallel > 0 else None

    tasks = []
    for spec in pset.problems:
        desc_p, chal_p = pset.paths(spec)
        description = desc_p.read_text(encoding="utf-8")
        challenge = chal_p.read_text(encoding="utf-8")
        for r in range(args.repeat):
            tasks.append(_solve(spec, description, challenge, r, factory, llm, lean,
                                run_dir, gate))

    started = time.monotonic()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    wall = time.monotonic() - started

    # authoritative comparator, sequential (each spawns its own container)
    spent = budget.snapshot().spent_usd
    print(f"\n=== fastdrive: {len(tasks)} agent runs in {wall:.0f}s wall "
          f"(spent ${spent:.4f}) ===")
    scored: dict[str, list[bool]] = {}
    for item in results:
        if isinstance(item, Exception):
            print(f"  EXCEPTION: {type(item).__name__}: {item}")
            continue
        spec, r, res = item
        solution = res.solution
        repl_ok = bool(res.metadata.get("accepted_by_repl"))
        passed = False
        if repl_ok:
            cmp = await asyncio.to_thread(
                compare_solution, image=settings.lean_image,
                session_id=f"cmp-{spec.id[:8]}-{r}", challenge=_read(spec, pset, "challenge"),
                solution=solution, spec=spec, timeout_s=settings.comparator_timeout_s)
            passed = cmp.passed
        scored.setdefault(spec.id, []).append(passed)
        (run_dir / f"{spec.id}__r{r}.lean").write_text(solution, encoding="utf-8")
        print(f"  {spec.id:20s} r{r} repl_ok={repl_ok} comparator={'PASS' if passed else 'fail'} "
              f"stop={res.metadata.get('stop_reason')}")

    total = sum(any(v) for v in scored.values())
    print(f"\n=== SCORE (any-repeat pass) = {total}/{len(scored)} ===")
    for pid, passes in sorted(scored.items()):
        print(f"  {pid:20s} {sum(passes)}/{len(passes)} repeats passed")
    (run_dir / "summary.json").write_text(json.dumps(
        {"score": total, "n": len(scored), "wall_s": wall,
         "spent_usd": spent,
         "by_problem": {k: v for k, v in scored.items()}}, indent=2), encoding="utf-8")
    print("DONE_0")


def _read(spec, pset, which):
    desc_p, chal_p = pset.paths(spec)
    return chal_p.read_text(encoding="utf-8")


async def _solve(spec, description, challenge, r, factory, llm, lean, run_dir, gate):
    async def run():
        sol_path = run_dir / f"{spec.id}__r{r}__ckpt.lean"

        def checkpoint(source, metadata=None):
            sol_path.write_text(source, encoding="utf-8")

        problem = Problem(id=spec.id, description=description, challenge=challenge,
                          metadata=dict(spec.metadata))
        services = Services(llm=llm, lean=lean, checkpoint=checkpoint)
        agent = factory()
        res = await agent.solve(problem, services)
        return spec, r, res

    if gate is None:
        return await run()
    async with gate:
        return await run()


if __name__ == "__main__":
    asyncio.run(main())
