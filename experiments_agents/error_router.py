"""Cheap failure classification for routing (Phase E).

No problem ids.  Labels come from Lean/guard detail strings and stage names.
The LLM is optional; default path is pure heuristics so unit tests stay offline.
"""

from __future__ import annotations

import re
from typing import Any


# Ordered: first match wins.
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "def_circular",
        re.compile(
            r"circular|tautolog|definitional/tautological|canonical answer|"
            r"characterisation theorem definitional",
            re.I,
        ),
    ),
    (
        "signature_rewrite",
        re.compile(r"changed required declaration signature|signature", re.I),
    ),
    (
        "syntax_name",
        re.compile(
            r"unknown (?:identifier|constant)|invalid field|expected token|"
            r"unexpected token|failed to elaborate|type mismatch|"
            r"don't know how to synthesize",
            re.I,
        ),
    ),
    (
        "needs_lemma",
        re.compile(
            r"unsolved goals|failed to prove|no goals to be solved|"
            r"tactic.*failed|linarith|nlinarith|ring failed",
            re.I,
        ),
    ),
    (
        "goal_stuck",
        re.compile(r"exhausted|no_accept|portfolio_exhausted|bridge_no", re.I),
    ),
)


def classify_failure_text(*parts: str) -> str:
    """Return one of: def_circular, signature_rewrite, syntax_name, needs_lemma,
    goal_stuck, other.
    """

    blob = "\n".join(p for p in parts if p)
    if not blob.strip():
        return "other"
    for label, pattern in _RULES:
        if pattern.search(blob):
            return label
    return "other"


def classify_stage_report(report: dict[str, Any] | None) -> str:
    if not report:
        return "other"
    return classify_failure_text(
        str(report.get("stage") or ""),
        str(report.get("detail") or ""),
        str(report.get("failure_kind") or ""),
    )


def preferred_residual_mode(kind: str) -> str:
    """Map failure kind → residual emphasis.

    - program: definition/multi-decl first (Putnam-like)
    - bridge: lemma division
    - either: default
    """

    if kind in {"def_circular", "signature_rewrite"}:
        return "program"
    if kind in {"needs_lemma", "goal_stuck"}:
        return "bridge"
    if kind == "syntax_name":
        return "bridge"  # division still OK; repair already tried earlier
    return "either"


def problem_looks_answer_shaped(problem: Any) -> bool:
    """True if the challenge has answer defs/abbrevs with sorry (generic, no ids)."""

    challenge = getattr(problem, "challenge", "") or ""
    meta = getattr(problem, "metadata", None) or {}
    manifest = meta.get("__manifest__", {}) if isinstance(meta, dict) else {}
    if isinstance(manifest, dict):
        defs = manifest.get("definition_names") or []
        nums = manifest.get("numeric_answer_names") or []
        if defs or nums:
            return True
    # Structural: def/abbrev ... sorry appears before a theorem that mentions it.
    if re.search(
        r"(?m)^\s*(?:noncomputable\s+|private\s+)*(?:def|abbrev)\s+\S+[\s\S]{0,400}?\bsorry\b",
        challenge,
    ):
        return True
    return False
