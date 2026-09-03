"""Minimal single-agent Lean repair loop baseline.

This is intentionally plain: one model, one chronological feedback loop, and
no search or multi-agent orchestration. It is a working example of the public
Agent API, not an optimized solver.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from typing import Any

from re_harness import AgentResult, Problem, Services
from re_harness.models import ALLOWED_MODELS, MODEL_A


DEFAULT_MAX_TURNS = 25
DEFAULT_MAX_TOKENS = 12000


@dataclass(frozen=True)
class Attempt:
    turn: int
    accepted: bool
    timed_out: bool
    message_count: int


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
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


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
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


def _env_model() -> str:
    model = os.environ.get("BASELINE_MODEL", MODEL_A).strip()
    if model not in ALLOWED_MODELS:
        allowed = ", ".join(sorted(ALLOWED_MODELS))
        raise ValueError(f"BASELINE_MODEL must be one of: {allowed}")
    return model


def _extract_lean(text: str, fallback: str) -> str:
    """Extract one complete Lean file from an LLM response."""

    fenced = re.findall(r"```(?:lean|lean4)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced[-1].strip() + "\n"
    stripped = text.strip()
    import_at = stripped.find("import ")
    if import_at >= 0:
        return stripped[import_at:].strip() + "\n"
    return fallback


def _format_messages(messages: list[dict[str, Any]], *, limit: int = 6000) -> str:
    chunks: list[str] = []
    for message in messages:
        severity = message.get("severity", "message")
        pos = message.get("pos")
        data = str(message.get("data", "")).strip()
        chunks.append(f"{severity} at {pos}: {data}")
    text = "\n\n".join(chunks)
    return text[-limit:]


class SimpleBaselineAgent:
    def __init__(
        self,
        *,
        model: str | None = None,
        max_turns: int | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        self.model = model or _env_model()
        self.max_turns = max_turns or _env_int(
            "BASELINE_MAX_TURNS", DEFAULT_MAX_TURNS, minimum=1, maximum=25
        )
        self.max_tokens = max_tokens or _env_int(
            "BASELINE_MAX_TOKENS", DEFAULT_MAX_TOKENS, minimum=1000, maximum=32000
        )
        self.temperature = (
            temperature
            if temperature is not None
            else _env_float("BASELINE_TEMPERATURE", 0.2, minimum=0.0, maximum=2.0)
        )

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        candidate = problem.challenge
        attempts: list[Attempt] = []
        feedback = ""

        for turn in range(1, self.max_turns + 1):
            is_last = turn == self.max_turns
            response = await services.llm.complete(
                model=self.model,
                messages=self._messages(problem, feedback=feedback, turn=turn, is_last=is_last),
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            candidate = _extract_lean(response.content, fallback=candidate)
            services.checkpoint(candidate, {"baseline_turn": turn, "model": self.model})

            check = await services.lean.check_file(candidate)
            attempts.append(
                Attempt(
                    turn=turn,
                    accepted=check.accepted,
                    timed_out=check.timed_out,
                    message_count=len(check.messages),
                )
            )
            if check.accepted:
                return AgentResult(
                    candidate,
                    {
                        "baseline": "simple",
                        "model": self.model,
                        "turns": turn,
                        "accepted_by_repl": True,
                        "attempts": [asdict(attempt) for attempt in attempts],
                    },
                )
            feedback = _format_messages(check.messages)
            if check.timed_out and not feedback:
                feedback = "Lean timed out while checking the previous candidate."

        return AgentResult(
            candidate,
            {
                "baseline": "simple",
                "model": self.model,
                "turns": self.max_turns,
                "accepted_by_repl": False,
                "attempts": [asdict(attempt) for attempt in attempts],
            },
        )

    def _messages(
        self, problem: Problem, *, feedback: str, turn: int, is_last: bool
    ) -> list[dict[str, str]]:
        instructions = [
            "You are writing a complete Lean 4 file using Mathlib.",
            "Return only the complete Lean code, preferably in one ```lean code block.",
            "Preserve the theorem names and statements from the challenge.",
            "Do not use sorry, admit, axioms, or unsafe escapes.",
            "The file must compile as-is.",
        ]
        if is_last:
            instructions.append(
                "This is your final attempt. Return the best complete Lean file only."
            )
        user = [
            f"Problem id: {problem.id}",
            f"Baseline turn: {turn}/{self.max_turns}",
            "",
            "Problem description:",
            problem.description,
            "",
            "Challenge Lean file:",
            "```lean",
            problem.challenge,
            "```",
        ]
        if feedback:
            user.extend([
                "",
                "Lean compiler feedback from the previous candidate:",
                "```text",
                feedback,
                "```",
            ])
        return [
            {"role": "system", "content": "\n".join(instructions)},
            {"role": "user", "content": "\n".join(user)},
        ]


def create_agent() -> SimpleBaselineAgent:
    return SimpleBaselineAgent()

