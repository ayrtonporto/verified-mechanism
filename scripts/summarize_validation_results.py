#!/usr/bin/env python3
"""Summarize validation result.json files under a root."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    roots = [Path(a) for a in sys.argv[1:]] or [Path("outputs/validation")]
    for root in roots:
        files = sorted(root.rglob("result.json"))
        print(f"=== {root} ({len(files)} results) ===")
        for path in files:
            r = json.loads(path.read_text(encoding="utf-8"))
            md = r.get("agent_metadata") or {}
            comp = bool((r.get("comparator") or {}).get("passed"))
            sub = bool(md.get("substantive_closure"))
            if comp and not sub:
                # gate semantics: substantive requires comparator AND flag
                pass
            print(
                f"{r.get('problem_id')}: comp={comp} sub={bool(comp and md.get('substantive_closure'))} "
                f"flag={md.get('substantive_closure')} stage={md.get('stage_winner')} "
                f"usd={((r.get('budget') or {}).get('spent_usd'))} wall={r.get('wall_s')} "
                f"status={r.get('status')} cq={md.get('calls_q')} cg={md.get('calls_g')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
