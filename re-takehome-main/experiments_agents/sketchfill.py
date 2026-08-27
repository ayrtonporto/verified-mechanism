"""Sketch-and-fill with verified independent holes (the depth lever).

PROJECT_STATE §19.4 pinned the ceiling as the *action policy*: Q/G cannot chain
more than ~2 Lean-verified steps on a hard goal. A free-form tactic tree plays to
that weakness. This agent plays to the models' *strength* — writing a structured
mathematical argument — while keeping Lean as the strong checker, and it factorises
the difficulty so no single verified chain has to be deep:

1. Ask the proposer for a proof *skeleton*: a sequence of ``have hi : Pi := by
   sorry`` steps that decompose the goal, then a final step that closes it using the
   ``have``s. The model writes structure, not the hole proofs.
2. **Compose-check the skeleton**: elaborate it with every hole left as ``sorry``.
   If Lean raises no error, the decomposition is logically valid — the final step
   really follows from the ``have`` statements. A bad skeleton is rejected here,
   cheaply, before any effort goes into holes. (This is the filter free-form search
   lacks.)
3. **Fill each hole in place, independently**: for hole ``i`` we probe its exact
   goal state (``trace_state`` at that hole, all other holes still ``sorry``), then
   try the deterministic tactic sweep and a few targeted model tactics, Lean-checking
   each candidate with only hole ``i`` filled. The first candidate that elaborates
   freezes the hole. Each hole is a shallow, independent sub-proof.
4. When every hole is filled, assemble the final file (original statement + filled
   body), strict-check it, and accept only past the integrity gate.

Universal: same skeleton protocol, same sweep, same hole procedure for every
problem. Multiple skeleton samples give diversity. Falls back to whole-file
tactic-augmented repair so it never scores below baseline. Internal ``sorry`` lives
only in disposable probes; acceptance is the strict comparator path.
"""

from __future__ import annotations

import json
import re
import textwrap

from re_harness import AgentResult, Problem, Services

from . import leanprobe as LP
from .common import (
    CLOSING_TACTICS,
    SWEEP_CHECK_TIMEOUT_S,
    count_model_calls,
    env_int,
    env_float,
    format_messages,
    integrity_check,
    require_model,
)

_FORBIDDEN = ("admit", "axiom", "import ", "theorem ", "lemma ")
_BY = re.compile(r":=\s*by\b")
_SORRY = re.compile(r"\bsorry\b")


