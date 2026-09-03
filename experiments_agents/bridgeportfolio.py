"""BridgePortfolio: bridge-first, recursively decomposed theorem proving.

The expensive failure mode in whole-file sampling is committing to a proof plan before
we know whether its intermediate facts are sufficient.  This agent reverses that order:

1. GPT-OSS proposes a *portfolio* of routes.  Each route is only a short list of Lean
   proposition statements, ordered by dependency.
2. For every route, GPT-OSS must prove the original goal with those propositions added as
   immutable hypotheses.  This "bridge" is checked by Lean without ``sorry``.  Routes
   whose milestones do not actually imply the goal are discarded before we try to prove
   any milestone.
3. Qwen independently reviews the GPT-OSS routes which survived Lean, rejecting
   circular, impossible, or non-simplifying decompositions.
4. Milestones are proved in order.  Qwen gets the cheap attempts and GPT-OSS gets the
   deeper repairs.  Model output is restricted to a proof body which is grafted under an
   exact, machine-owned theorem header, so a repair cannot alter the statement.
5. If the first blocked milestone remains unsolved, the same bridge-first procedure is
   applied recursively to that milestone (bounded depth).  Verified proof bodies are
   memoized by their exact generated challenge.
6. If every route in a wave fails, Qwen classifies the Lean-grounded frontier as near
   or far and recommends deeper subdivision or a fresh partition.  This is advisory:
   it cannot invalidate certificates or override bridge verification.
7. A second portfolio wave receives that assessment, the structured failure ledger,
   and every newly verified certificate, then proposes fresh routes.

Only a strictly accepted, integrity-preserving proof of the original challenge is ever
checkpointed or returned as solved.  Internal bridge probes contain neither ``sorry`` nor
new axioms.  The implementation is problem-agnostic and only calls the two permitted
models through the supplied harness services.
"""

from __future__ import annotations

import asyncio
import json
import re
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from re_harness import AgentResult, Problem, Services

from .common import (
    CLOSING_TACTICS,
    GPT_OSS,
    QWEN,
    count_model_calls,
    env_float,
    env_int,
    format_messages,
    integrity_check,
)
from .verified_progress import (
    RouteState,
    VerifiedLemmaNode,
    VerifiedProgressGraph,
    normalize_statement,
)


