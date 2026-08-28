"""Per-theorem heavy sampling + combine (the throughput strategy, within our
constraints). For a multi-theorem problem, solve EACH theorem independently across
N parallel samples (shared Lean queue, per-task budget), keep the best accepted proof
per theorem, then COMBINE the winners into one file and run the authoritative
comparator. Independent theorems mean p09_a and p09_b need not come out clean in the
same run — this breaks the conjunction that defeated the in-run lemma bank.

Universal: same procedure for any problem; slots are split structurally, each solved
by the same inner arm. Diversity comes from temperature + independent samples.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
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
from experiments_agents.multitheorem import (
    split_declarations, _block_has_sorry, _preamble_lines, _merge_preambles,
)
from experiments_agents.common import required_decl_names, integrity_check


def _factory(spec):
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn or "create_agent")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--agent", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", type=Path, default=Path("outputs_fast/multisample"))
    args = ap.parse_args()

    S = HarnessSettings.from_env()
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    pset = load_problem_set(args.set)
    spec = next(p for p in pset.problems if p.id == args.id)
    _desc_p, chal_p = pset.paths(spec)
    challenge = chal_p.read_text(encoding="utf-8")
    description = _desc_p.read_text(encoding="utf-8")
    run_dir = args.out / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir.mkdir(parents=True, exist_ok=True)
    events = EventLogger(run_dir / "events.jsonl", problem_id=args.id, secrets=(api_key,))
    lean = LeanClient(image=S.lean_image, events=events, session_id="multisample",
                      timeout_s=S.lean_check_timeout_s)
    factory = _factory(args.agent)

    pre, blocks = split_declarations(challenge)
    prov = [b for b in blocks if _block_has_sorry(b)]
    imports = "\n".join(_preamble_lines(pre)) or "import Mathlib"

    async def sample(block, s):
        name = (required_decl_names(block) or ["?"])[0]
        mini = imports + "\n\n" + block.rstrip() + "\n"
        budget = BudgetLedger(S.budget_usd)
        llm = LLMClient(api_key=api_key, budget=budget, events=events)
        prob = Problem(id=f"{args.id}::{name}#{s}",
                       description=f"{description}\n\n[Focus] Prove exactly `{name}`.",
                       challenge=mini, metadata=dict(spec.metadata))
        services = Services(llm=llm, lean=lean, checkpoint=lambda *a, **k: None)
        try:
            res = await factory().solve(prob, services)
            return name, s, res.solution, bool(res.metadata.get("accepted_by_repl"))
        except Exception as e:
            return name, s, None, False

    tasks = [sample(b, s) for b in prov for s in range(args.n)]
    started = time.monotonic()
    results = await asyncio.gather(*tasks)
    wall = time.monotonic() - started

    # best accepted proof per theorem
    winners: dict[str, str] = {}
    per_name_ok: dict[str, int] = {}
    for name, s, sol, ok in results:
        per_name_ok[name] = per_name_ok.get(name, 0) + (1 if ok else 0)
        if ok and name not in winners:
            winners[name] = sol
    print(f"=== multisample {args.id}: {len(tasks)} samples in {wall:.0f}s ===")
    for name in sorted(per_name_ok):
        print(f"  {name}: {per_name_ok[name]}/{args.n} samples accepted"
              f"{'  -> WINNER kept' if name in winners else ''}")

    prov_names = [(required_decl_names(b) or ['?'])[0] for b in prov]
    if all(n in winners for n in prov_names):
        merged = _merge_preambles([pre] + list(winners.values()))
        bodies = []
        for n in prov_names:
            _p, sb = split_declarations(winners[n])
            bodies.append("\n\n".join(x.rstrip() for x in sb) if sb else winners[n])
        final = merged + "\n\n" + "\n\n".join(bodies) + "\n"
        (run_dir / f"{args.id}__combined.lean").write_text(final, encoding="utf-8")
        c = await lean.check_file(final, timeout_s=180)
        ok_int = integrity_check(final, challenge)[0]
        print(f"COMBINED: repl_accepted={c.accepted} integrity={ok_int}")
        if c.accepted and ok_int:
            cmp = await asyncio.to_thread(
                compare_solution, image=S.lean_image, session_id=f"cmp-{args.id[:8]}",
                challenge=challenge, solution=final, spec=spec,
                timeout_s=S.comparator_timeout_s)
            print(f"COMPARATOR: passed={cmp.passed}")
    else:
        missing = [n for n in prov_names if n not in winners]
        print(f"NOT ALL SLOTS SOLVED — missing: {missing}")
    print("DONE_0")


if __name__ == "__main__":
    asyncio.run(main())