class SketchFillAgent:
    def __init__(self, *, arm: str, propose_model: str, fill_model: str):
        self.arm = arm
        self.propose_model = require_model(propose_model)
        self.fill_model = require_model(fill_model)
        self.max_skeletons = env_int("SF_MAX_SKELETONS", 4, minimum=1, maximum=16)
        self.fill_actions = env_int("SF_FILL_ACTIONS", 5, minimum=1, maximum=12)
        self.max_holes = env_int("SF_MAX_HOLES", 12, minimum=1, maximum=40)
        self.check_timeout = env_int("SF_CHECK_TIMEOUT_S", 30, minimum=5, maximum=180)
        self.max_tokens = env_int("SF_MAX_TOKENS", 4000, minimum=500, maximum=16000)
        self.temperature = env_float("SF_TEMPERATURE", 0.6, minimum=0.0, maximum=2.0)

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        self._q = self._g = self._checks = 0
        stats = {"skeletons": 0, "composed": 0, "holes_seen": 0, "holes_filled": 0}

        shell = LP.theorem_shell(problem.challenge)
        if not shell.ok:
            return await self._fallback(problem, services, "fallback_multi", stats)

        # cheap free win first
        for tactic, variant in _sweep(problem.challenge):
            c = await services.lean.check_file(variant, timeout_s=SWEEP_CHECK_TIMEOUT_S)
            self._checks += 1
            if c.accepted and integrity_check(variant, problem.challenge)[0]:
                return self._result(variant, True, "tactic_sweep", stats)

        for attempt in range(self.max_skeletons):
            body = await self._propose_skeleton(services, problem, attempt)
            if body is None:
                continue
            stats["skeletons"] += 1
            solved = await self._try_skeleton(services, problem, shell, body, stats)
            if solved is not None:
                return solved

        return await self._fallback(problem, services, "sketch_exhausted", stats)

    async def _try_skeleton(self, services, problem, shell, body, stats):
        parts = _SORRY.split(body)
        n_holes = len(parts) - 1
        if n_holes == 0 or n_holes > self.max_holes:
            return None

        # (2) compose-check: all holes = sorry must elaborate without error
        composed = _render(parts, ["sorry"] * n_holes)
        probe = _build(shell, composed)
        c = await services.lean.check_file(probe, timeout_s=self.check_timeout)
        self._checks += 1
        if not LP.probe_valid(c):
            return None
        stats["composed"] += 1
        stats["holes_seen"] += n_holes

        fills = ["sorry"] * n_holes
        for i in range(n_holes):
            got = await self._fill_hole(services, problem, shell, parts, fills, i)
            if got is None:
                return None  # this skeleton is dead; caller samples another
            fills[i] = got
            stats["holes_filled"] += 1

        final = _build_final(shell, _render(parts, fills))
        fc = await services.lean.check_file(final, timeout_s=self.check_timeout)
        self._checks += 1
        if fc.accepted and integrity_check(final, problem.challenge)[0]:
            return self._result(final, True, "sketch_fill_solved", stats)
        return None

    async def _fill_hole(self, services, problem, shell, parts, fills, i):
        # (3a) deterministic sweep in place
        for tac in CLOSING_TACTICS:
            cand = fills.copy()
            cand[i] = tac
            probe = _build(shell, _render(parts, cand))
            c = await services.lean.check_file(probe, timeout_s=SWEEP_CHECK_TIMEOUT_S)
            self._checks += 1
            if LP.probe_valid(c) and not _has_sorry_in_hole(tac):
                return tac

        # (3b) probe the exact goal at this hole, then ask the model for tactics
        trace_cand = fills.copy()
        trace_cand[i] = "trace_state; sorry"
        tprobe = _build(shell, _render(parts, trace_cand))
        tc = await services.lean.check_file(tprobe, timeout_s=self.check_timeout)
        self._checks += 1
        goal = LP.parse_goal_state(tc.messages)
        if not goal:
            return None

        actions = await self._ask_fill(services, problem, goal)
        last_err = ""
        for act in actions:
            cand = fills.copy()
            cand[i] = act
            probe = _build(shell, _render(parts, cand))
            c = await services.lean.check_file(probe, timeout_s=self.check_timeout)
            self._checks += 1
            if LP.probe_valid(c):
                return act
            last_err = format_messages(c.messages)[:1500]

        # (3c) one repair round from the exact error
        if last_err:
            rep = await self._ask_fill(services, problem, goal, error=last_err,
                                       tried=actions)
            for act in rep:
                cand = fills.copy()
                cand[i] = act
                probe = _build(shell, _render(parts, cand))
                c = await services.lean.check_file(probe, timeout_s=self.check_timeout)
                self._checks += 1
                if LP.probe_valid(c):
                    return act
        return None

    # -- model I/O --------------------------------------------------------------
    async def _propose_skeleton(self, services, problem, attempt):
        system = "\n".join([
            "You are decomposing a Lean 4 (Mathlib) proof into a verifiable skeleton.",
            "Return ONE ```lean code block: the COMPLETE theorem, its statement copied",
            "verbatim from the challenge, and a proof body that is a sequence of",
            "`have hi : <statement> := by sorry` steps decomposing the goal, followed by",
            "a FINAL step that closes the goal using those `have`s (e.g. `exact ...`,",
            "`simpa using ...`, `omega`, `linarith [...]`).",
            "Rules:",
            "- Leave EACH `have` proof as `by sorry` — do NOT prove them here.",
            "- The FINAL step must NOT be sorry; it must really follow from the `have`s.",
            "- Choose `have` statements that are individually easy to prove and that",
            "  together clearly imply the goal (good intermediate facts, base/step of an",
            "  induction, the two directions of an iff, case splits made explicit).",
            "- Keep names/statement of the target theorem unchanged; no new axioms.",
        ])
        user = "\n".join([
            f"Problem id: {problem.id}",
            f"Skeleton attempt: {attempt + 1}/{self.max_skeletons}",
            "", "Problem description:", problem.description,
            "", "Challenge Lean file:", "```lean", problem.challenge, "```",
        ])
        resp = await services.llm.complete(
            model=self.propose_model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=self.max_tokens,
            temperature=self.temperature if attempt else max(0.2, self.temperature - 0.3),
        )
        self._q, self._g = count_model_calls(self.propose_model, self._q, self._g)
        return _extract_body(resp.content)

    async def _ask_fill(self, services, problem, goal, *, error="", tried=None):
        system = "\n".join([
            "You are proving ONE small Lean 4 (Mathlib) subgoal.",
            f"Return ONLY a JSON array of {self.fill_actions} candidate proofs for the",
            'goal, most-promising first: [{"tactic": "..."}, ...].',
            "Each `tactic` is a self-contained proof of THIS goal: one or a few tactic",
            "commands, or a single term. <=400 chars. No sorry/admit/axiom, no imports,",
            "no theorem/lemma declarations. Prefer Mathlib automation (omega, simp,",
            "simp_all, norm_num, nlinarith, positivity, decide, aesop, ring) and named",
            "lemmas; you may combine with `<;>` or `first | .. | ..`.",
        ])
        lines = ["Exact goal state (prove the `⊢` goal in this local context):",
                 "```", goal, "```"]
        if error:
            lines += ["", "Your previous attempts failed. Lean error:", error,
                      "Already tried (do not repeat):", "; ".join(tried or [])]
        resp = await services.llm.complete(
            model=self.fill_model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": "\n".join(lines)}],
            max_tokens=1500, temperature=0.5,
        )
        self._q, self._g = count_model_calls(self.fill_model, self._q, self._g)
        return _parse_actions(resp.content, self.fill_actions)

    async def _fallback(self, problem, services, reason, stats):
        from .tactics import make_tactic_agent
        agent = make_tactic_agent(arm=f"{self.arm}-fb", propose_model=self.propose_model,
                                  repair_model=self.fill_model)
        res = await agent.solve(problem, services)
        md = res.metadata
        self._q += int(md.get("calls_q", 0) or 0)
        self._g += int(md.get("calls_g", 0) or 0)
        self._checks += int(md.get("lean_checks", 0) or 0)
        return self._result(res.solution, bool(md.get("accepted_by_repl")), reason, stats)

    def _result(self, solution, accepted, stop_reason, stats):
        return AgentResult(solution, {
            "arm": self.arm, "protocol": "sketch_fill",
            "propose_model": self.propose_model, "fill_model": self.fill_model,
            "accepted_by_repl": accepted, "stop_reason": stop_reason,
            "calls_q": self._q, "calls_g": self._g, "lean_checks": self._checks,
            "sketch_stats": stats,
        })


