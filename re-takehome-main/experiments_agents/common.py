"""Shared helpers for science arms (S/R/H)."""

from __future__ import annotations

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


def extract_lean(text: str, fallback: str) -> str:
    """Extract one complete Lean file from an LLM response (baseline-compatible)."""

    fenced = re.findall(
        r"```(?:lean|lean4)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE
    )
    if fenced:
        return fenced[-1].strip() + "\n"
    stripped = text.strip()
    import_at = stripped.find("import ")
    if import_at >= 0:
        return stripped[import_at:].strip() + "\n"
    return fallback


def format_messages(messages: list[dict[str, Any]], *, limit: int = 6000) -> str:
    chunks: list[str] = []
    for message in messages:
        severity = message.get("severity", "message")
        pos = message.get("pos")
        data = str(message.get("data", "")).strip()
        chunks.append(f"{severity} at {pos}: {data}")
    text = "\n\n".join(chunks)
    return text[-limit:]


def normalize_diagnostics(text: str) -> str:
    """Collapse whitespace for no-progress detection."""

    return re.sub(r"\s+", " ", (text or "").strip())


def count_model_calls(model: str, calls_q: int, calls_g: int) -> tuple[int, int]:
    if model == QWEN:
        return calls_q + 1, calls_g
    if model == GPT_OSS:
        return calls_q, calls_g + 1
    return calls_q, calls_g
