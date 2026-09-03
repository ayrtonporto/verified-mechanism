"""Applicant-facing agent protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

if False:  # pragma: no cover - imports for type checkers without cycles
    from .lean import LeanClient
    from .llm import LLMClient

JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]


@dataclass(frozen=True)
class Problem:
    id: str
    description: str
    challenge: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    solution: str
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)


class Services:
    """Capabilities provided to an applicant agent for one problem."""

    def __init__(self, *, llm: "LLMClient", lean: "LeanClient", checkpoint):
        self.llm = llm
        self.lean = lean
        self._checkpoint = checkpoint

    def checkpoint(
        self, source: str, metadata: Mapping[str, JSONValue] | None = None
    ) -> None:
        """Atomically preserve a candidate for timeout/crash recovery."""

        self._checkpoint(source, dict(metadata or {}))


@runtime_checkable
class Agent(Protocol):
    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        """Return the best complete Lean source for ``problem``."""