# -- pure helpers (unit-testable without Lean) ---------------------------------
def _sweep(challenge):
    from .common import tactic_sweep_variants
    return tactic_sweep_variants(challenge)


def _render(parts: list[str], fills: list[str]) -> str:
    out = parts[0]
    for j, f in enumerate(fills):
        out += f + parts[j + 1]
    return out


def _has_sorry_in_hole(tac: str) -> bool:
    return "sorry" in tac


def _extract_body(text: str) -> str | None:
    """Pull the proof body (tactics after the theorem's `:= by`) from a model file."""
    if not text:
        return None
    m = re.search(r"```(?:lean|lean4)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    src = m.group(1) if m else text
    by = list(_BY.finditer(src))
    if not by:
        return None
    # The theorem's own `:= by` is the FIRST one; later `:= by` belong to the
    # skeleton's `have` steps. The proof body is everything after the theorem's.
    tail = src[by[0].end():]
    body = textwrap.dedent(tail).strip("\n")
    # must contain at least one hole to be a skeleton
    if not _SORRY.search(body):
        return None
    if any(f in body for f in ("admit", "axiom ", "import ", "\ntheorem ", "\nlemma ")):
        return None
    return body


def _build(shell, body: str) -> str:
    """Probe file: the skeleton body grafted under the exact challenge statement.

    No trailing `all_goals sorry`: the body must END in a real closer, so the
    compose-check truly verifies the final step discharges the goal from the
    `have`s (holes left as `sorry` only stand in for the intermediate facts).
    """
    lines = [shell.preamble]
    for ln in body.split("\n"):
        lines.append(shell.indent + ln if ln.strip() else ln)
    return "\n".join(lines) + "\n"


def _build_final(shell, body: str) -> str:
    return _build(shell, body)


def _parse_actions(text: str, limit: int) -> list[str]:
    out: list[str] = []
    m = re.search(r"\[.*\]", text or "", flags=re.DOTALL)
    if m:
        try:
            for item in json.loads(m.group(0)):
                if isinstance(item, dict):
                    out.append(str(item.get("tactic", "")))
                elif isinstance(item, str):
                    out.append(item)
        except (json.JSONDecodeError, TypeError):
            pass
    cleaned = []
    seen = set()
    for t in out:
        t = t.strip()
        if t and t not in seen and len(t) <= 400 and "sorry" not in t \
                and not any(f in t.lower() for f in _FORBIDDEN):
            seen.add(t)
            cleaned.append(t)
    return cleaned[:limit]


def make_sketch_fill(*, arm: str, propose_model: str, fill_model: str) -> SketchFillAgent:
    return SketchFillAgent(arm=arm, propose_model=propose_model, fill_model=fill_model)
