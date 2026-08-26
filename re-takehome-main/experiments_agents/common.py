"""Shared helpers for science arms (S/R/H)."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from re_harness.models import ALLOWED_MODELS, MODEL_A, MODEL_B

QWEN = MODEL_A
GPT_OSS = MODEL_B

REPAIR_INVARIANTS = (
    "Repair invariants (mandatory):",
    "- Do not use sorry or admit.",
    "- Do not introduce new axioms or equivalent proof bypasses.",
    "- Do not alter theorem names or statements to weaken the problem.",
    "- Repair the actual proof obligation from the challenge.",
    "- When the diagnostic is local, prefer a minimal correction.",
    "- Return a complete Lean 4 file that compiles as-is (Mathlib imports preserved).",
)


def env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def require_model(model: str) -> str:
    model = model.strip()
    if model not in ALLOWED_MODELS:
        allowed = ", ".join(sorted(ALLOWED_MODELS))
        raise ValueError(f"model must be one of: {allowed}")
    return model


def extract_lean_ex(text: str, fallback: str) -> tuple[str, bool]:
    """Extract one complete Lean file; also report whether extraction succeeded.

    Returns ``(source, extracted_ok)``. ``extracted_ok`` is False when we could
    not find a fenced block or an ``import`` anchor and fell back to the previous
    candidate — the caller can then avoid misreading a re-check of identical
    source as mathematical stagnation.
    """

    fenced = re.findall(
        r"```(?:lean|lean4)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE
    )
    if fenced:
        return fenced[-1].strip() + "\n", True
    stripped = text.strip()
    import_at = stripped.find("import ")
    if import_at >= 0:
        return stripped[import_at:].strip() + "\n", True
    return fallback, False


def extract_lean(text: str, fallback: str) -> str:
    """Baseline-compatible wrapper around :func:`extract_lean_ex`."""

    return extract_lean_ex(text, fallback)[0]


def format_messages(messages: list[dict[str, Any]], *, limit: int = 6000) -> str:
    """Render Lean diagnostics, **errors first** (root cause preserved).

    The kit's raw diagnostics can bury the first/root error under cascading
    follow-on errors; keeping only the tail (old behaviour) sometimes dropped the
    actual cause. We order error-severity messages first, then the rest, and if
    truncation is still required we keep a head+tail with an explicit marker so
    the primary error survives.
    """

    errors: list[str] = []
    others: list[str] = []
    for message in messages:
        severity = message.get("severity", "message")
        pos = message.get("pos")
        data = str(message.get("data", "")).strip()
        chunk = f"{severity} at {pos}: {data}"
        (errors if severity == "error" else others).append(chunk)
    text = "\n\n".join(errors + others)
    if len(text) <= limit:
        return text
    head = (limit * 3) // 5
    tail = limit - head
    return text[:head] + "\n\n…[diagnostics truncated]…\n\n" + text[-tail:]


# --- universal candidate hygiene (source-agnostic, applied to every problem) ---

_DECL_RE = re.compile(
    r"(?:^|\n)\s*(?:noncomputable\s+)?(?:theorem|lemma|def|abbrev)\s+"
    r"([A-Za-z_][A-Za-z0-9_.']*)"
)
_AXIOM_RE = re.compile(r"(?:^|\n)\s*axiom\s+")
_SORRY_RE = re.compile(r"\bsorry\b")
_ADMIT_RE = re.compile(r"\badmit\b")


def sha16(source: str) -> str:
    """Short stable content hash for candidate/parent provenance."""

    return hashlib.sha256((source or "").encode("utf-8")).hexdigest()[:16]


def required_decl_names(source: str) -> list[str]:
    """Names of theorem/lemma/def/abbrev declarations found in ``source``."""

    return _DECL_RE.findall(source or "")


def integrity_check(candidate: str, challenge: str) -> tuple[bool, list[str]]:
    """Guard against a REPL-accepted candidate that silently cheats.

    ``lean.check_file`` proves a file is valid Lean, not that it still proves the
    *original* challenge. Conservatively require every declaration named in the
    challenge to still be declared, and reject forbidden escapes. Name-level only
    (whitespace/format tolerant); the private comparator is the final authority.
    """

    errors: list[str] = []
    have = set(required_decl_names(candidate))
    for name in required_decl_names(challenge):
        if name not in have:
            errors.append(f"missing required declaration `{name}`")
    if _SORRY_RE.search(candidate or ""):
        errors.append("uses `sorry`")
    if _ADMIT_RE.search(candidate or ""):
        errors.append("uses `admit`")
    if _AXIOM_RE.search(candidate or ""):
        errors.append("declares an `axiom`")
    return (not errors, errors)


def diagnostic_category(messages: list[dict[str, Any]]) -> str:
    """Coarse, deterministic class of the primary Lean error (for routing/logs)."""

    err = next(
        (str(m.get("data", "")) for m in messages if m.get("severity") == "error"),
        "",
    ).lower()
    if not err:
        return "none"
    if "unexpected" in err or "unterminated" in err or (
        "expected" in err and "token" in err
    ):
        return "parse"
    if "unknown identifier" in err or "unknown constant" in err or "unknown" in err:
        return "unknown_ident"
    if "type mismatch" in err or "has type" in err:
        return "type"
    if "unsolved goals" in err:
        return "unsolved_goal"
    if "failed" in err or "tactic" in err:
        return "tactic_failed"
    return "other"


# Universal closing-tactic battery (same for every problem — no problem-specific
# lemmas). Ordered cheap→heavy; heavy ones (decide/nlinarith) rely on the Lean
# timeout to bound wall time. Used both as a zero-model-cost "finisher" sweep and
# as a menu the models are told about.
CLOSING_TACTICS: tuple[str, ...] = (
    "simp_all",
    "omega",
    "norm_num",
    "decide",
    "nlinarith",
    "positivity",
    "aesop",
    "norm_num <;> omega",
    "simp_all <;> omega",
    "constructor <;> omega",
)

TACTIC_MENU = (
    "Prefer Mathlib automation to close routine goals: `omega` (linear nat/int "
    "arithmetic), `decide` (finite/decidable props), `norm_num` (numeric), "
    "`simp`/`simp_all`, `nlinarith`/`positivity` (inequalities), `ring`/`field_simp` "
    "(algebra), `aesop`. Break the goal into `have` steps and discharge each with "
    "the strongest applicable tactic; wrap uncertain steps in `first | t1 | t2` and "
    "combine with `<;>`."
)


def tactic_sweep_variants(
    challenge: str, tactics: tuple[str, ...] = CLOSING_TACTICS
) -> list[tuple[str, str]]:
    """Zero-model-cost candidates: challenge with its ``sorry`` placeholder(s)
    replaced by each single closing tactic. Empty if the challenge has no
    ``sorry`` to fill. Universal (same battery for every problem)."""

    if not _SORRY_RE.search(challenge or ""):
        return []
    return [(t, _SORRY_RE.sub(lambda _m, _t=t: _t, challenge)) for t in tactics]


def candidate_rank(
    *, accepted: bool, integrity_ok: bool, extracted_ok: bool,
    timed_out: bool, error_count: int, message_count: int,
) -> list[int]:
    """Total order over candidates (larger is better) for a ``best_so_far`` seed.

    Only used to choose which candidate to repair next / return at the end — it
    never decides correctness (that stays the comparator). Prevents regressing
    from an elaborating proof to a parse error and then repairing the regression.
    """

    return [
        1 if accepted else 0,
        1 if integrity_ok else 0,
        1 if extracted_ok else 0,
        0 if timed_out else 1,
        -error_count,
        -message_count,
    ]


def normalize_diagnostics(text: str) -> str:
    """Collapse whitespace for no-progress detection."""

    return re.sub(r"\s+", " ", (text or "").strip())


def count_model_calls(model: str, calls_q: int, calls_g: int) -> tuple[int, int]:
    if model == QWEN:
        return calls_q + 1, calls_g
    if model == GPT_OSS:
        return calls_q, calls_g + 1
    return calls_q, calls_g
