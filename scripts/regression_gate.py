#!/usr/bin/env python3
"""Summarise one harness run as a strict substantive regression gate.

The script is deliberately problem-agnostic: the run directory/manifest selects the
population. It never contains problem ids, answers, or proofs. Comparator PASS and
substantive closure are separate columns, so a tautological answer definition cannot
silently preserve the score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_counts(path: Path) -> tuple[int, int]:
    calls = checks = 0
    if not path.is_file():
        return calls, checks
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        calls += event.get("event") == "llm_request"
        checks += event.get("event") == "lean_check"
    return calls, checks


def collect(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result_path in sorted(run_dir.glob("*/result.json")):
        result = _json(result_path)
        metadata = result.get("agent_metadata", {}) or {}
        graph = metadata.get("progress_graph", {}) or {}
        calls, checks = _event_counts(result_path.with_name("events.jsonl"))
        comparator = bool(result.get("comparator", {}).get("passed"))
        substantive = bool(comparator and metadata.get("substantive_closure"))
        failure = ""
        if comparator and not substantive:
            failure = "Comparator PASS, but the semantic/non-circularity gate did not certify it."
        elif not comparator:
            failure = str(result.get("status", "failed"))
        rows.append({
            "problem": str(result.get("problem_id", result_path.parent.name)),
            "comparator": comparator,
            "substantive": substantive,
            "wall_s": float(result.get("wall_s", 0.0) or 0.0),
            "cost_usd": float(result.get("budget", {}).get("spent_usd", 0.0) or 0.0),
            "calls": calls,
            "lean_checks": checks,
            "winner": str(metadata.get("stage_winner", "")),
            "lemmas_saved": int(graph.get("nodes_saved", 0) or 0),
            "lemmas_reused": int(graph.get("nodes_reused", 0) or 0),
            "failure": failure,
        })
    return rows


def markdown(rows: list[dict[str, Any]], expected: int) -> str:
    substantive = sum(row["substantive"] for row in rows)
    comparator = sum(row["comparator"] for row in rows)
    lines = [
        "# Regression gate",
        "",
        f"- Comparator PASS: **{comparator}/{len(rows)}**",
        f"- Substantive closures: **{substantive}/{len(rows)}**",
        f"- Required substantive closures: **{expected}**",
        f"- Gate: **{'PASS' if substantive >= expected and len(rows) >= expected else 'FAIL'}**",
        "",
        "| Problem | Comparator | Substantive | Wall s | USD | Calls | Lean | Winning stage | Saved | Reused |",
        "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['problem']}` | {'PASS' if row['comparator'] else 'FAIL'} | "
            f"{'YES' if row['substantive'] else 'NO'} | {row['wall_s']:.1f} | "
            f"{row['cost_usd']:.6f} | {row['calls']} | {row['lean_checks']} | "
            f"{row['winner'] or '—'} | {row['lemmas_saved']} | {row['lemmas_reused']} |"
        )
    failures = [row for row in rows if not row["substantive"]]
    if failures:
        lines.extend(["", "## Failures", ""])
        for row in failures:
            lines.append(f"- `{row['problem']}`: {row['failure'] or 'not substantively certified'}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--expected", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = collect(args.run_dir)
    report = markdown(rows, args.expected)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report)
    return 0 if len(rows) >= args.expected and sum(row["substantive"] for row in rows) >= args.expected else 1


if __name__ == "__main__":
    raise SystemExit(main())