_PROOF_START = re.compile(r":=\s*by\b")
_DECL_START = re.compile(r"(?:^|\n)\s*(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_.']*)\b")
_FENCE = re.compile(r"```(?:lean|lean4)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_LEMMA_NAME = re.compile(r"bp_[1-9][0-9]*\Z")
_LEMMA_REF = re.compile(r"\bbp_[1-9][0-9]*\b")
_FORBIDDEN_PROOF = re.compile(
    r"\b(?:sorry|admit|axiom|native_decide)\b|(?:^|\n)\s*(?:theorem|lemma)\s+",
    re.IGNORECASE,
)
_FORBIDDEN_STATEMENT = re.compile(
    r"\b(?:sorry|admit|axiom|native_decide|theorem|lemma)\b|:=|\bby\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GoalShape:
    """A single theorem split at its top-level result colon."""

    before_result: str
    goal: str
    theorem_name: str


@dataclass(frozen=True)
class RouteLemma:
    name: str
    statement: str
    purpose: str = ""
    proof_hint: str = ""


@dataclass
class BridgeRoute:
    route_id: str
    summary: str
    lemmas: list[RouteLemma]
    bridge_body: str = ""
    review_score: int = 0
    review_reason: str = ""


@dataclass
class ProofAttempt:
    body: str | None = None
    diagnostics: str = ""


@dataclass
class SearchStats:
    calls_q: int = 0
    calls_g: int = 0
    lean_checks: int = 0
    portfolio_calls: int = 0
    routes_proposed: int = 0
    bridges_checked: int = 0
    bridges_verified: int = 0
    root_direct: int = 0
    routes_rejected_illtyped: int = 0
    routes_rejected_rebinding: int = 0
    routes_rejected_restatement: int = 0
    routes_tried: int = 0
    lemmas_attempted: int = 0
    lemmas_direct: int = 0
    recursive_calls: int = 0
    max_depth_seen: int = 0
    bank_revalidations: int = 0
    bank_compatible: int = 0
    bank_closures: int = 0
    bank_path_tries: int = 0
    bank_path_hits: int = 0
    lemmas_harvested: int = 0
    waves_started: int = 0
    retry_waves: int = 0
    critic_calls: int = 0
    critic_assessments: list[dict[str, Any]] = field(default_factory=list)
    reports: list[dict[str, Any]] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "calls_q": self.calls_q,
            "calls_g": self.calls_g,
            "lean_checks": self.lean_checks,
            "portfolio_calls": self.portfolio_calls,
            "routes_proposed": self.routes_proposed,
            "bridges_checked": self.bridges_checked,
            "bridges_verified": self.bridges_verified,
            "root_direct": self.root_direct,
            "routes_rejected_illtyped": self.routes_rejected_illtyped,
            "routes_rejected_rebinding": self.routes_rejected_rebinding,
            "routes_rejected_restatement": self.routes_rejected_restatement,
            "routes_tried": self.routes_tried,
            "lemmas_attempted": self.lemmas_attempted,
            "lemmas_direct": self.lemmas_direct,
            "recursive_calls": self.recursive_calls,
            "max_depth_seen": self.max_depth_seen,
            "bank_revalidations": self.bank_revalidations,
            "bank_compatible": self.bank_compatible,
            "bank_closures": self.bank_closures,
            "bank_path_tries": self.bank_path_tries,
            "bank_path_hits": self.bank_path_hits,
            "lemmas_harvested": self.lemmas_harvested,
            "waves_started": self.waves_started,
            "retry_waves": self.retry_waves,
            "critic_calls": self.critic_calls,
            "critic_assessments": self.critic_assessments,
            "reports": self.reports[-24:],
        }


def _normal(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _find_result_colon(source: str, start: int, end: int) -> int | None:
    """Find the final top-level ``:`` in a theorem header.

    Binder type colons occur inside ``()``, ``{}``, or ``[]``.  The theorem's result
    colon is at depth zero.  A small Lean-aware scanner is enough for the challenge
    format and avoids trusting a model to rewrite the target statement.
    """

    paren = bracket = brace = 0
    block_comment = 0
    line_comment = False
    in_string = False
    escaped = False
    result: int | None = None
    i = start
    while i < end:
        pair = source[i : i + 2]
        char = source[i]
        if line_comment:
            if char == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if pair == "/-":
                block_comment += 1
                i += 2
            elif pair == "-/":
                block_comment -= 1
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            i += 1
            continue
        if pair == "--":
            line_comment = True
            i += 2
            continue
        if pair == "/-":
            block_comment = 1
            i += 2
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            paren += 1
        elif char == ")":
            paren = max(0, paren - 1)
        elif char == "[":
            bracket += 1
        elif char == "]":
            bracket = max(0, bracket - 1)
        elif char == "{":
            brace += 1
        elif char == "}":
            brace = max(0, brace - 1)
        elif char == ":" and not (paren or bracket or brace):
            result = i
        i += 1
    return result


def goal_shape(challenge: str) -> GoalShape | None:
    """Parse the final open theorem in a challenge.

    A coordinated multi-declaration run may place already-solved definitions or
    sibling theorems before the current locked theorem.  The current obligation is
    therefore the *last* top-level theorem whose header ends in ``:= by``.  Local
    ``have ... := by`` blocks in the solved prefix cannot be selected because the
    declaration scan below still chooses the last top-level theorem/lemma preceding
    that proof marker.
    """

    proof_starts = list(_PROOF_START.finditer(challenge or ""))
    if not proof_starts:
        return None
    proof = proof_starts[-1]
    declarations = [m for m in _DECL_START.finditer(challenge, 0, proof.start())]
    if not declarations:
        return None
    declaration = declarations[-1]
    colon = _find_result_colon(challenge, declaration.start(), proof.start())
    if colon is None:
        return None
    goal = challenge[colon + 1 : proof.start()].strip()
    if not goal:
        return None
    return GoalShape(
        before_result=challenge[:colon].rstrip(),
        goal=goal,
        theorem_name=declaration.group(1),
    )


def locked_parameter_names(challenge: str) -> set[str]:
    """Extract simple binder names already owned by the locked theorem header."""

    shape = goal_shape(challenge)
    if shape is None:
        return set()
    declarations = list(_DECL_START.finditer(shape.before_result))
    if not declarations:
        return set()
    header = shape.before_result[declarations[-1].end() :]
    names: set[str] = set()
    for match in re.finditer(r"[({\[]\s*([^:(){}\[\]]+?)\s*:", header):
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", match.group(1)):
            if token != "_":
                names.add(token)
    return names


def statement_rebinds_locked_parameter(statement: str, locked: set[str]) -> bool:
    """Reject planner milestones which shadow parameters already in local scope."""

    if not locked:
        return False
    match = re.match(r"^\s*(?:∀|forall)\s+(.+?),", statement, re.DOTALL)
    if match is None:
        return False
    quantified_prefix = set(
        re.findall(r"[A-Za-z_][A-Za-z0-9_']*", match.group(1))
    )
    return bool(locked & quantified_prefix)


def build_goal_source(
    challenge: str,
    *,
    extra_hypotheses: list[tuple[str, str]] | None = None,
    goal_override: str | None = None,
    proof_body: str | None = None,
) -> str | None:
    """Build a machine-owned theorem with optional hypotheses and a locked goal.

    ``proof_body=None`` produces an intentionally open task with a comment, not a
    ``sorry``.  Every source sent to Lean has a concrete proof body.
    """

    shape = goal_shape(challenge)
    if shape is None:
        return None
    head = shape.before_result
    declarations = list(_DECL_START.finditer(head))
    if not declarations:
        return None
    match = declarations[-1]
    # Insert set_option immediately before the theorem/lemma keyword (not before
    # the leading newline captured by _DECL_START), so the source stays readable.
    m_kw = re.search(
        r"(theorem|lemma)\s+" + re.escape(match.group(1)),
        head[max(0, match.start()) :],
    )
    if m_kw is None:
        decl_kw_at = match.start()
    else:
        decl_kw_at = max(0, match.start()) + m_kw.start()
    prefix = head[:decl_kw_at].rstrip("\n") + "\n"
    head = prefix + "set_option autoImplicit false in\n" + head[decl_kw_at:].lstrip("\n")
    for name, statement in extra_hypotheses or []:
        head += f"\n  ({name} : {statement})"
    goal = (goal_override or shape.goal).strip()
    source = f"{head} :\n  {goal} := by\n"
    if proof_body is None:
        return source + "  -- proof required\n"
    body = textwrap.dedent(proof_body).strip("\n")
    if not body:
        return source + "  fail_if_success done\n"
    return source + "\n".join("  " + line if line.strip() else line for line in body.splitlines()) + "\n"


def _extract_json(text: str) -> dict[str, Any] | None:
    candidates = re.findall(r"```(?:json)?\s*\n(.*?)```", text or "", re.DOTALL)
    candidates.append(text or "")
    for candidate in candidates:
        left, right = candidate.find("{"), candidate.rfind("}")
        if left < 0 or right <= left:
            continue
        try:
            value = json.loads(candidate[left : right + 1])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return None


def parse_routes(text: str, *, goal: str, max_routes: int, max_lemmas: int) -> list[BridgeRoute]:
    """Parse, sanitize, de-duplicate, and structurally filter a route portfolio."""

    payload = _extract_json(text)
    raw_routes = payload.get("routes", []) if payload else []
    if not isinstance(raw_routes, list):
        return []
    routes: list[BridgeRoute] = []
    seen_signatures: set[tuple[str, ...]] = set()
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_routes):
        if not isinstance(raw, dict):
            continue
        route_id = str(raw.get("id", f"route_{index + 1}")).strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", route_id):
            route_id = f"route_{index + 1}"
        if route_id in seen_ids:
            route_id = f"{route_id}_{index + 1}"
        raw_lemmas = raw.get("lemmas", [])
        if not isinstance(raw_lemmas, list) or not 1 <= len(raw_lemmas) <= max_lemmas:
            continue
        lemmas: list[RouteLemma] = []
        valid = True
        previous_names: set[str] = set()
        for lemma_index, item in enumerate(raw_lemmas, 1):
            if not isinstance(item, dict):
                valid = False
                break
            name = str(item.get("name", "")).strip()
            statement = str(item.get("statement", "")).strip()
            if name != f"bp_{lemma_index}" or not _LEMMA_NAME.fullmatch(name):
                valid = False
                break
            if not 3 <= len(statement) <= 1800 or _FORBIDDEN_STATEMENT.search(statement):
                valid = False
                break
            normalized = _normal(statement)
            if normalized in {"false", "true", _normal(goal)}:
                valid = False
                break
            references = set(_LEMMA_REF.findall(statement))
            if not references.issubset(previous_names):
                valid = False
                break
            lemmas.append(RouteLemma(
                name=name,
                statement=statement,
                purpose=str(item.get("purpose", "")).strip()[:800],
                proof_hint=str(item.get("proof_hint", "")).strip()[:1200],
            ))
            previous_names.add(name)
        if not valid:
            continue
        signature = tuple(_normal(lemma.statement) for lemma in lemmas)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        seen_ids.add(route_id)
        routes.append(BridgeRoute(
            route_id=route_id,
            summary=str(raw.get("summary", "")).strip()[:1000],
            lemmas=lemmas,
        ))
        if len(routes) >= max_routes:
            break
    return routes


def extract_proof_body(text: str) -> str | None:
    """Extract a tactic body while refusing proof escapes and top-level declarations."""

    blocks = _FENCE.findall(text or "")
    body = (blocks[-1] if blocks else (text or "")).strip()
    if not body:
        return None
    # Be tolerant when a model ignores "body only" and returns one complete theorem.
    if re.match(r"\s*(?:import\b|open\b|namespace\b|theorem\b|lemma\b)", body):
        marker = _PROOF_START.search(body)
        if marker is None:
            return None
        # Preserve the common indentation until `dedent` below. Stripping here would
        # unindent only the first tactic and leave its siblings nested underneath it.
        body = body[marker.end() :]
    by_prefix = re.match(r"^\s*by[ \t]*(?:\r?\n)", body)
    if by_prefix is not None:
        # Models occasionally return `by` despite the body-only contract. Remove just
        # that wrapper; do not strip the first line before normalizing the whole block.
        body = body[by_prefix.end() :]
    if not body or len(body) > 30_000 or _FORBIDDEN_PROOF.search(body):
        return None
    return textwrap.dedent(body).strip()


def bridge_used_lemmas(route: BridgeRoute, body: str) -> set[str]:
    """Milestones explicitly consumed by a bridge body.

    A bridge commonly uses only the final milestones. Earlier milestones remain useful:
    they are premises available while proving those final milestones. Requiring every
    name in the final bridge therefore rejects a valid dependency chain before Lean can
    inspect it. We require at least one consumed milestone and let the route reviewer
    penalize genuinely redundant portfolios.
    """

    return {
        lemma.name
        for lemma in route.lemmas
        if re.search(rf"\b{re.escape(lemma.name)}\b", body) is not None
    }


def failure_kind(diagnostics: str) -> str:
    """Return a deterministic coarse signal for the next-wave critic."""

    text = diagnostics.lower()
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if any(
        token in text
        for token in ("unexpected token", "expected command", "unknown identifier")
    ):
        return "elaboration"
    if "unsolved goals" in text or "failed to find a contradiction" in text:
        return "local_goal"
    return "other" if text.strip() else "no_candidate"


def closing_battery_body(tactics: tuple[str, ...] = CLOSING_TACTICS[:7]) -> str:
    """Run deterministic closers in one Lean request, accepting only closed branches."""

    branches = "\n".join(f"  | ({tactic} <;> done)" for tactic in tactics)
    return f"first\n{branches}"


def restatement_probe_body(route: BridgeRoute) -> str:
    """Detect exact and binder-generalized target restatements in one Lean request."""

    branches: list[str] = []
    for lemma in route.lemmas:
        branches.append(f"  | exact {lemma.name}")
        # `apply bp <;> done` catches a milestone such as `∀ a b, P a b` when
        # the locked theorem has parameters `a b` and its current goal is `P a b`.
        # `done` makes the branch fail if applying the milestone leaves premises.
        branches.append(f"  | (apply {lemma.name} <;> done)")
        # A generalized restatement may leave premises which are already present in the
        # locked local context (for example its positivity hypothesis).  Let Lean use
        # those facts as well; a genuine weaker milestone cannot close the target.
        branches.append(f"  | (solve_by_elim [{lemma.name}] <;> done)")
    return "first\n" + "\n".join(branches)


class BridgePortfolioAgent:
    """Bridge-first portfolio search with bounded recursive lemma decomposition."""

    def __init__(
        self,
        *,
        arm: str = "BP-GQ",
        time_left: Callable[[], float] | None = None,
        max_depth: int | None = None,
        portfolio_calls: int | None = None,
        routes_per_call: int | None = None,
        max_routes_checked: int | None = None,
        max_routes_tried: int | None = None,
        max_lemmas: int | None = None,
        q_attempts: int | None = None,
        g_attempts: int | None = None,
        check_timeout_s: int | None = None,
        min_time_s: float | None = None,
        search_waves: int | None = None,
        progress_graph: VerifiedProgressGraph | None = None,
        lab_notebook: str = "",
    ):
        self.arm = arm
        self.time_left = time_left or (lambda: float("inf"))
        self.max_depth = max_depth if max_depth is not None else env_int(
            "BP_MAX_DEPTH", 2, minimum=0, maximum=3
        )
        self.portfolio_calls = portfolio_calls if portfolio_calls is not None else env_int(
            "BP_PORTFOLIO_CALLS", 2, minimum=1, maximum=4
        )
        self.routes_per_call = routes_per_call if routes_per_call is not None else env_int(
            "BP_ROUTES_PER_CALL", 4, minimum=2, maximum=8
        )
        self.max_routes_checked = max_routes_checked if max_routes_checked is not None else env_int(
            "BP_MAX_ROUTES_CHECKED", 8, minimum=1, maximum=16
        )
        self.max_routes_tried = max_routes_tried if max_routes_tried is not None else env_int(
            "BP_MAX_ROUTES_TRIED", 3, minimum=1, maximum=8
        )
        self.max_lemmas = max_lemmas if max_lemmas is not None else env_int(
            "BP_MAX_LEMMAS", 5, minimum=1, maximum=8
        )
        self.q_attempts = q_attempts if q_attempts is not None else env_int(
            "BP_Q_ATTEMPTS", 3, minimum=0, maximum=8
        )
        self.g_attempts = g_attempts if g_attempts is not None else env_int(
            "BP_G_ATTEMPTS", 4, minimum=0, maximum=8
        )
        self.check_timeout_s = check_timeout_s if check_timeout_s is not None else env_int(
            "BP_CHECK_TIMEOUT_S", 90, minimum=10, maximum=240
        )
        self.min_time_s = min_time_s if min_time_s is not None else env_float(
            "BP_MIN_TIME_S", 240.0, minimum=30.0, maximum=1800.0
        )
        self.search_waves = search_waves if search_waves is not None else env_int(
            "BP_SEARCH_WAVES", 2, minimum=1, maximum=3
        )
        self.stats = SearchStats()
        self._memo: dict[str, str] = {}
        self.progress_graph = progress_graph or VerifiedProgressGraph()
        # English residual lab notebook ("Avoid repeating: …"); empty outside residual.
        self.lab_notebook = (lab_notebook or "").strip()

    def _has_time(self, reserve: float | None = None) -> bool:
        return self.time_left() > (self.min_time_s if reserve is None else reserve)

    async def _complete(self, services: Services, *, model: str, **kwargs):
        response = await services.llm.complete(model=model, **kwargs)
        self.stats.calls_q, self.stats.calls_g = count_model_calls(
            model, self.stats.calls_q, self.stats.calls_g
        )
        return response

    async def _check(self, services: Services, source: str, *, timeout_s: int | None = None):
        check = await services.lean.check_file(
            source, timeout_s=timeout_s or self.check_timeout_s
        )
        self.stats.lean_checks += 1
        return check

    @staticmethod
    def _strictly_accepted(check) -> bool:
        return bool(
            check
            and check.accepted
            and not getattr(check, "has_sorry", False)
            and not getattr(check, "timed_out", False)
        )

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        self.stats = SearchStats()
        self._memo = {}
        if goal_shape(problem.challenge) is None:
            return self._result(problem.challenge, False, "unsupported_goal_shape")
        # Keep the standalone component honest on easy goals. In the integrated agent
        # this duplicates the preceding cheap sweep by only one Lean request, while a
        # direct BridgePortfolio experiment no longer decomposes a one-line theorem.
        body = await self._try_closing_battery(problem, services)
        if body is not None:
            self.stats.root_direct += 1
        else:
            body = await self._decompose_goal(
                problem, services, depth=0, failure_context="", breadcrumb="root"
            )
        if body is None:
            return self._result(problem.challenge, False, "portfolio_exhausted")
        final = build_goal_source(problem.challenge, proof_body=body)
        if final is None:
            return self._result(problem.challenge, False, "assembly_failed")
        try:
            check = await self._check(services, final, timeout_s=max(120, self.check_timeout_s))
        except Exception:
            return self._result(problem.challenge, False, "final_check_error")
        ok = self._strictly_accepted(check) and integrity_check(final, problem.challenge)[0]
        if ok:
            shape = goal_shape(problem.challenge)
            self.progress_graph.record_route(
                route_id=f"{self.arm}:final",
                state=RouteState.COMPLETE,
                goal=shape.goal if shape is not None else "",
                bridge_verified=True,
                provenance={"problem": problem.id, "stage": "strict_final"},
            )
            services.checkpoint(final, {
                "arm": self.arm,
                "protocol": "bridge_portfolio",
                "stage": "strict_final",
                "stats": self.stats.metadata(),
            })
            return self._result(final, True, "solved")
        return self._result(problem.challenge, False, "strict_final_failed")

    async def _decompose_goal(
        self,
        problem: Problem,
        services: Services,
        *,
        depth: int,
        failure_context: str,
        breadcrumb: str,
        wave: int = 0,
    ) -> str | None:
        if not self._has_time():
            return None
        self.stats.max_depth_seen = max(self.stats.max_depth_seen, depth)
        shape = goal_shape(problem.challenge)
        if shape is None:
            return None
        self.stats.waves_started += 1

        # Revalidate saved certificates in the *current* theorem context before they
        # become hypotheses. A node from a failed route or sibling theorem is executable
        # Lean code, but never trusted across contexts without this replay.
        bank = await self._compatible_bank(problem, services)
        bank_closed = await self._try_bank_closure(problem, services, bank)
        if bank_closed is not None:
            self.stats.bank_closures += 1
            return bank_closed
        # Phase B: try small combinations of bank facts as alternate "paths"
        # before spending a fresh portfolio wave.
        path_closed = await self._try_bank_path_combinations(problem, services, bank)
        if path_closed is not None:
            self.stats.bank_path_hits += 1
            return path_closed

        routes = await self._make_portfolio(
            problem,
            services,
            depth=depth,
            wave=wave,
            failure_context=failure_context,
            bank=bank,
        )
        if not routes:
            return await self._retry_wave(
                problem, services, depth, wave, failure_context, breadcrumb, "no routes parsed"
            )
        routes = await self._filter_route_statements(problem, services, routes, bank=bank)
        if not routes:
            return await self._retry_wave(
                problem,
                services,
                depth,
                wave,
                failure_context,
                breadcrumb,
                "all proposed routes were ill-typed or restated the target",
            )
        verified = await self._verify_bridges(
            problem, services, routes, depth=depth, bank=bank
        )
        if not verified:
            for route in routes:
                self.progress_graph.record_route(
                    route_id=route.route_id,
                    state=RouteState.INVALID,
                    goal=shape.goal,
                    bridge_verified=False,
                    provenance={
                        "problem": problem.id,
                        "depth": depth,
                        "wave": wave,
                        "breadcrumb": breadcrumb,
                    },
                )
            return await self._retry_wave(
                problem,
                services,
                depth,
                wave,
                failure_context,
                breadcrumb,
                "no proposed route produced a Lean-verified bridge",
            )
        ranked = await self._rank_routes(problem, services, verified, depth=depth)
        for route in ranked[: self.max_routes_tried]:
            if not self._has_time():
                break
            # A previous route in this same portfolio may have failed after proving useful
            # prefixes. Recompute compatibility so the next route can consume them.
            route_bank = await self._compatible_bank(problem, services)
            self.stats.routes_tried += 1
            report: dict[str, Any] = {
                "goal": breadcrumb,
                "depth": depth,
                "wave": wave,
                "route": route.route_id,
                "score": route.review_score,
                "review_reason": route.review_reason,
                "bank": [node.node_id for node in route_bank],
                "lemmas": [],
            }
            solved: list[tuple[RouteLemma, str, str | None]] = []
            route_failed = False
            for lemma in route.lemmas:
                if not self._has_time():
                    route_failed = True
                    break
                self.stats.lemmas_attempted += 1
                prior = [(node.alias, node.statement) for node in route_bank]
                prior.extend((item.name, item.statement) for item, _body, _node in solved)
                lemma_challenge = build_goal_source(
                    problem.challenge,
                    extra_hypotheses=prior,
                    goal_override=lemma.statement,
                    proof_body=None,
                )
                if lemma_challenge is None:
                    route_failed = True
                    break
                memo_key = _normal(lemma_challenge)
                proof = self._memo.get(memo_key)
                attempt = ProofAttempt(body=proof)
                # Prefer an already-certified bank fact with the same statement.
                if proof is None:
                    bank_hit = next(
                        (
                            node
                            for node in route_bank
                            if normalize_statement(node.statement)
                            == normalize_statement(lemma.statement)
                        ),
                        None,
                    )
                    if bank_hit is not None:
                        attempt = ProofAttempt(body=bank_hit.certificate or bank_hit.proof)
                        self.progress_graph.mark_reused(
                            [bank_hit.node_id], decisive=False
                        )
                if attempt.body is None:
                    attempt = await self._prove_locked_goal(
                        Problem(
                            id=f"{problem.id}::{breadcrumb}::{route.route_id}::{lemma.name}",
                            description=(
                                f"{problem.description}\n\n"
                                f"Current milestone: {lemma.purpose}\n"
                                f"Proof hint from the route planner: {lemma.proof_hint}"
                            ),
                            challenge=lemma_challenge,
                            metadata=dict(problem.metadata),
                        ),
                        services,
                    )
                if attempt.body is None and depth < self.max_depth:
                    self.stats.recursive_calls += 1
                    recursive_problem = Problem(
                        id=f"{problem.id}::{breadcrumb}::{lemma.name}",
                        description=(
                            f"{problem.description}\n\n"
                            f"This is a blocked intermediate milestone. Its role is: "
                            f"{lemma.purpose}. Suggested mathematics: {lemma.proof_hint}"
                        ),
                        challenge=lemma_challenge,
                        metadata=dict(problem.metadata),
                    )
                    attempt.body = await self._decompose_goal(
                        recursive_problem,
                        services,
                        depth=depth + 1,
                        failure_context=attempt.diagnostics,
                        breadcrumb=f"{breadcrumb}/{route.route_id}/{lemma.name}",
                    )
                status = "proved" if attempt.body is not None else "blocked"
                report["lemmas"].append({
                    "name": lemma.name,
                    "status": status,
                    "diagnostics": attempt.diagnostics[:900] if attempt.body is None else "",
                    "failure_kind": (
                        failure_kind(attempt.diagnostics)
                        if attempt.body is None
                        else ""
                    ),
                })
                if attempt.body is None:
                    route_failed = True
                    break
                self._memo[memo_key] = attempt.body
                # Bank facts were available as hypotheses while proving this lemma.
                # Count non-decisive reuse even if the model never spells the alias.
                if route_bank:
                    self.progress_graph.mark_reused(
                        [node.node_id for node in route_bank], decisive=False
                    )
                certificate = self._certificate_body(route_bank, solved, attempt.body)
                certificate_source = build_goal_source(
                    problem.challenge,
                    goal_override=lemma.statement,
                    proof_body=certificate,
                )
                node_id: str | None = None
                if certificate_source is not None:
                    try:
                        certificate_check = await self._check(services, certificate_source)
                    except Exception:
                        certificate_check = None
                    accepted_certificate = self._strictly_accepted(certificate_check)
                    node = self.progress_graph.add_verified(
                        statement=lemma.statement,
                        proof=attempt.body,
                        certificate=certificate,
                        context=problem.challenge,
                        dependencies=[
                            *[node.node_id for node in route_bank],
                            *[saved for _item, _proof, saved in solved if saved is not None],
                        ],
                        provenance={
                            "problem": problem.id,
                            "route": route.route_id,
                            "lemma": lemma.name,
                            "depth": depth,
                            "breadcrumb": breadcrumb,
                        },
                        original_goal=shape.goal,
                        lean_accepted=accepted_certificate,
                    )
                    if node is not None:
                        node_id = node.node_id
                        self.stats.lemmas_harvested += 1
                        report["lemmas"][-1]["node_id"] = node_id
                solved.append((lemma, attempt.body, node_id))
            self.stats.reports.append(report)
            if route_failed:
                self.progress_graph.record_route(
                    route_id=route.route_id,
                    state=RouteState.SUFFICIENT_INCOMPLETE,
                    goal=shape.goal,
                    bridge_verified=True,
                    proved_nodes=[node for _lemma, _body, node in solved if node is not None],
                    provenance={
                        "problem": problem.id,
                        "depth": depth,
                        "wave": wave,
                        "breadcrumb": breadcrumb,
                    },
                )
                continue
            assembled = self._assemble_route(
                problem.challenge,
                route_bank,
                [(lemma, body) for lemma, body, _node in solved],
                route.bridge_body,
            )
            if assembled is None:
                continue
            try:
                check = await self._check(services, assembled)
            except Exception:
                continue
            if self._strictly_accepted(check):
                # Bank certificates are always material in `_certificate_body` (`have vp_…`).
                # Old code only counted reuse when the alias appeared in free-form bridge text,
                # which left decisive_reuses=0 even when the bank closed the goal.
                if route_bank:
                    self.progress_graph.mark_reused(
                        [node.node_id for node in route_bank], decisive=True
                    )
                self.progress_graph.record_route(
                    route_id=route.route_id,
                    state=RouteState.COMPLETE,
                    goal=shape.goal,
                    bridge_verified=True,
                    proved_nodes=[node for _lemma, _body, node in solved if node is not None],
                    provenance={
                        "problem": problem.id,
                        "depth": depth,
                        "wave": wave,
                        "breadcrumb": breadcrumb,
                    },
                )
                # Return only the body.  The caller always rebuilds it under its own
                # exact statement, including at recursive levels.  Do not call
                # ``goal_shape`` here: a completed proof legitimately contains further
                # ``:= by`` tokens in local ``have`` declarations.
                marker = _PROOF_START.search(assembled)
                if marker is not None:
                    return textwrap.dedent(assembled[marker.end() :]).strip()
        return await self._retry_wave(
            problem,
            services,
            depth,
            wave,
            failure_context,
            breadcrumb,
            "all bridge-verified routes exhausted their milestone attempts",
        )

    async def _retry_wave(
        self,
        problem: Problem,
        services: Services,
        depth: int,
        wave: int,
        failure_context: str,
        breadcrumb: str,
        reason: str,
    ) -> str | None:
        """Start one fresh portfolio wave with a compact cross-route failure ledger."""

        if wave + 1 >= self.search_waves or not self._has_time():
            return None
        recent = [
            report
            for report in self.stats.reports[-self.max_routes_tried :]
            if report.get("goal") == breadcrumb and report.get("depth") == depth
        ]
        ledger = json.dumps(recent, ensure_ascii=False, separators=(",", ":"))
        critic = await self._assess_failed_frontier(
            problem,
            services,
            depth=depth,
            wave=wave,
            reason=reason,
            reports=recent,
        )
        next_context = (
            f"Previous portfolio wave {wave} failed: {reason}.\n"
            f"Cross-route failure ledger: {ledger[:3600]}"
        )
        if critic:
            next_context += (
                "\nIndependent Qwen frontier assessment (advisory; Lean certificates "
                f"remain authoritative): {json.dumps(critic, ensure_ascii=False)}"
            )
        if failure_context:
            next_context = failure_context[-1200:] + "\n\n" + next_context
        self.stats.retry_waves += 1
        return await self._decompose_goal(
            problem,
            services,
            depth=depth,
            wave=wave + 1,
            failure_context=next_context,
            breadcrumb=breadcrumb,
        )

    async def _assess_failed_frontier(
        self,
        problem: Problem,
        services: Services,
        *,
        depth: int,
        wave: int,
        reason: str,
        reports: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Ask Qwen whether to deepen or repartition, grounded in verified facts.

        This is deliberately one batched call per failed wave, rather than one call per
        lemma.  It cannot discard a Lean-valid certificate or declare a route sufficient;
        it only advises the next GPT-OSS portfolio wave.
        """

        if not reports or not self._has_time():
            return None
        compact = []
        for report in reports:
            compact.append({
                "route": report.get("route"),
                "bridge_verified": True,
                "review_score": report.get("score"),
                "lemmas": report.get("lemmas", []),
                "revalidated_bank": report.get("bank", []),
            })
        system = (
            "You are an independent Qwen critic of a failed verified theorem-search "
            "frontier proposed and attacked by GPT-OSS. Lean is authoritative: every "
            "reported proved lemma and bridge status is a hard fact. Classify the "
            "frontier as near only when the verified prefix and first compiler failure "
            "make further subdivision plausibly cheaper than restarting. Otherwise call "
            "it far. Never propose changing the locked target or discarding verified "
            "lemmas. Return only JSON: "
            '{"assessment":"near|far","reason":"...",'
            '"recommended_action":"deepen_blocked|repartition",'
            '"feedback_for_planner":"concise actionable feedback"}.'
        )
        user = (
            f"Depth: {depth}; portfolio wave: {wave}; terminal reason: {reason}.\n"
            f"Locked goal:\n{problem.challenge}\n\n"
            "Lean-grounded failed frontier:\n"
            f"{json.dumps(compact, ensure_ascii=False)}"
        )
        try:
            response = await self._complete(
                services,
                model=QWEN,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=6000,
                temperature=0.1,
            )
        except Exception:
            return None
        payload = _extract_json(response.content or "")
        if not payload:
            return None
        assessment = str(payload.get("assessment", "")).lower()
        action = str(payload.get("recommended_action", "")).lower()
        if assessment not in {"near", "far"}:
            return None
        if action not in {"deepen_blocked", "repartition"}:
            action = "deepen_blocked" if assessment == "near" else "repartition"
        result = {
            "depth": depth,
            "wave": wave,
            "assessment": assessment,
            "recommended_action": action,
            "reason": str(payload.get("reason", ""))[:700],
            "feedback_for_planner": str(payload.get("feedback_for_planner", ""))[:1200],
        }
        self.stats.critic_calls += 1
        self.stats.critic_assessments.append(result)
        return result

    async def _make_portfolio(
        self,
        problem: Problem,
        services: Services,
        *,
        depth: int,
        wave: int,
        failure_context: str,
        bank: list[VerifiedLemmaNode],
    ) -> list[BridgeRoute]:
        shape = goal_shape(problem.challenge)
        if shape is None:
            return []
        calls = self.portfolio_calls if depth == 0 else min(2, self.portfolio_calls)
        system = (
            "You are the strategic reasoner in a Lean theorem-proving system. Propose "
            "several genuinely different milestone decompositions, not full proofs. "
            "Each route must contain 1-5 Lean propositions which are meaningful, easier "
            "than the target, and collectively sufficient. Avoid restating the target, "
            "False, giant conjunctions that hide the target, cosmetic rewrites, and "
            "problem-specific tactic advice. Every milestone is inserted under the "
            "locked theorem's existing parameters: never re-quantify or shadow those "
            "parameters. Split coercions, denominator nonzeroness, algebraic rewriting, "
            "and finite classification into separate genuinely smaller milestones when "
            "needed; keep each statement in one ambient number type when possible. "
            "Lemmas are ordered: bp_2 may use bp_1, but "
            "never a future lemma. Use names bp_1, bp_2, ... exactly. Return only JSON: "
            '{"routes":[{"id":"route_1","summary":"mathematical route",'
            '"lemmas":[{"name":"bp_1","statement":"Lean proposition only",'
            '"purpose":"why the bridge needs it","proof_hint":"concise mathematics"}]}]}.'
        )
        context = ""
        if failure_context:
            context = (
                "\n\nDirect attempts on this exact goal failed. Use this compact Lean "
                f"feedback to choose a better decomposition:\n{failure_context[:2500]}"
            )
        notebook_context = ""
        if self.lab_notebook:
            notebook_context = f"\n\n{self.lab_notebook[:1500]}"
        bank_context = ""
        if bank:
            facts = "\n".join(f"- {node.alias} : {node.statement}" for node in bank)
            bank_context = (
                "\n\nThese facts have executable Lean certificates revalidated in "
                f"this exact context and may be combined with a new route:\n{facts}"
            )
        parameters = sorted(locked_parameter_names(problem.challenge))
        user = (
            f"Produce {self.routes_per_call} diverse routes. Recursion depth: {depth}. "
            f"Portfolio wave: {wave}.\n"
            f"Locked local parameters already in scope: {parameters or '(none)'}. "
            "Use them directly; do not add a leading forall for them.\n"
            f"Problem description:\n{problem.description}\n\n"
            f"Exact locked Lean goal file:\n```lean\n{problem.challenge}\n```"
            f"{bank_context}{context}{notebook_context}"
        )

        async def one(index: int):
            if not self._has_time():
                return None
            # Dual-model attack diversity: even slots GPT-OSS, odd slots Qwen.
            # Lean still filters bridges; the second model is not an opinion critic.
            model = GPT_OSS if index % 2 == 0 else QWEN
            try:
                response = await self._complete(
                    services,
                    model=model,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    max_tokens=7000,
                    temperature=0.55 + 0.2 * index + (0.1 if model == QWEN else 0.0),
                    seed=7919 + depth * 101 + wave * 1009 + index,
                )
                self.stats.portfolio_calls += 1
                return response.content or ""
            except Exception:
                return None

        texts = await asyncio.gather(*(one(i) for i in range(calls)))
        combined: list[BridgeRoute] = []
        signatures: set[tuple[str, ...]] = set()
        for text in texts:
            if not text:
                continue
            parsed = parse_routes(
                text,
                goal=shape.goal,
                max_routes=self.max_routes_checked,
                max_lemmas=self.max_lemmas,
            )
            for route in parsed:
                # Names emitted by the planner are deliberately simple.  Namespace them
                # by recursion depth before putting them into a real theorem context so
                # a child decomposition cannot collide with a parent route's hypotheses.
                namespace = f"bp_d{depth}" if wave == 0 else f"bp_d{depth}_w{wave}"
                rename = {
                    lemma.name: f"{namespace}_{i}"
                    for i, lemma in enumerate(route.lemmas, 1)
                }

                def renamed(text: str) -> str:
                    for old, new in rename.items():
                        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
                    return text

                route.lemmas = [
                    RouteLemma(
                        name=rename[lemma.name],
                        statement=renamed(lemma.statement),
                        purpose=renamed(lemma.purpose),
                        proof_hint=renamed(lemma.proof_hint),
                    )
                    for lemma in route.lemmas
                ]
                signature = tuple(_normal(lemma.statement) for lemma in route.lemmas)
                if signature in signatures:
                    continue
                signatures.add(signature)
                # IDs only need to be unique in this portfolio.
                route.route_id = (
                    f"d{depth}_w{wave}_{len(combined) + 1}_{route.route_id}"
                )[:48]
                combined.append(route)
                if len(combined) >= self.max_routes_checked:
                    break
            if len(combined) >= self.max_routes_checked:
                break
        self.stats.routes_proposed += len(combined)
        return combined

    async def _filter_route_statements(
        self,
        problem: Problem,
        services: Services,
        routes: list[BridgeRoute],
        *,
        bank: list[VerifiedLemmaNode],
    ) -> list[BridgeRoute]:
        """Reject ill-typed and circular routes before spending model calls on bridges."""

        accepted: list[BridgeRoute] = []
        locked = locked_parameter_names(problem.challenge)
        bank_keys = {normalize_statement(node.statement) for node in bank}
        shape = goal_shape(problem.challenge)
        goal_key = normalize_statement(shape.goal) if shape is not None else ""
        for route in routes:
            if not self._has_time():
                break
            if any(
                statement_rebinds_locked_parameter(lemma.statement, locked)
                for lemma in route.lemmas
            ):
                self.stats.routes_rejected_rebinding += 1
                continue
            # Cheap structural drop: empty/goal-restating/already-banked-only routes.
            lemma_keys = [normalize_statement(lemma.statement) for lemma in route.lemmas]
            if not any(lemma_keys) or all(not key for key in lemma_keys):
                self.stats.routes_rejected_illtyped += 1
                continue
            if goal_key and any(key == goal_key for key in lemma_keys):
                self.stats.routes_rejected_restatement += 1
                continue
            # If every milestone is already in the bank, skip re-planning; bank closure
            # / injection at the top of decompose should spend the certificates.
            if bank_keys and lemma_keys and all(key in bank_keys for key in lemma_keys):
                self.stats.routes_rejected_restatement += 1
                continue
            hypotheses = [(node.alias, node.statement) for node in bank]
            hypotheses.extend((lemma.name, lemma.statement) for lemma in route.lemmas)

            # A trivial target proves nothing about the milestones, but Lean must still
            # parse and elaborate every binder in order. This catches bad notation,
            # unknown/free names, and malformed dependency chains without `sorry`.
            type_probe = build_goal_source(
                problem.challenge,
                extra_hypotheses=hypotheses,
                goal_override="True",
                proof_body="trivial",
            )
            if type_probe is None:
                self.stats.routes_rejected_illtyped += 1
                continue
            try:
                type_check = await self._check(
                    services, type_probe, timeout_s=min(35, self.check_timeout_s)
                )
            except Exception:
                self.stats.routes_rejected_illtyped += 1
                continue
            if not self._strictly_accepted(type_check):
                self.stats.routes_rejected_illtyped += 1
                continue

            if await self._route_restates_target(problem, services, route, bank=bank):
                self.stats.routes_rejected_restatement += 1
                continue
            accepted.append(route)
        return accepted

    async def _verify_bridges(
        self,
        problem: Problem,
        services: Services,
        routes: list[BridgeRoute],
        *,
        depth: int,
        bank: list[VerifiedLemmaNode],
    ) -> list[BridgeRoute]:
        async def propose(route: BridgeRoute):
            hypotheses = [(node.alias, node.statement) for node in bank]
            hypotheses.extend((lemma.name, lemma.statement) for lemma in route.lemmas)
            bridge_task = build_goal_source(
                problem.challenge, extra_hypotheses=hypotheses, proof_body=None
            )
            if bridge_task is None or not self._has_time():
                return route, bridge_task, None
            lemma_notes = "\n".join(
                f"- {lemma.name}: {lemma.statement}\n  Purpose: {lemma.purpose}"
                for lemma in route.lemmas
            )
            bank_notes = "\n".join(
                f"- {node.alias}: {node.statement} (revalidated certificate)"
                for node in bank
            )
            system = (
                "Prove the exact Lean theorem supplied by the user. Its bp_* hypotheses "
                "are assumed milestones. Return only the tactic proof body, without `by`, "
                "imports, theorem declarations, sorry, admit, axioms, or native_decide. "
                "Use at least one bp_* hypothesis and only the dependency-relevant ones. "
                "Do not prove the milestones here: "
                "only build the bridge from them to the unchanged final goal."
            )
            user = (
                f"Route: {route.summary}\n{lemma_notes}\n\n"
                f"Reusable verified facts:\n{bank_notes or '(none)'}\n\n"
                f"Exact bridge task:\n```lean\n{bridge_task}\n```"
            )
            try:
                response = await self._complete(
                    services,
                    model=GPT_OSS,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    max_tokens=4500,
                    temperature=0.35,
                )
                return route, bridge_task, extract_proof_body(response.content or "")
            except Exception:
                return route, bridge_task, None

        proposed = await asyncio.gather(*(propose(route) for route in routes))
        verified: list[BridgeRoute] = []
        for route, bridge_task, body in proposed:
            if not self._has_time() or bridge_task is None or body is None:
                continue
            # Earlier milestones may be used to prove the final milestones rather than
            # appearing in the final bridge itself. The bridge must still consume at
            # least one route hypothesis, otherwise it is just an unrelated direct proof.
            if not bridge_used_lemmas(route, body):
                continue
            source = build_goal_source(
                problem.challenge,
                extra_hypotheses=[
                    *[(node.alias, node.statement) for node in bank],
                    *[(lemma.name, lemma.statement) for lemma in route.lemmas],
                ],
                proof_body=body,
            )
            if source is None:
                continue
            self.stats.bridges_checked += 1
            try:
                check = await self._check(services, source)
            except Exception:
                continue
            if self._strictly_accepted(check):
                route.bridge_body = body
                verified.append(route)
                self.stats.bridges_verified += 1
                continue
            # One focused bridge repair is worth doing: it is still much cheaper than
            # attempting all of the route's milestone proofs.
            if not self._has_time():
                continue
            diagnostics = format_messages(check.messages, limit=3000)
            try:
                response = await self._complete(
                    services,
                    model=GPT_OSS,
                    messages=[
                        {"role": "system", "content": (
                            "Repair only the tactic body for the exact locked bridge. "
                            "Return body only; use at least one dependency-relevant bp_* "
                            "hypothesis; no statement "
                            "changes, declarations, sorry, admit, axioms, or native_decide."
                        )},
                        {"role": "user", "content": (
                            f"Exact task:\n```lean\n{bridge_task}\n```\n\n"
                            f"Failed body:\n```lean\n{body}\n```\n\nLean feedback:\n{diagnostics}"
                        )},
                    ],
                    max_tokens=4000,
                    temperature=0.25,
                )
            except Exception:
                continue
            repaired = extract_proof_body(response.content or "")
            if repaired is None or not bridge_used_lemmas(route, repaired):
                continue
            repaired_source = build_goal_source(
                problem.challenge,
                extra_hypotheses=[
                    *[(node.alias, node.statement) for node in bank],
                    *[(lemma.name, lemma.statement) for lemma in route.lemmas],
                ],
                proof_body=repaired,
            )
            if repaired_source is None:
                continue
            self.stats.bridges_checked += 1
            try:
                repaired_check = await self._check(services, repaired_source)
            except Exception:
                continue
            if self._strictly_accepted(repaired_check):
                route.bridge_body = repaired
                verified.append(route)
                self.stats.bridges_verified += 1
        return verified

    async def _route_restates_target(
        self,
        problem: Problem,
        services: Services,
        route: BridgeRoute,
        *,
        bank: list[VerifiedLemmaNode],
    ) -> bool:
        """Use one Lean check to reject exact or binder-generalized target milestones."""

        probe = build_goal_source(
            problem.challenge,
            extra_hypotheses=[
                *[(node.alias, node.statement) for node in bank],
                *[(lemma.name, lemma.statement) for lemma in route.lemmas],
            ],
            proof_body=restatement_probe_body(route),
        )
        if probe is None:
            return False
        try:
            check = await self._check(
                services, probe, timeout_s=min(35, self.check_timeout_s)
            )
        except Exception:
            return False
        return self._strictly_accepted(check)

    async def _rank_routes(
        self,
        problem: Problem,
        services: Services,
        routes: list[BridgeRoute],
        *,
        depth: int,
    ) -> list[BridgeRoute]:
        # Deterministic fallback favours fewer and shorter obligations.
        fallback = sorted(
            routes,
            key=lambda route: (len(route.lemmas), sum(len(x.statement) for x in route.lemmas)),
        )
        if len(routes) == 1 or not self._has_time():
            fallback[0].review_score = 50
            return fallback
        descriptions = []
        for route in routes:
            descriptions.append({
                "id": route.route_id,
                "summary": route.summary,
                "lemmas": [
                    {"name": lemma.name, "statement": lemma.statement,
                     "purpose": lemma.purpose, "proof_hint": lemma.proof_hint}
                    for lemma in route.lemmas
                ],
            })
        system = (
            "Act as an independent critic of another model's already Lean-verified "
            "theorem decompositions. Their bridges compile, "
            "so judge only whether the milestones are genuinely simpler and realistically "
            "provable. Penalize a disguised restatement of the target, False-like "
            "obligations, huge conjunctions, a milestone which re-quantifies parameters "
            "already bound by the locked theorem, or one milestone carrying the whole problem. "
            "Prefer short dependency chains with reusable mathematical content. Return "
            'only JSON: {"ranking":[{"id":"...","score":0,'
            '"verdict":"accept|reject","reason":"..."}]}.'
        )
        review_user = (
            f"Depth: {depth}\nOriginal locked goal:\n{problem.challenge}\n\n"
            f"Verified routes:\n{json.dumps(descriptions, ensure_ascii=False)}"
        )
        payload = None
        # Qwen sometimes provides a useful mathematical audit but is truncated before
        # the required JSON (or a provider returns a transient error). Retry the audit
        # once rather than silently treating an unaudited route as approved.
        for review_attempt in range(2):
            if not self._has_time(25.0):
                break
            retry_note = (
                "\n\nThe previous audit did not produce parseable JSON. Return only the "
                "specified compact JSON now, with one entry per route."
                if review_attempt
                else ""
            )
            try:
                response = await self._complete(
                    services,
                    model=QWEN,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": review_user + retry_note},
                    ],
                    max_tokens=6000 if review_attempt == 0 else 3000,
                    temperature=0.1,
                )
            except Exception:
                continue
            payload = _extract_json(response.content or "")
            if payload is not None and isinstance(payload.get("ranking"), list):
                break
        ranking = payload.get("ranking", []) if payload else []
        if not isinstance(ranking, list):
            return fallback
        by_id = {route.route_id: route for route in routes}
        accepted: list[BridgeRoute] = []
        seen: set[str] = set()
        for item in ranking:
            if not isinstance(item, dict):
                continue
            route_id = str(item.get("id", ""))
            route = by_id.get(route_id)
            if route is None or route_id in seen:
                continue
            verdict = str(item.get("verdict", "accept")).lower()
            try:
                score = max(0, min(100, int(item.get("score", 0))))
            except (TypeError, ValueError):
                score = 0
            route.review_score = score
            route.review_reason = str(item.get("reason", ""))[:500]
            seen.add(route_id)
            if verdict == "accept" and score >= 35:
                accepted.append(route)
        # A malformed response cannot veto Lean-verified routes. A well-formed review
        # that actually inspected at least one route can reject the entire portfolio;
        # the caller then starts a fresh wave with the failure ledger instead of
        # spending proof budget on milestones the independent critic found unsound.
        if not accepted and not seen:
            fallback[0].review_score = max(fallback[0].review_score, 35)
            return fallback
        accepted.sort(key=lambda route: route.review_score, reverse=True)
        return accepted

    async def _prove_locked_goal(
        self, problem: Problem, services: Services
    ) -> ProofAttempt:
        """Prove one exact generated goal; model output can never mutate its header."""

        # Cheap deterministic closers first, collapsed into one serial Lean request.
        direct = await self._try_closing_battery(problem, services)
        if direct is not None:
            self.stats.lemmas_direct += 1
            return ProofAttempt(body=direct)

        last_body = ""
        last_diagnostics = ""
        sequence = [(QWEN, self.q_attempts), (GPT_OSS, self.g_attempts)]
        for model, attempts in sequence:
            for attempt_index in range(attempts):
                if not self._has_time():
                    return ProofAttempt(diagnostics=last_diagnostics)
                system = (
                    "You are proving one immutable Lean 4 + Mathlib subgoal. Return only "
                    "the tactic proof body, without `by`, imports, or declarations. The "
                    "host grafts it under the exact theorem header, so changing the "
                    "statement is impossible. Never use sorry, admit, axioms, or "
                    "native_decide. Build a mathematical chain of small `have` facts; "
                    "use Mathlib automation only where justified. Preserve useful parts "
                    "of a previous body and repair the first Lean error."
                )
                details = ""
                if last_diagnostics:
                    details = (
                        f"\n\nPrevious body:\n```lean\n{last_body}\n```\n"
                        f"Exact Lean feedback:\n{last_diagnostics[:4500]}"
                    )
                user = (
                    f"Context and mathematical guidance:\n{problem.description}\n\n"
                    f"Exact locked task:\n```lean\n{problem.challenge}\n```{details}"
                )
                try:
                    response = await self._complete(
                        services,
                        model=model,
                        messages=[{"role": "system", "content": system},
                                  {"role": "user", "content": user}],
                        max_tokens=5000,
                        temperature=min(1.0, 0.35 + 0.18 * attempt_index),
                        seed=104729 + attempt_index,
                    )
                except Exception:
                    continue
                body = extract_proof_body(response.content or "")
                if body is None:
                    continue
                source = build_goal_source(problem.challenge, proof_body=body)
                if source is None:
                    return ProofAttempt(diagnostics=last_diagnostics)
                try:
                    check = await self._check(services, source)
                except Exception:
                    continue
                if self._strictly_accepted(check):
                    self.stats.lemmas_direct += 1
                    return ProofAttempt(body=body)
                last_body = body
                last_diagnostics = format_messages(check.messages, limit=5000)
        return ProofAttempt(body=None, diagnostics=last_diagnostics)

    async def _compatible_bank(
        self,
        problem: Problem,
        services: Services,
    ) -> list[VerifiedLemmaNode]:
        """Replay executable certificates and return only context-compatible nodes."""

        shape = goal_shape(problem.challenge)
        if shape is None or not self.progress_graph.nodes:
            return []
        compatible: list[VerifiedLemmaNode] = []
        for node in self.progress_graph.candidates(
            goal=shape.goal, context=problem.challenge, limit=8
        ):
            if not self._has_time(20.0):
                break
            source = build_goal_source(
                problem.challenge,
                goal_override=node.statement,
                proof_body=node.certificate,
            )
            if source is None:
                self.progress_graph.reject_incompatible()
                continue
            self.stats.bank_revalidations += 1
            try:
                check = await self._check(
                    services, source, timeout_s=min(45, self.check_timeout_s)
                )
            except Exception:
                self.progress_graph.reject_incompatible()
                continue
            if self._strictly_accepted(check):
                compatible.append(node)
                self.stats.bank_compatible += 1
            else:
                self.progress_graph.reject_incompatible()
        return compatible

    async def _try_bank_closure(
        self,
        problem: Problem,
        services: Services,
        bank: list[VerifiedLemmaNode],
    ) -> str | None:
        """Try and ablate a deterministic closure using revalidated bank facts."""

        if not bank or not self._has_time(30.0):
            return None
        body = closing_battery_body()

        async def closes(nodes: list[VerifiedLemmaNode]) -> bool:
            source = build_goal_source(
                problem.challenge,
                extra_hypotheses=[(node.alias, node.statement) for node in nodes],
                proof_body=body,
            )
            if source is None:
                return False
            try:
                check = await self._check(
                    services, source, timeout_s=min(45, self.check_timeout_s)
                )
            except Exception:
                return False
            return self._strictly_accepted(check)

        if not await closes(bank):
            return None

        # Greedy leave-one-out ablation avoids claiming reuse merely because facts were
        # present in the context. The surviving set is load-bearing for this closer.
        necessary = list(bank)
        for node in list(bank):
            trial = [item for item in necessary if item.node_id != node.node_id]
            if await closes(trial):
                necessary = trial
        if not necessary:
            return None

        assembled_body = self._certificate_body(necessary, [], body)
        assembled = build_goal_source(problem.challenge, proof_body=assembled_body)
        if assembled is None:
            return None
        try:
            final_check = await self._check(services, assembled)
        except Exception:
            return None
        if not self._strictly_accepted(final_check):
            return None
        self.progress_graph.mark_reused(
            [node.node_id for node in necessary], decisive=True
        )
        return assembled_body

    async def greedy_full_bank_close(
        self,
        problem: Problem,
        services: Services,
    ) -> str | None:
        """No-LLM end-of-round close: full bank + path combos + cheap battery.

        Used by residual hygiene (P0.5). Returns a full Lean source on success.
        """

        if not self._has_time(20.0):
            return None
        bank = await self._compatible_bank(problem, services)
        body = await self._try_bank_closure(problem, services, bank)
        if body is None:
            body = await self._try_bank_path_combinations(problem, services, bank)
        if body is None and bank:
            # Last cheap attempt: certificates + closing battery without ablation.
            battery = closing_battery_body()
            assembled_body = self._certificate_body(bank, [], battery)
            assembled = build_goal_source(problem.challenge, proof_body=assembled_body)
            if assembled is not None:
                try:
                    check = await self._check(services, assembled)
                except Exception:
                    check = None
                if self._strictly_accepted(check) and integrity_check(
                    assembled, problem.challenge
                )[0]:
                    self.progress_graph.mark_reused(
                        [node.node_id for node in bank], decisive=True
                    )
                    return assembled
        if body is None:
            body = await self._try_closing_battery(problem, services)
        if body is None:
            return None
        final = build_goal_source(problem.challenge, proof_body=body)
        if final is None:
            return None
        try:
            check = await self._check(services, final)
        except Exception:
            return None
        if self._strictly_accepted(check) and integrity_check(final, problem.challenge)[0]:
            return final
        return None

    async def _try_bank_path_combinations(
        self,
        problem: Problem,
        services: Services,
        bank: list[VerifiedLemmaNode],
    ) -> str | None:
        """Try small bank subsets as alternate assembly paths (Phase B).

        Full-bank closure already ran.  Here we probe size-1 and size-2 subsets so a
        *combination* of harvested facts can close even when the whole bag does not
        (or when leave-one-out would drop the wrong piece under a weak closer).
        """

        if len(bank) < 1 or not self._has_time(45.0):
            return None
        body = closing_battery_body()
        # Prefer high-overlap / recently useful nodes first.
        ordered = list(bank)[:8]
        candidates: list[list[VerifiedLemmaNode]] = [[n] for n in ordered]
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                candidates.append([a, b])
        # Cap attempts so this stays a cheap pre-portfolio probe.
        max_tries = env_int("BP_BANK_PATH_TRIES", 12, minimum=1, maximum=24)
        for subset in candidates[:max_tries]:
            if not self._has_time(25.0):
                break
            self.stats.bank_path_tries += 1
            source = build_goal_source(
                problem.challenge,
                extra_hypotheses=[(node.alias, node.statement) for node in subset],
                proof_body=body,
            )
            if source is None:
                continue
            try:
                check = await self._check(
                    services, source, timeout_s=min(45, self.check_timeout_s)
                )
            except Exception:
                continue
            if not self._strictly_accepted(check):
                continue
            assembled_body = self._certificate_body(subset, [], body)
            assembled = build_goal_source(problem.challenge, proof_body=assembled_body)
            if assembled is None:
                continue
            try:
                final_check = await self._check(services, assembled)
            except Exception:
                continue
            if not self._strictly_accepted(final_check):
                continue
            self.progress_graph.mark_reused(
                [node.node_id for node in subset], decisive=True
            )
            return assembled_body
        return None

    async def _try_closing_battery(
        self,
        problem: Problem,
        services: Services,
    ) -> str | None:
        if not self._has_time():
            return None
        body = closing_battery_body()
        source = build_goal_source(problem.challenge, proof_body=body)
        if source is None:
            return None
        try:
            check = await self._check(
                services, source, timeout_s=min(35, self.check_timeout_s)
            )
        except Exception:
            return None
        return body if self._strictly_accepted(check) else None

    @staticmethod
    def _certificate_body(
        bank: list[VerifiedLemmaNode],
        solved: list[tuple[RouteLemma, str, str | None]],
        final_body: str,
    ) -> str:
        lines: list[str] = []
        for node in bank:
            lines.append(f"have {node.alias} : {node.statement} := by")
            for line in textwrap.dedent(node.certificate).strip().splitlines():
                lines.append("  " + line if line.strip() else line)
        for lemma, body, _node_id in solved:
            lines.append(f"have {lemma.name} : {lemma.statement} := by")
            for line in textwrap.dedent(body).strip().splitlines():
                lines.append("  " + line if line.strip() else line)
        lines.extend(textwrap.dedent(final_body).strip().splitlines())
        return "\n".join(lines)

    @classmethod
    def _assemble_route(
        cls,
        challenge: str,
        bank: list[VerifiedLemmaNode],
        solved: list[tuple[RouteLemma, str]],
        bridge_body: str,
    ) -> str | None:
        expanded = [(lemma, body, None) for lemma, body in solved]
        return build_goal_source(
            challenge,
            proof_body=cls._certificate_body(bank, expanded, bridge_body),
        )

    def _result(self, solution: str, accepted: bool, reason: str) -> AgentResult:
        return AgentResult(solution, {
            "arm": self.arm,
            "protocol": "bridge_portfolio",
            "accepted_by_repl": accepted,
            "stop_reason": reason,
            "progress_graph": self.progress_graph.metadata(),
            **self.stats.metadata(),
        })


def create_agent() -> BridgePortfolioAgent:
    return BridgePortfolioAgent()
