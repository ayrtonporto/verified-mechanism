"""Dependency-aware program coordinator for BridgePortfolio.

``BridgePortfolioAgent`` deliberately owns one immutable theorem header.  That is the
right safety boundary for theorem proving, but a benchmark problem can be a small Lean
*program*: first an answer ``abbrev`` or solution-set ``def``, then one or more theorems
which refer to it.  Splitting every ``sorry`` into an independent file loses precisely
that dependency.

This coordinator restores the program structure without weakening the theorem lock:

1. value/definition holes receive a small portfolio of *hole replacements*;
2. every replacement is grafted into the original declaration and elaborated by Lean;
3. the accepted definition candidates become immutable context for theorem slots;
4. theorem slots are solved by BridgePortfolio, still under machine-owned headers;
5. independently solved sibling theorems are exposed on a second pass; and
6. only a complete, ``sorry``-free reconstruction of the original program is returned
   as solved and checkpointed.

Definition candidates are branches rather than commitments.  A syntactically valid but
mathematically wrong numeric answer will make its downstream theorem fail, after which
the next candidate is tried.  All routing is structural (declaration kind and dependency
order), never keyed to a problem id.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from re_harness import AgentResult, Problem, Services

from .bridgeportfolio import BridgePortfolioAgent
from .candidate_guard import definition_is_circular
from .common import (
    GPT_OSS,
    QWEN,
    count_model_calls,
    env_int,
    format_messages,
    integrity_check,
    required_decl_names,
    strict_integrity_check,
)
from .multitheorem import _block_has_sorry, split_declarations
from .verified_progress import VerifiedProgressGraph


_DECL_INFO = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(theorem|lemma|def|abbrev|instance|example)\s+"
    r"([A-Za-z_][A-Za-z0-9_.']*)\b",
    re.MULTILINE,
)
_SORRY = re.compile(r"\bsorry\b")
_FENCE = re.compile(r"```(?:lean|lean4)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_FORBIDDEN_REPLACEMENT = re.compile(
    r"\b(?:sorry|admit|axiom|native_decide)\b|"
    r"(?:^|\n)\s*(?:theorem|lemma|def|abbrev|instance|example)\b",
    re.IGNORECASE,
)
_NUMERIC_LITERAL_INSTRUCTION = re.compile(
    r"must\s+be\s+(?:an?\s+)?numeric\s+literal", re.IGNORECASE
)
_TACTIC_REPLACEMENT = re.compile(
    r"^(?:exact|refine|apply|intro|intros|simp|simpa|norm_num|decide|constructor|"
    r"rfl|aesop|omega|linarith|nlinarith|ring|ring_nf|change|show|let|have|rw|"
    r"rcases|cases|ext|first|repeat|all_goals|classical|unfold|field_simp|"
    r"positivity|contradiction|exfalso)\b"
)


def declaration_info(block: str) -> tuple[str, str] | None:
    """Return ``(kind, name)`` for one top-level declaration block."""

    match = _DECL_INFO.search(block or "")
    return (match.group(1), match.group(2)) if match else None


def _program_source(preamble: str, blocks: list[str]) -> str:
    pieces = [preamble.rstrip()] if preamble.strip() else ["import Mathlib"]
    pieces.extend(block.rstrip() for block in blocks if block.strip())
    return "\n\n".join(pieces).rstrip() + "\n"


def _replace_single_sorry(block: str, replacement: str) -> str | None:
    """Graft a candidate into the unique ``sorry`` token, preserving indentation."""

    holes = list(_SORRY.finditer(block or ""))
    if len(holes) != 1:
        return None
    candidate = textwrap.dedent(replacement or "").strip()
    if not candidate or len(candidate) > 20_000 or _FORBIDDEN_REPLACEMENT.search(candidate):
        return None
    hole = holes[0]
    # Definition prompts explicitly request tactics when the locked declaration already
    # owns `:= by`, but models occasionally return one redundant `by` wrapper.  Strip it
    # only when the hole is the direct body of that machine-owned tactic block; a `by`
    # returned for a nested term hole remains semantically meaningful and untouched.
    prefix = block[: hole.start()]
    owned_tactic_block = re.search(r":=\s*by\s*$", prefix) is not None
    if owned_tactic_block:
        wrapper = re.match(r"^by[ \t]*(?:\r?\n|$)", candidate)
        if wrapper is not None:
            candidate = candidate[wrapper.end() :].strip()
            if not candidate:
                return None
        # The protocol permits either a term or tactics. Inside an already-owned
        # `:= by` block, a bare set literal, tuple, lambda, match, or parenthesized term
        # is not a tactic; graft it through `exact`. Recognized tactic prefixes remain
        # byte-for-byte model output.
        if _TACTIC_REPLACEMENT.match(candidate) is None:
            candidate = f"exact ({candidate})"
    line_start = block.rfind("\n", 0, hole.start()) + 1
    continuation = " " * (hole.start() - line_start)
    candidate = candidate.replace("\n", "\n" + continuation)
    return block[: hole.start()] + candidate + block[hole.end() :]


def _extract_json(text: str) -> dict[str, Any] | None:
    candidates = re.findall(r"```(?:json)?\s*\n(.*?)```", text or "", re.DOTALL)
    candidates.append(text or "")
    for candidate in candidates:
        left, right = candidate.find("{"), candidate.rfind("}")
        if left < 0 or right <= left:
            continue
        try:
            parsed = json.loads(candidate[left : right + 1])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def parse_definition_candidates(text: str, *, numeric: bool, maximum: int) -> list[str]:
    """Extract sanitized replacements from the definition-portfolio response."""

    raw: list[Any] = []
    payload = _extract_json(text)
    if payload and isinstance(payload.get("candidates"), list):
        raw.extend(payload["candidates"])
    if not raw:
        raw.extend(_FENCE.findall(text or ""))
    candidates: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = item.get("replacement", "") if isinstance(item, dict) else item
        candidate = textwrap.dedent(str(value)).strip()
        if candidate.startswith(":="):
            candidate = candidate[2:].strip()
        if numeric and not re.fullmatch(r"[0-9]+", candidate):
            continue
        if (
            not candidate
            or len(candidate) > 20_000
            or _FORBIDDEN_REPLACEMENT.search(candidate)
            or candidate in seen
        ):
            continue
        seen.add(candidate)
        candidates.append(candidate)
        if len(candidates) >= maximum:
            break
    return candidates


def _manifest_name_set(problem: Problem, key: str) -> set[str]:
    manifest = problem.metadata.get("__manifest__", {})
    if not isinstance(manifest, dict):
        return set()
    values = manifest.get(key, [])
    if not isinstance(values, (list, tuple)):
        return set()
    return {str(value) for value in values}


def _is_numeric_definition(problem: Problem, block: str, name: str) -> bool:
    if name in _manifest_name_set(problem, "numeric_answer_names"):
        return True
    # Standalone experiment drivers historically omitted manifest fields from
    # Problem.metadata.  Preserve the explicit user instruction as a safe fallback.
    return bool(_NUMERIC_LITERAL_INSTRUCTION.search(block) and re.search(r":\s*ℕ\s*:=", block))


@dataclass
class DefinitionStats:
    calls_q: int = 0
    calls_g: int = 0
    lean_checks: int = 0
    proposed: int = 0
    accepted: int = 0
    repaired: int = 0
    rejected_circular: int = 0
    canonical_retry_calls: int = 0


class DefinitionPortfolio:
    """Propose and Lean-elaborate replacements for one immutable definition hole."""

    def __init__(
        self,
        *,
        portfolio_calls: int | None = None,
        max_candidates: int | None = None,
        max_accepted: int | None = None,
        check_timeout_s: int | None = None,
        canonical_retry_calls: int | None = None,
    ):
        self.portfolio_calls = portfolio_calls if portfolio_calls is not None else env_int(
            "BP_DEF_PORTFOLIO_CALLS", 2, minimum=1, maximum=4
        )
        self.max_candidates = max_candidates if max_candidates is not None else env_int(
            "BP_DEF_MAX_CANDIDATES", 8, minimum=1, maximum=16
        )
        self.max_accepted = max_accepted if max_accepted is not None else env_int(
            "BP_DEF_MAX_ACCEPTED", 3, minimum=1, maximum=6
        )
        self.check_timeout_s = check_timeout_s if check_timeout_s is not None else env_int(
            "BP_DEF_CHECK_TIMEOUT_S", 90, minimum=10, maximum=240
        )
        self.canonical_retry_calls = (
            canonical_retry_calls
            if canonical_retry_calls is not None
            else env_int("BP_DEF_CANONICAL_RETRY_CALLS", 2, minimum=1, maximum=3)
        )
        self.stats = DefinitionStats()

    async def _complete(self, services: Services, *, model: str, messages, temperature: float):
        response = await services.llm.complete(
            model=model,
            messages=messages,
            max_tokens=5000,
            temperature=temperature,
        )
        self.stats.calls_q, self.stats.calls_g = count_model_calls(
            model, self.stats.calls_q, self.stats.calls_g
        )
        return response

    @staticmethod
    def _accepted(check) -> bool:
        return bool(
            check
            and check.accepted
            and not getattr(check, "has_sorry", False)
            and not getattr(check, "timed_out", False)
        )

    async def solve(
        self,
        problem: Problem,
        services: Services,
        *,
        preamble: str,
        context_blocks: list[str],
        block: str,
        time_left: Callable[[], float],
        dependent_blocks: list[str] | None = None,
    ) -> list[str]:
        info = declaration_info(block)
        if info is None:
            return []
        _kind, name = info
        numeric = _is_numeric_definition(problem, block, name)
        locked = _program_source(preamble, context_blocks + [block])
        requirement = (
            "Every replacement must be one ASCII decimal literal."
            if numeric
            else "A replacement may be a Lean expression or a tactic replacing the hole."
        )
        system = (
            "Solve one immutable Lean definition hole. Return only JSON of the form "
            '{"candidates":[{"replacement":"...","reason":"..."}]}. '
            "Each replacement is substituted for the exact word `sorry`; do not repeat "
            "the declaration, imports, or `:=`. If the locked declaration already says "
            "`:= by`, return tactics such as `exact ...`, not another `by`. Never use "
            "sorry, admit, axioms, theorem declarations, or native_decide. Propose "
            f"mathematically distinct candidates when uncertainty remains. {requirement}"
        )
        if not numeric:
            system += (
                " The answer must be a closed canonical object. Never define it by the "
                "same predicate or equation that a downstream theorem is meant to "
                "characterise; enumerate or otherwise compute the answer instead."
            )
        user = (
            f"Problem description:\n{problem.description}\n\n"
            f"Definition to complete: `{name}`\n"
            f"Exact locked program:\n```lean\n{locked}\n```"
        )

        async def one(index: int):
            if time_left() < 30:
                return ""
            model = GPT_OSS if index % 2 == 0 else QWEN
            try:
                response = await self._complete(
                    services,
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.25 + 0.25 * index,
                )
                return response.content or ""
            except Exception:
                return ""

        texts = await asyncio.gather(*(one(i) for i in range(self.portfolio_calls)))
        candidates: list[str] = []
        seen: set[str] = set()
        for text in texts:
            for candidate in parse_definition_candidates(
                text, numeric=numeric, maximum=self.max_candidates
            ):
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)
                if len(candidates) >= self.max_candidates:
                    break
        self.stats.proposed += len(candidates)

        accepted: list[str] = []
        failed: tuple[str, str] | None = None
        circular_before = self.stats.rejected_circular
        for candidate in candidates:
            if time_left() < 20:
                break
            solved_block = _replace_single_sorry(block, candidate)
            if solved_block is None:
                continue
            source = _program_source(preamble, context_blocks + [solved_block])
            try:
                check = await services.lean.check_file(source, timeout_s=self.check_timeout_s)
                self.stats.lean_checks += 1
            except Exception:
                continue
            if self._accepted(check):
                circular = False
                if not numeric:
                    circular, extra_checks = await definition_is_circular(
                        services,
                        preamble=preamble,
                        context_blocks=context_blocks,
                        definition_block=solved_block,
                        dependent_blocks=dependent_blocks or [],
                        timeout_s=min(45, self.check_timeout_s),
                    )
                    self.stats.lean_checks += extra_checks
                if circular:
                    self.stats.rejected_circular += 1
                    if failed is None:
                        failed = (
                            candidate,
                            "Semantic answer-shape failure: the definition makes a "
                            "downstream characterisation tautological. Return a closed "
                            "canonical/enumerated answer instead.",
                        )
                    continue
                accepted.append(solved_block)
                self.stats.accepted += 1
                if len(accepted) >= self.max_accepted:
                    break
            elif failed is None:
                failed = (candidate, format_messages(check.messages, limit=3000))

        # One focused syntax/type repair is useful for structured objects (sets, maps,
        # tuples). Numeric literals already elaborate or fail the downstream theorem.
        if not accepted and failed is not None and not numeric and time_left() >= 30:
            bad, diagnostics = failed
            repair_user = (
                f"Exact locked program:\n```lean\n{locked}\n```\n\n"
                f"Failed replacement:\n```lean\n{bad}\n```\n\n"
                f"Lean feedback:\n{diagnostics}\n\nReturn corrected JSON candidates."
            )
            try:
                response = await self._complete(
                    services,
                    model=GPT_OSS,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": repair_user},
                    ],
                    temperature=0.15,
                )
            except Exception:
                response = None
            if response is not None:
                for candidate in parse_definition_candidates(
                    response.content or "", numeric=False, maximum=self.max_candidates
                ):
                    seen.add(candidate)
                    solved_block = _replace_single_sorry(block, candidate)
                    if solved_block is None:
                        continue
                    source = _program_source(preamble, context_blocks + [solved_block])
                    try:
                        check = await services.lean.check_file(
                            source, timeout_s=self.check_timeout_s
                        )
                        self.stats.lean_checks += 1
                    except Exception:
                        continue
                    if self._accepted(check):
                        circular, extra_checks = await definition_is_circular(
                            services,
                            preamble=preamble,
                            context_blocks=context_blocks,
                            definition_block=solved_block,
                            dependent_blocks=dependent_blocks or [],
                            timeout_s=min(45, self.check_timeout_s),
                        )
                        self.stats.lean_checks += extra_checks
                        if circular:
                            self.stats.rejected_circular += 1
                            continue
                        accepted.append(solved_block)
                        self.stats.accepted += 1
                        self.stats.repaired += 1
                        break

        # A circular candidate is mathematical evidence, not merely a syntax error: the
        # model found the defining predicate but failed to compute its extension.  Give
        # independent models one bounded canonicalization round with the full problem
        # and downstream characterisations.  This is universal object synthesis; no
        # problem id, expected element, or known proof is embedded here.
        if (
            not numeric
            and not accepted
            and self.stats.rejected_circular > circular_before
            and self.canonical_retry_calls > 0
            and time_left() >= 45
        ):
            downstream = "\n\n".join((dependent_blocks or [])[:3])
            canonical_user = (
                f"Problem description:\n{problem.description}\n\n"
                f"Definition to compute: `{name}`\n"
                f"Exact locked program:\n```lean\n{locked}\n```\n\n"
                f"Downstream immutable characterisations:\n```lean\n{downstream}\n```\n\n"
                "Earlier candidates were rejected because they merely restated the "
                "characterised predicate. Compute a closed canonical object instead "
                "(for a finite set, enumerate its elements extensionally). Return "
                "mathematically distinct JSON replacements and never repeat the "
                "predicate as a set-builder definition."
            )

            async def canonical_one(index: int):
                if time_left() < 30:
                    return ""
                model = GPT_OSS if index % 2 == 0 else QWEN
                try:
                    response = await self._complete(
                        services,
                        model=model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": canonical_user},
                        ],
                        temperature=0.35 + 0.2 * index,
                    )
                    self.stats.canonical_retry_calls += 1
                    return response.content or ""
                except Exception:
                    return ""

            retry_texts = await asyncio.gather(*(
                canonical_one(index) for index in range(self.canonical_retry_calls)
            ))
            retry_candidates: list[str] = []
            for text in retry_texts:
                for candidate in parse_definition_candidates(
                    text, numeric=False, maximum=self.max_candidates
                ):
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    retry_candidates.append(candidate)
                    if len(retry_candidates) >= self.max_candidates:
                        break
            self.stats.proposed += len(retry_candidates)

            for candidate in retry_candidates:
                if time_left() < 20:
                    break
                solved_block = _replace_single_sorry(block, candidate)
                if solved_block is None:
                    continue
                source = _program_source(preamble, context_blocks + [solved_block])
                try:
                    check = await services.lean.check_file(
                        source, timeout_s=self.check_timeout_s
                    )
                    self.stats.lean_checks += 1
                except Exception:
                    continue
                if not self._accepted(check):
                    continue
                circular, extra_checks = await definition_is_circular(
                    services,
                    preamble=preamble,
                    context_blocks=context_blocks,
                    definition_block=solved_block,
                    dependent_blocks=dependent_blocks or [],
                    timeout_s=min(45, self.check_timeout_s),
                )
                self.stats.lean_checks += extra_checks
                if circular:
                    self.stats.rejected_circular += 1
                    continue
                accepted.append(solved_block)
                self.stats.accepted += 1
                self.stats.repaired += 1
                if len(accepted) >= self.max_accepted:
                    break
        return accepted


@dataclass
class ProgramStats:
    theorem_attempts: int = 0
    theorem_solved: int = 0
    definition_states: int = 0
    final_checks: int = 0
    calls_q: int = 0
    calls_g: int = 0
    lean_checks: int = 0
    reports: list[dict[str, Any]] = field(default_factory=list)


class ProgramPortfolioAgent:
    """Coordinate definition portfolios and immutable BridgePortfolio theorem slots."""

    def __init__(
        self,
        *,
        definition_portfolio: DefinitionPortfolio | None = None,
        theorem_factory: Callable[[Callable[[], float]], Any] | None = None,
        time_left: Callable[[], float] | None = None,
        max_definition_states: int | None = None,
        theorem_passes: int | None = None,
        reserve_s: float = 90.0,
        progress_graph: VerifiedProgressGraph | None = None,
    ):
        self.definition_portfolio = definition_portfolio or DefinitionPortfolio()
        self.progress_graph = progress_graph or VerifiedProgressGraph()
        self.theorem_factory = theorem_factory or (
            lambda time_left: BridgePortfolioAgent(
                arm="BP-PROGRAM-GQ",
                time_left=time_left,
                min_time_s=60.0,
                progress_graph=self.progress_graph,
            )
        )
        self.external_time_left = time_left
        self.max_definition_states = (
            max_definition_states
            if max_definition_states is not None
            else env_int("BP_PROGRAM_MAX_DEF_STATES", 3, minimum=1, maximum=8)
        )
        self.theorem_passes = (
            theorem_passes
            if theorem_passes is not None
            else env_int("BP_PROGRAM_THEOREM_PASSES", 2, minimum=1, maximum=3)
        )
        self.reserve_s = reserve_s
        self.stats = ProgramStats()

    @staticmethod
    def _time_budget() -> float:
        raw = os.environ.get("VM_TIME_LIMIT_S", "").strip()
        try:
            return max(120.0, float(raw)) if raw else 7200.0
        except ValueError:
            return 7200.0

    @staticmethod
    def _extract_block(solution: str, name: str) -> str | None:
        _pre, blocks = split_declarations(solution)
        for block in blocks:
            info = declaration_info(block)
            if info is not None and info[1] == name:
                return block.rstrip()
        return None

    @staticmethod
    def _strict(check) -> bool:
        return bool(
            check
            and check.accepted
            and not getattr(check, "has_sorry", False)
            and not getattr(check, "timed_out", False)
        )

    def _metadata(self, accepted: bool, reason: str) -> dict[str, Any]:
        ds = self.definition_portfolio.stats
        return {
            "arm": "BP-PROGRAM-GQ",
            "protocol": "program_portfolio",
            "accepted_by_repl": accepted,
            "substantive_closure": accepted,
            "stop_reason": reason,
            "calls_q": self.stats.calls_q + ds.calls_q,
            "calls_g": self.stats.calls_g + ds.calls_g,
            "lean_checks": self.stats.lean_checks + ds.lean_checks,
            "definition_calls_q": ds.calls_q,
            "definition_calls_g": ds.calls_g,
            "definition_candidates": ds.proposed,
            "definition_candidates_accepted": ds.accepted,
            "definition_candidates_repaired": ds.repaired,
            "definition_candidates_rejected_circular": ds.rejected_circular,
            "definition_canonical_retry_calls": ds.canonical_retry_calls,
            "definition_states": self.stats.definition_states,
            "theorem_attempts": self.stats.theorem_attempts,
            "theorem_solved": self.stats.theorem_solved,
            "final_checks": self.stats.final_checks,
            "reports": self.stats.reports[-24:],
            "progress_graph": self.progress_graph.metadata(),
        }

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        started = time.monotonic()
        budget = self._time_budget()

        def time_left() -> float:
            if self.external_time_left is not None:
                return self.external_time_left()
            return budget - self.reserve_s - (time.monotonic() - started)

        self.stats = ProgramStats()
        self.definition_portfolio.stats = DefinitionStats()
        preamble, blocks = split_declarations(problem.challenge)
        open_indices = [i for i, block in enumerate(blocks) if _block_has_sorry(block)]
        if not open_indices:
            try:
                check = await services.lean.check_file(problem.challenge)
                self.stats.lean_checks += 1
            except Exception:
                check = None
            ok = self._strict(check) and strict_integrity_check(
                problem.challenge, problem.challenge
            )[0]
            return AgentResult(problem.challenge, self._metadata(ok, "already_complete"))

        definition_indices: list[int] = []
        theorem_indices: list[int] = []
        for index in open_indices:
            info = declaration_info(blocks[index])
            if info is None:
                return AgentResult(problem.challenge, self._metadata(False, "unknown_declaration"))
            (theorem_indices if info[0] in {"theorem", "lemma"} else definition_indices).append(index)

        # A state maps original declaration indexes to solved, immutable blocks. Carry
        # already-complete declarations from the start; open theorem slots are filled later.
        fixed = {i: block.rstrip() for i, block in enumerate(blocks) if not _block_has_sorry(block)}
        states: list[dict[int, str]] = [dict(fixed)]
        for index in definition_indices:
            next_states: list[dict[int, str]] = []
            for state in states:
                if time_left() < 30:
                    break
                context = [state[i] for i in sorted(state) if i < index]
                candidates = await self.definition_portfolio.solve(
                    problem,
                    services,
                    preamble=preamble,
                    context_blocks=context,
                    block=blocks[index],
                    time_left=time_left,
                    dependent_blocks=blocks[index + 1 :],
                )
                for candidate in candidates:
                    branch = dict(state)
                    branch[index] = candidate
                    next_states.append(branch)
                    if len(next_states) >= self.max_definition_states:
                        break
                if len(next_states) >= self.max_definition_states:
                    break
            states = next_states
            if not states:
                return AgentResult(
                    problem.challenge, self._metadata(False, "definition_portfolio_exhausted")
                )
        self.stats.definition_states = len(states)

        best_solved = 0
        for state_number, base_state in enumerate(states, 1):
            state = dict(base_state)
            pending = list(theorem_indices)
            state_report: dict[str, Any] = {
                "definition_state": state_number,
                "theorems": [],
            }
            for pass_number in range(1, self.theorem_passes + 1):
                if not pending or time_left() < 45:
                    break
                progress = False
                next_pending: list[int] = []
                for index in pending:
                    info = declaration_info(blocks[index])
                    if info is None or time_left() < 45:
                        next_pending.append(index)
                        continue
                    _kind, name = info
                    context = [state[i] for i in sorted(state) if i != index]
                    mini = _program_source(preamble, context + [blocks[index]])
                    mini_problem = Problem(
                        id=f"{problem.id}::{name}",
                        description=(
                            f"{problem.description}\n\n"
                            f"[Program focus] Prove exactly `{name}`. Earlier solved "
                            "definitions and any verified sibling theorems are included "
                            "above it and may be reused."
                        ),
                        challenge=mini,
                        metadata=dict(problem.metadata),
                    )
                    # Internal theorem checkpoints are not complete program solutions.
                    inner_services = Services(
                        llm=services.llm, lean=services.lean, checkpoint=lambda *_a, **_k: None
                    )
                    agent = self.theorem_factory(time_left)
                    self.stats.theorem_attempts += 1
                    try:
                        result = await agent.solve(mini_problem, inner_services)
                    except Exception:
                        result = None
                    solved = bool(
                        result is not None
                        and result.metadata.get("accepted_by_repl")
                        and integrity_check(result.solution, mini)[0]
                    )
                    if result is not None:
                        self.stats.calls_q += int(result.metadata.get("calls_q", 0) or 0)
                        self.stats.calls_g += int(result.metadata.get("calls_g", 0) or 0)
                        self.stats.lean_checks += int(result.metadata.get("lean_checks", 0) or 0)
                    solved_block = self._extract_block(result.solution, name) if solved else None
                    search_keys = (
                        "stop_reason",
                        "portfolio_calls",
                        "routes_proposed",
                        "routes_rejected_illtyped",
                        "routes_rejected_rebinding",
                        "routes_rejected_restatement",
                        "bridges_checked",
                        "bridges_verified",
                        "routes_tried",
                        "lemmas_attempted",
                        "lemmas_harvested",
                        "recursive_calls",
                        "max_depth_seen",
                        "waves_started",
                        "retry_waves",
                        "critic_calls",
                        "critic_assessments",
                        "reports",
                    )
                    search = (
                        {
                            key: result.metadata[key]
                            for key in search_keys
                            if key in result.metadata
                        }
                        if result is not None
                        else {}
                    )
                    state_report["theorems"].append({
                        "name": name,
                        "pass": pass_number,
                        "status": "solved" if solved_block is not None else "miss",
                        "search": search,
                    })
                    if solved_block is not None:
                        state[index] = solved_block
                        self.stats.theorem_solved += 1
                        progress = True
                    else:
                        next_pending.append(index)
                pending = next_pending
                # A second pass is useful only when a newly solved sibling changed context.
                if not progress:
                    break
            self.stats.reports.append(state_report)
            best_solved = max(best_solved, len(theorem_indices) - len(pending))
            if pending:
                continue

            final_blocks = [state.get(i, blocks[i].rstrip()) for i in range(len(blocks))]
            final = _program_source(preamble, final_blocks)
            try:
                check = await services.lean.check_file(final, timeout_s=180)
                self.stats.lean_checks += 1
                self.stats.final_checks += 1
            except Exception:
                check = None
            if self._strict(check) and strict_integrity_check(final, problem.challenge)[0]:
                metadata = self._metadata(True, "program_solved")
                services.checkpoint(final, metadata)
                return AgentResult(final, metadata)

        self.stats.reports.append({
            "summary": "exhausted",
            "theorems_solved_in_best_state": best_solved,
            "theorems_total": len(theorem_indices),
        })
        return AgentResult(problem.challenge, self._metadata(False, "program_exhausted"))


def create_agent() -> ProgramPortfolioAgent:
    return ProgramPortfolioAgent()
