"""Residual-path hygiene helpers (P0): notebook, goal-shaped extract, telemetry.

English-only durable strings. No problem ids. Pure helpers so offline unit tests
do not need Lean or LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .verified_progress import VerifiedProgressGraph, normalize_statement

_STOP = {
    "theorem",
    "lemma",
    "have",
    "by",
    "exact",
    "true",
    "false",
    "nat",
    "int",
    "real",
    "prop",
    "type",
    "and",
    "or",
    "not",
    "iff",
    "forall",
    "exists",
    "fun",
    "let",
    "with",
    "from",
    "this",
    "that",
    "import",
    "mathlib",
    "sorry",
}


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_'.]*|[0-9]+", text or ""):
        low = tok.lower()
        if low in _STOP:
            continue
        # Keep multi-char ids always; keep single-char binders and digits too
        # (algebraic goals often share only `n`, `0`, …).
        if len(tok) > 1 or tok.isdigit() or (len(tok) == 1 and tok.isalpha()):
            out.add(low)
    return out


def locked_goal_text(challenge: str) -> str:
    """Best-effort locked goal / theorem statement text (no Lean)."""

    match = re.search(
        r"(?ms)^\s*(?:theorem|lemma)\s+[A-Za-z_][\w']*[^{:=]*?:=\s*by",
        challenge or "",
    )
    if match:
        return match.group(0)
    parts = re.findall(
        r"(?ms)^\s*(?:theorem|lemma)\s+.+$",
        challenge or "",
    )
    return parts[-1] if parts else (challenge or "")


def manifest_answer_names(problem: Any) -> set[str]:
    meta = getattr(problem, "metadata", None) or {}
    manifest = meta.get("__manifest__", {}) if isinstance(meta, dict) else {}
    if not isinstance(manifest, dict):
        return set()
    names: set[str] = set()
    for key in ("definition_names", "numeric_answer_names", "theorem_names"):
        values = manifest.get(key) or []
        if isinstance(values, (list, tuple)):
            names.update(str(v) for v in values)
    return names


def is_goal_shaped(
    statement: str,
    *,
    goal_text: str,
    answer_names: Iterable[str] = (),
    min_overlap: int = 2,
) -> bool:
    """True when a lemma statement shares structure/tokens with the locked goal.

    Rejects full-goal restatements (caller still uses graph.add_verified restatement
    filter). Accepts IsLeast / membership / answer-def name hits as soft signals.
    """

    stmt = (statement or "").strip()
    if not stmt or len(stmt) > 400:
        return False
    goal = goal_text or ""
    if normalize_statement(stmt) == normalize_statement(goal):
        return False
    soft = bool(
        re.search(r"\bIsLeast\b|\bIsGreatest\b|\bIsMin\b|\bIsMax\b", stmt)
        or re.search(r"↔|\\iff|\bIff\b", stmt)
        or re.search(r"∈|\\in", stmt)
    )
    names = {n.lower() for n in answer_names if n}
    stmt_tokens = _tokens(stmt)
    if names and stmt_tokens & names:
        return True
    if soft:
        return True
    goal_tokens = _tokens(goal)
    overlap = len(stmt_tokens & goal_tokens)
    if overlap >= min_overlap:
        return True
    if goal_tokens and overlap / max(1, len(stmt_tokens)) >= 0.5 and overlap >= 1:
        return True
    return False


@dataclass
class FailedAttemptNotebook:
    """Capped English negative memory across residual rounds."""

    max_bullets: int = 8
    max_chars: int = 120
    bullets: list[str] = field(default_factory=list)

    def clear(self) -> None:
        self.bullets.clear()

    def size(self) -> int:
        return len(self.bullets)

    def fingerprint(self) -> tuple[str, ...]:
        return tuple(self.bullets)

    def add(self, text: str) -> bool:
        """Append one bullet; return True if the notebook content changed."""

        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if not cleaned:
            return False
        # Durable artifacts must stay English — drop non-ASCII letters.
        cleaned = cleaned.encode("ascii", "ignore").decode("ascii").strip()
        if not cleaned:
            return False
        if len(cleaned) > self.max_chars:
            cleaned = cleaned[: max(1, self.max_chars - 3)].rstrip() + "..."
        if cleaned in self.bullets:
            return False
        self.bullets.append(cleaned)
        if len(self.bullets) > self.max_bullets:
            self.bullets = self.bullets[-self.max_bullets :]
        return True

    def as_prompt_block(self) -> str:
        if not self.bullets:
            return ""
        lines = "\n".join(f"- {b}" for b in self.bullets)
        return (
            "Avoid repeating these prior residual failures (lab notebook):\n" + lines
        )


def textwrap_dedent_body(body: str) -> str:
    lines = (body or "").splitlines()
    cleaned: list[str] = []
    for line in lines:
        if not line.strip():
            cleaned.append("")
            continue
        if line[:1] in " \t":
            cleaned.append(re.sub(r"^[ \t]+", "", line, count=1))
        else:
            cleaned.append(line)
    if not any(ln.strip() for ln in cleaned):
        return ""
    return "\n".join(cleaned).strip()


def _have_blocks_with_bodies(source: str) -> list[tuple[str, str]]:
    """Return (statement, certificate_body) for each `have … := by …` block."""

    out: list[tuple[str, str]] = []
    pattern = re.compile(
        r"(?ms)^[ \t]*have\s+[A-Za-z_][\w']*\s*:\s*(.+?)\s*:=\s*by[ \t]*\n"
        r"((?:[ \t]+.+\n?)*)"
    )
    for m in pattern.finditer(source or ""):
        stmt = re.sub(r"\s+", " ", m.group(1)).strip()
        body = textwrap_dedent_body(m.group(2))
        if stmt and body:
            out.append((stmt, body))
    if out:
        return out
    # Header-only fallback from nearmiss (empty certificate → skip promote).
    from .nearmiss import extract_verified_have_texts

    return [(stmt, "") for stmt, _block in extract_verified_have_texts(source or "")]


def promote_goal_shaped_from_text(
    graph: VerifiedProgressGraph,
    *,
    source: str,
    goal_text: str,
    context: str,
    answer_names: Iterable[str] = (),
    lean_accepted: bool = True,
    provenance: dict[str, Any] | None = None,
    max_promote: int = 6,
) -> int:
    """Extract `have` facts from near-miss text and promote goal-shaped ones.

    Caller decides whether Lean already accepted the surrounding fragment; this
    helper does not talk to Lean. Returns count of newly inserted nodes.
    """

    if not source or not lean_accepted:
        return 0
    promoted = 0
    base_prov = dict(provenance or {})
    base_prov.setdefault("source", "goal_shaped_extract")
    for statement, certificate in _have_blocks_with_bodies(source):
        if promoted >= max_promote:
            break
        if not is_goal_shaped(
            statement, goal_text=goal_text, answer_names=answer_names
        ):
            continue
        if not certificate or re.search(
            r"\b(?:sorry|admit|axiom)\b", certificate, re.I
        ):
            continue
        before = len(graph.nodes)
        node = graph.add_verified(
            statement=statement,
            proof=certificate,
            certificate=certificate,
            context=context,
            original_goal=goal_text,
            lean_accepted=True,
            provenance=base_prov,
        )
        if node is not None and len(graph.nodes) > before:
            promoted += 1
    return promoted


def promote_goal_shaped_from_graph_routes(
    graph: VerifiedProgressGraph,
    *,
    goal_text: str,
    answer_names: Iterable[str] = (),
) -> int:
    """Count already-banked nodes that look goal-shaped (telemetry helper)."""

    names = list(answer_names)
    return sum(
        1
        for node in graph.nodes.values()
        if is_goal_shaped(node.statement, goal_text=goal_text, answer_names=names)
    )


def build_fail_telemetry(
    *,
    failure_kind: str,
    residual_route_mode: str,
    progress_graph: VerifiedProgressGraph | None,
    residual_rounds_ran: int,
    residual_stall_reason: str = "",
    extracts_promoted: int = 0,
    greedy_close_attempted: int = 0,
    notebook_size: int = 0,
    last_residual_detail: str = "",
    stages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """English metadata keys for terminal FAIL / exhausted AgentResult."""

    graph_md = (
        progress_graph.metadata()
        if progress_graph is not None
        else {
            "nodes_saved": 0,
            "nodes_reused": 0,
            "reuse_events": 0,
            "decisive_reuses": 0,
        }
    )
    detail = re.sub(r"\s+", " ", (last_residual_detail or "").strip())
    if len(detail) > 240:
        detail = detail[:239].rstrip() + "..."
    detail = detail.encode("ascii", "ignore").decode("ascii")
    return {
        "failure_kind": failure_kind or "other",
        "residual_route_mode": residual_route_mode or "either",
        "progress_graph": graph_md,
        "residual_rounds_ran": int(residual_rounds_ran),
        "residual_stall_reason": residual_stall_reason or "",
        "extracts_promoted": int(extracts_promoted),
        "greedy_close_attempted": int(greedy_close_attempted),
        "notebook_size": int(notebook_size),
        "last_residual_detail": detail,
        "bank_nodes_saved": int(graph_md.get("nodes_saved", 0) or 0),
        "bank_nodes_reused": int(graph_md.get("nodes_reused", 0) or 0),
        "bank_decisive_reuses": int(graph_md.get("decisive_reuses", 0) or 0),
        "stages": list(stages or []),
    }
