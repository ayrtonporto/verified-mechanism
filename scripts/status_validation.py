#!/usr/bin/env python3
"""Quick validation leaf status for the live matrix."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_validation_gate import collect_run, find_run_dir  # noqa: E402


def score(leaf: str, root: Path) -> None:
    base = root / leaf
    n = len(list(base.rglob("result.json"))) if base.exists() else 0
    rd = find_run_dir(base)
    if not rd:
        print(f"{leaf}: {n}/9 no run_dir")
        return
    rows = collect_run(rd)
    cu = 0
    for p in rd.glob("*/result.json"):
        if json.loads(p.read_text(encoding="utf-8")).get("status") == "cost_unknown":
            cu += 1
    sub = sum(1 for r in rows if r["substantive"] is True)
    comp = sum(1 for r in rows if r["comparator"])
    usd = sum(r["cost_usd"] for r in rows)
    print(f"{leaf}: {n}/9 | SUB={sub} COMP={comp} cost_unknown={cu} usd={usd:.4f}")
    for r in rows:
        if r["substantive"]:
            mark = "Y"
        elif r["comparator"]:
            mark = "C"
        else:
            mark = "N"
        stage = str(r["winner"] or "-")
        print(
            f"  {r['problem']:20s} {mark}  stage={stage:28s} "
            f"status={r['status']:14s} wall={r['wall_s']:7.1f} usd={r['cost_usd']:.4f}"
        )


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/validation")
    leaves = sys.argv[2:] or [
        "agent_s1",
        "agent_s2",
        "agent_s3",
        "portfolio_rr_s1",
        "portfolio_rr_s2",
        "portfolio_rr_s3",
    ]
    for leaf in leaves:
        score(leaf, root)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
