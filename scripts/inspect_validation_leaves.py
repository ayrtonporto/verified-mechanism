#!/usr/bin/env python3
"""Inspect validation leaves for contamination (cost_unknown, tiny wall, empty spend)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/validation")
leaves = sys.argv[2:] or ["agent_s1", "agent_s2", "agent_s3"]


def main() -> None:
    for leaf in leaves:
        base = ROOT / leaf
        print(f"==== {leaf} ====")
        results = sorted(base.rglob("result.json"))
        if not results:
            print("  no results")
            continue
        for path in results:
            r = json.loads(path.read_text(encoding="utf-8"))
            md = r.get("agent_metadata") or {}
            budget = r.get("budget") or {}
            comp = bool((r.get("comparator") or {}).get("passed"))
            sub = bool(comp and md.get("substantive_closure"))
            err = r.get("agent_error") or {}
            print(
                f"  {r.get('problem_id')}: status={r.get('status')} comp={comp} sub={sub} "
                f"usd={budget.get('spent_usd')} acct={budget.get('accounting_complete')} "
                f"wall={r.get('wall_s')} stage={md.get('stage_winner')} "
                f"models={r.get('models_used')} err_type={err.get('type')} "
                f"err_msg={(str(err.get('message') or ''))[:120]}"
            )


if __name__ == "__main__":
    main()
