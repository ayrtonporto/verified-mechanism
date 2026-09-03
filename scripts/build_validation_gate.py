#!/usr/bin/env python3
"""Build validation_gate markdown from outputs/validation/* runs.

Reports BOTH comparator and substantive. For arms that do not set
substantive_closure in metadata, falls back to comparator-only and marks
substantive as 'not logged' unless a solution.lean can be re-checked offline
(we do not invent).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROBLEMS = [
    "p01_linear",
    "p03_sq_ge_two_ab",
    "p05_gcd_mersenne",
    "p06_pow_mod",
    "p09_imo1964",
    "p10_factorial_pow",
    "putnam_2018_a1",
    "rmo_2000_2",
    "rmo_2000_3",
]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _model_from_event(event: dict[str, Any]) -> str:
    model = event.get("model")
    if model:
        return str(model)
    req = event.get("request") or {}
    if isinstance(req, dict) and req.get("model"):
        return str(req.get("model"))
    resp = event.get("response") or {}
    if isinstance(resp, dict) and resp.get("model"):
        return str(resp.get("model"))
    return ""


def _event_counts(path: Path) -> tuple[int, int, int, int]:
    """Return (calls, lean_checks, calls_q, calls_g) from events.jsonl if present."""
    calls = checks = cq = cg = 0
    if not path.is_file():
        return calls, checks, cq, cg
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "llm_request":
            calls += 1
            model = _model_from_event(event).lower()
            if "qwen" in model:
                cq += 1
            elif "gpt-oss" in model or model.startswith("openai/"):
                cg += 1
        elif event.get("event") == "lean_check":
            checks += 1
    return calls, checks, cq, cg


def _calls_from_stages(md: dict[str, Any]) -> tuple[int | None, int | None]:
    stages = md.get("stages")
    if not isinstance(stages, list) or not stages:
        return None, None
    cq = cg = 0
    saw = False
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        if "calls_q" in stage or "calls_g" in stage:
            saw = True
            cq += int(stage.get("calls_q") or 0)
            cg += int(stage.get("calls_g") or 0)
    return (cq, cg) if saw else (None, None)


def collect_run(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result_path in sorted(run_dir.glob("*/result.json")):
        result = _load(result_path)
        md = result.get("agent_metadata") or {}
        calls, checks, cq, cg = _event_counts(result_path.with_name("events.jsonl"))
        # Prefer explicit metadata totals, then stage sums, else events.
        if md.get("calls_q") is not None or md.get("calls_g") is not None:
            cq = int(md.get("calls_q") or 0)
            cg = int(md.get("calls_g") or 0)
        else:
            scq, scg = _calls_from_stages(md)
            if scq is not None and scg is not None:
                cq, cg = scq, scg
        comparator = bool((result.get("comparator") or {}).get("passed"))
        flag = md.get("substantive_closure")
        # integrated agent / portfolio set the flag; science arms often omit it.
        # Timeout/crash with empty metadata → substantive False (not a pass), not invent.
        if flag is None:
            if comparator:
                substantive = None  # cannot claim substantive without guard flag
            else:
                substantive = False
        else:
            substantive = bool(comparator and flag)
        rows.append(
            {
                "problem": str(result.get("problem_id") or result_path.parent.name),
                "comparator": comparator,
                "substantive": substantive,
                "flag": flag,
                "wall_s": float(result.get("wall_s") or 0.0),
                "cost_usd": float((result.get("budget") or {}).get("spent_usd") or 0.0),
                "calls": calls,
                "calls_q": cq,
                "calls_g": cg,
                "lean_checks": checks,
                "winner": str(md.get("stage_winner") or md.get("arm") or md.get("stop_reason") or ""),
                "status": str(result.get("status") or ""),
                "time_limit_s": float(
                    (result.get("limits") or {}).get("time_limit_s")
                    or (result.get("config") or {}).get("time_limit_s")
                    or 0.0
                ),
            }
        )
    return rows


def find_run_dir(leaf_dir: Path) -> Path | None:
    """outputs/validation/<leaf>/<agent_name>/<timestamp>/"""
    if not leaf_dir.is_dir():
        return None
    pointer = leaf_dir.parent / f"{leaf_dir.name}_run_dir.txt"
    if pointer.is_file():
        text = pointer.read_text(encoding="utf-8").strip()
        if text and text != "not logged" and Path(text).is_dir():
            return Path(text)
    candidates: list[Path] = []
    for child in leaf_dir.iterdir():
        if not child.is_dir():
            continue
        for ts in child.iterdir():
            if ts.is_dir() and any(ts.glob("*/result.json")):
                candidates.append(ts)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def fmt_sub(v: bool | None) -> str:
    if v is None:
        return "not logged"
    return "Y" if v else "N"


def run_summary(label: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"### {label}\n\n- **status:** not logged (no results)\n"
    n = len(rows)
    comp = sum(1 for r in rows if r["comparator"])
    sub_known = [r for r in rows if r["substantive"] is not None]
    sub = sum(1 for r in sub_known if r["substantive"])
    usd = sum(r["cost_usd"] for r in rows)
    wall = sum(r["wall_s"] for r in rows)
    lines = [
        f"### {label}",
        "",
        f"- Problems logged: **{n}/9**",
        f"- Comparator PASS: **{comp}/{n}**",
        f"- Substantive: **{sub}/{len(sub_known)}**"
        + (" (arms without substantive flag → not logged)" if len(sub_known) < n else ""),
        f"- Total USD: **{usd:.6f}**",
        f"- Total wall_s: **{wall:.1f}**",
        "",
        "| Problem | Comp | Sub | Stage/arm | USD | Calls Q/G | Wall s | Status |",
        "|---|---:|---|---|---:|---|---:|---|",
    ]
    by = {r["problem"]: r for r in rows}
    for pid in PROBLEMS:
        r = by.get(pid)
        if r is None:
            lines.append(f"| {pid} | — | not logged | — | — | — | — | missing |")
            continue
        lines.append(
            f"| {r['problem']} | {'Y' if r['comparator'] else 'N'} | {fmt_sub(r['substantive'])} | "
            f"{r['winner'] or '—'} | {r['cost_usd']:.6f} | {r['calls_q']}/{r['calls_g']} | "
            f"{r['wall_s']:.1f} | {r['status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def matrix_cell(leaf_rows: list[list[dict[str, Any]]], problem: str) -> str:
    """k/3 substantive when known; else k/3 comparator with note."""
    passes = 0
    known = 0
    for rows in leaf_rows:
        by = {r["problem"]: r for r in rows}
        r = by.get(problem)
        if r is None:
            continue
        known += 1
        if r["substantive"] is True:
            passes += 1
        elif r["substantive"] is None and r["comparator"]:
            # count comparator as provisional for science arms
            passes += 1
    if known == 0:
        return "not logged"
    return f"{passes}/{known}"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/validation")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "away/validation_gate_2026-09-02.md")

    agent_leaves = [f"agent_s{i}" for i in (1, 2, 3)]
    portfolio_leaves = [f"portfolio_rr_s{i}" for i in (1, 2, 3)]
    arms = ["s_q", "s_g", "r_q", "r_g", "h_qg", "h_gq"]
    arm_leaves = {arm: [f"{arm}_s{i}" for i in (1, 2, 3)] for arm in arms}

    sections: list[str] = []
    sections.append("# Validation gate — 2026-09-02")
    sections.append("")
    sections.append(f"- Generated: `{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}`")
    sections.append("- Caps (matched): `VM_TIME_LIMIT_S=1200` (20 min), `VM_BUDGET_USD=1.00`, Lean 8g, N_WORKERS=1")
    sections.append("- Set: `sets/S_dev` (9 problems)")
    sections.append("- Rule: never invent cells; missing → `not logged`")
    sections.append("- Substantive = comparator PASS **and** integrity/anti-tautology guard when the arm sets the flag")
    sections.append("- Science S/R/H arms historically omit `substantive_closure`; for those cells we report comparator and mark substantive flag status")
    sections.append("")

    # P1 agent
    sections.append("## P1 — Integrated agent (`submission.agent`) × 3")
    sections.append("")
    agent_runs: list[list[dict[str, Any]]] = []
    agent_subscores: list[int] = []
    for leaf in agent_leaves:
        run_dir = find_run_dir(root / leaf)
        if run_dir is None:
            sections.append(run_summary(f"{leaf} — **not logged**", []))
            agent_runs.append([])
            continue
        rows = collect_run(run_dir)
        agent_runs.append(rows)
        sub = sum(1 for r in rows if r["substantive"] is True)
        agent_subscores.append(sub)
        sections.append(run_summary(f"{leaf} (`{run_dir}`)", rows))

    if agent_subscores:
        rate = sum(1 for s in agent_subscores if s == 5)
        sections.append(
            f"**Headline:** substantive scores over completed seeds = "
            f"{agent_subscores} → 5/9 in **{rate}/{len(agent_subscores)}** completed runs "
            f"(target reproduce: 5/9 under 20-min cap)."
        )
    else:
        sections.append("**Headline:** not logged (no agent seeds complete).")
    sections.append("")

    # P2 portfolio
    sections.append("## P2 — `portfolio_RR` (R-Q half → R-G remainder) × 3")
    sections.append("")
    port_runs: list[list[dict[str, Any]]] = []
    port_scores: list[int] = []
    for leaf in portfolio_leaves:
        run_dir = find_run_dir(root / leaf)
        if run_dir is None:
            sections.append(run_summary(f"{leaf} — **not logged**", []))
            port_runs.append([])
            continue
        rows = collect_run(run_dir)
        port_runs.append(rows)
        sub = sum(1 for r in rows if r["substantive"] is True)
        port_scores.append(sub)
        sections.append(run_summary(f"{leaf} (`{run_dir}`)", rows))
    if port_scores and agent_subscores:
        sections.append(
            f"**Causal compare (same budget):** portfolio_RR scores {port_scores} vs integrated agent {agent_subscores}."
        )
    else:
        sections.append("**Causal compare:** not logged (incomplete).")
    sections.append("")

    # P3 matrix
    sections.append("## P3 — S/R/H matrix, 3 seeds, matched caps")
    sections.append("")
    sections.append(
        "Per-cell values are **k/3** (how many of the completed seeds passed). "
        "For science arms without `substantive_closure`, k counts **comparator PASS** and is labelled `(comp)`."
    )
    sections.append("")
    header = "| Problem | " + " | ".join(arms) + " |"
    sep = "|---|" + "|".join(["---:"] * len(arms)) + "|"
    sections.append(header)
    sections.append(sep)

    arm_row_sets: dict[str, list[list[dict[str, Any]]]] = {}
    for arm, leaves in arm_leaves.items():
        sets: list[list[dict[str, Any]]] = []
        for leaf in leaves:
            rd = find_run_dir(root / leaf)
            sets.append(collect_run(rd) if rd else [])
        arm_row_sets[arm] = sets

    for pid in PROBLEMS:
        cells = []
        for arm in arms:
            cell = matrix_cell(arm_row_sets[arm], pid)
            # annotate if any seed lacked substantive flag
            had_flag = False
            had_comp_only = False
            for rows in arm_row_sets[arm]:
                by = {r["problem"]: r for r in rows}
                r = by.get(pid)
                if not r:
                    continue
                if r["substantive"] is not None:
                    had_flag = True
                else:
                    had_comp_only = True
            if cell != "not logged" and had_comp_only and not had_flag:
                cell = f"{cell} (comp)"
            cells.append(cell)
        sections.append(f"| {pid} | " + " | ".join(cells) + " |")
    sections.append("")

    sections.append("### Per-arm totals (over completed seeds)")
    sections.append("")
    sections.append("| Arm | Seeds done | Comp total | Sub total | USD total |")
    sections.append("|---|---:|---:|---:|---:|")
    for arm in arms:
        seeds = arm_row_sets[arm]
        done = sum(1 for s in seeds if s)
        comp = sum(1 for s in seeds for r in s if r["comparator"])
        sub = sum(1 for s in seeds for r in s if r["substantive"] is True)
        usd = sum(r["cost_usd"] for s in seeds for r in s)
        sub_note = str(sub) if any(r["substantive"] is not None for s in seeds for r in s) else "not logged"
        sections.append(f"| {arm} | {done}/3 | {comp} | {sub_note} | {usd:.6f} |")
    sections.append("")

    # Spend ledger
    sections.append("## Spend ledger (USD)")
    sections.append("")
    sections.append("| Condition | Seed | Problem | USD | Wall s |")
    sections.append("|---|---:|---|---:|---:|")
    grand = 0.0
    all_leaves = (
        [(f"agent_s{i}", f"agent", i) for i in (1, 2, 3)]
        + [(f"portfolio_rr_s{i}", "portfolio_rr", i) for i in (1, 2, 3)]
        + [(f"{arm}_s{i}", arm, i) for arm in arms for i in (1, 2, 3)]
    )
    for leaf, cond, seed in all_leaves:
        rd = find_run_dir(root / leaf)
        if rd is None:
            sections.append(f"| {cond} | {seed} | — | not logged | not logged |")
            continue
        rows = collect_run(rd)
        if not rows:
            sections.append(f"| {cond} | {seed} | — | not logged | not logged |")
            continue
        for r in rows:
            grand += r["cost_usd"]
            sections.append(
                f"| {cond} | {seed} | {r['problem']} | {r['cost_usd']:.6f} | {r['wall_s']:.1f} |"
            )
    sections.append("")
    sections.append(f"**Grand total USD (logged only):** {grand:.6f}")
    sections.append("")

    # Caps confirmation + diffs
    sections.append("## Caps confirmation")
    sections.append("")
    sections.append("- Requested: `VM_TIME_LIMIT_S=1200`, `VM_BUDGET_USD=1.00` for ALL conditions.")
    sections.append("- Runner script: `run_validation_matrix_sshrun.sh` exports those before every `run.py`.")
    sections.append("- 20-minute 5/9 robustness: see P1 headline above.")
    sections.append("")
    sections.append("## Differences vs writeup baseline (5/9 primary)")
    sections.append("")
    sections.append("- Writeup primary graded number: integrated agent **5/9 substantive** on S_dev.")
    if agent_subscores:
        diffs = [s for s in agent_subscores if s != 5]
        if not diffs and len(agent_subscores) == 3:
            sections.append("- This validation: **5/9 held in all 3 seeds under 20-min cap.**")
        else:
            sections.append(
                f"- This validation agent substantive scores: {agent_subscores}. "
                f"**FLAG any ≠5 loudly for the writeup.**"
            )
    else:
        sections.append("- Agent seeds incomplete at gate time → not logged.")
    sections.append("")
    sections.append("## P4 transcripts")
    sections.append("")
    sections.append("See `outputs/validation/transcripts/` for case-study excerpts when harvested.")
    sections.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(sections) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
