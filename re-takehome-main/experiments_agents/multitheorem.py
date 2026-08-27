"""Multi-theorem wrapper (P1) — solve each theorem in a challenge independently.

Motivation (PROJECT_STATE §19.5): a challenge like ``p09_imo1964`` bundles two
*independent* theorems in one file. Whole-file repair asks a model to prove both at
once; the deterministic sweep fills *every* ``sorry`` with the *same* tactic; and the
verified proof-state search (``statetree``) refuses multi-``:= by`` files outright.
So the two sub-theorems never get an independent, per-theorem shot.

This wrapper is universal (same procedure for every input, no per-problem routing):

1. Split the challenge into top-level declarations.
2. If it holds at most one *provable* declaration (one ``sorry``), defer entirely to
   the inner agent — behaviour is unchanged for the single-theorem problems.
3. Otherwise, build a standalone single-theorem mini-challenge for each provable
   slot (original imports/opens + just that declaration) and solve it with a *fresh*
   inner agent. Each slot is now a single-``:= by`` file, so the sweep and the
   verified search apply to it.
4. If — and only if — *every* slot is solved, reassemble one file (merged
   preamble + each slot solution's declarations) and strict-check it. Success only
   if Lean accepts and the integrity gate passes (all original names intact, no
   ``sorry``/``admit``/``axiom``).
5. On any miss (a slot fails, a slot is not independent, reassembly does not
   compile) fall back to a whole-file inner run on the original problem, so the
   wrapper can never score below the single-agent baseline.

The final acceptance is always the strict comparator path; internal ``sorry`` lives
only in the disposable independence probe.
"""

from __future__ import annotations

import re
from typing import Callable

from re_harness import Agent, AgentResult, Problem, Services

from . import leanprobe as LP
from .common import integrity_check, required_decl_names

# A declaration head: optional modifiers, then the keyword and the name.
_DECL_HEAD = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(theorem|lemma|def|abbrev|instance|example)\b"
)
_IMPORT_OR_OPEN = re.compile(r"^\s*(import|open|set_option|namespace|variable)\b")
_SORRY_RE = re.compile(r"\bsorry\b")


def _trivia_start(lines: list[str], head: int, floor: int) -> int:
    """Extend a declaration's start upward over its leading trivia.

    A Lean 4 declaration owns the doc-comment (``/-- … -/``) and ``@[…]`` attribute
    lines that immediately precede it (no blank line between). Splitting at the bare
    keyword line would strand the *next* declaration's doc-comment at the end of the
    *previous* block — and a doc-comment with no following declaration is a Lean
    error. ``floor`` is the previous declaration's head line (exclusive lower bound).
    """
    j = head - 1
    # attribute lines directly above the keyword
    while j > floor and lines[j].lstrip().startswith("@["):
        j -= 1
    # a doc-comment block whose closing `-/` sits directly above
    if j > floor and lines[j].rstrip().endswith("-/"):
        k = j
        while k > floor and not lines[k].lstrip().startswith(("/--", "/-!", "/-")):
            k -= 1
        if lines[k].lstrip().startswith(("/--", "/-!", "/-")):
            j = k - 1
    return j + 1


def split_declarations(source: str) -> tuple[str, list[str]]:
    """Return ``(preamble, [decl_block, ...])`` by top-level declaration start.

    ``preamble`` is everything before the first declaration (imports/opens/comments).
    Each ``decl_block`` runs from its own start (including its leading doc-comment /
    attributes) up to the next declaration's start (or EOF), so concatenating
    ``preamble`` + all blocks reproduces ``source``.
    """
    lines = source.splitlines(keepends=True)
    heads = [i for i, ln in enumerate(lines) if _DECL_HEAD.match(ln)]
    if not heads:
        return source, []
    starts: list[int] = []
    floor = -1
    for h in heads:
        s = _trivia_start(lines, h, floor)
        starts.append(s)
        floor = h
    preamble = "".join(lines[: starts[0]])
    blocks: list[str] = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(lines)
        blocks.append("".join(lines[s:e]))
    return preamble, blocks


def _preamble_lines(preamble: str) -> list[str]:
    """Keep only import/open/set_option/namespace/variable lines (dedup, in order)."""
    out: list[str] = []
    seen: set[str] = set()
    for ln in preamble.splitlines():
        if _IMPORT_OR_OPEN.match(ln):
            key = ln.strip()
            if key not in seen:
                seen.add(key)
                out.append(ln.rstrip())
    return out


def _block_has_sorry(block: str) -> bool:
    return bool(_SORRY_RE.search(block))


def _merge_preambles(preambles: list[str]) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for pre in preambles:
        for ln in _preamble_lines(pre):
            if ln.strip() not in seen:
                seen.add(ln.strip())
                merged.append(ln)
    return "\n".join(merged)


class MultiTheoremAgent:
    """Solve each provable declaration independently, then reassemble.

    ``make_inner`` must return a fresh single-theorem agent per call (so per-slot
    call/lean counters start clean).
    """

    def __init__(self, *, arm: str, make_inner: Callable[[], Agent]):
        self.arm = arm
        self.make_inner = make_inner

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        challenge = problem.challenge
        preamble, blocks = split_declarations(challenge)
        provable = [b for b in blocks if _block_has_sorry(b)]

        # Single (or zero) provable declaration → unchanged single-agent behaviour.
        if len(provable) <= 1:
            res = await self.make_inner().solve(problem, services)
            return self._tag(res, "single_theorem_delegate", slots=len(provable))

        calls_q = calls_g = lean_checks = 0
        slot_solutions: list[str] = []
        slot_report: list[dict] = []
        all_solved = True

        for block in blocks:
            if not _block_has_sorry(block):
                # Already-complete sibling declaration: carry it through verbatim.
                slot_solutions.append(block.rstrip())
                continue

            name = (required_decl_names(block) or ["?"])[0]
            mini_challenge = self._mini_challenge(preamble, block)

            # Independence probe: does the isolated statement even elaborate?
            root = await services.lean.check_file(
                _SORRY_RE.sub("sorry", mini_challenge)
            )
            lean_checks += 1
            if not LP.probe_valid(root):
                slot_report.append({"name": name, "status": "not_independent"})
                all_solved = False
                break

            mini_problem = Problem(
                id=f"{problem.id}::{name}",
                description=self._focus_description(problem.description, name),
                challenge=mini_challenge,
                metadata=dict(problem.metadata),
            )
            res = await self.make_inner().solve(mini_problem, services)
            md = res.metadata
            calls_q += int(md.get("calls_q", 0) or 0)
            calls_g += int(md.get("calls_g", 0) or 0)
            lean_checks += int(md.get("lean_checks", 0) or 0)
            solved = bool(md.get("accepted_by_repl"))
            slot_report.append({"name": name, "status": "solved" if solved else "miss",
                                "stop_reason": md.get("stop_reason")})
            if not solved:
                all_solved = False
                break
            _pre, sol_blocks = split_declarations(res.solution)
            slot_solutions.append("\n\n".join(b.rstrip() for b in sol_blocks))

        if all_solved and slot_solutions:
            final = self._reassemble(preamble, slot_solutions)
            check = await services.lean.check_file(final)
            lean_checks += 1
            ok, _errs = integrity_check(final, challenge)
            if check.accepted and ok:
                return self._result(final, True, "multi_theorem_solved",
                                    calls_q, calls_g, lean_checks, slot_report)

        # Fallback: whole-file inner run on the original (never below baseline).
        res = await self.make_inner().solve(problem, services)
        md = res.metadata
        calls_q += int(md.get("calls_q", 0) or 0)
        calls_g += int(md.get("calls_g", 0) or 0)
        lean_checks += int(md.get("lean_checks", 0) or 0)
        return self._result(res.solution, bool(md.get("accepted_by_repl")),
                            "multi_theorem_fallback", calls_q, calls_g, lean_checks,
                            slot_report)

    # -- helpers ---------------------------------------------------------------
    def _mini_challenge(self, preamble: str, block: str) -> str:
        pre = "\n".join(_preamble_lines(preamble)) or "import Mathlib"
        return pre + "\n\n" + block.rstrip() + "\n"

    def _focus_description(self, description: str, name: str) -> str:
        return (
            f"{description}\n\n"
            f"[Focus] This file isolates a single theorem `{name}` from a larger "
            f"challenge. Prove exactly this theorem. You may add helper lemmas above "
            f"it, but keep the statement and name of `{name}` unchanged."
        )

    def _reassemble(self, preamble: str, slot_solutions: list[str]) -> str:
        merged_pre = _merge_preambles([preamble] + slot_solutions)
        # Drop preamble lines from each slot body (already merged at the top).
        bodies: list[str] = []
        for sol in slot_solutions:
            _p, blocks = split_declarations(sol)
            body = "\n\n".join(b.rstrip() for b in blocks) if blocks else sol.rstrip()
            bodies.append(body)
        return merged_pre + "\n\n" + "\n\n".join(b for b in bodies if b.strip()) + "\n"

    def _tag(self, res: AgentResult, protocol: str, **extra) -> AgentResult:
        md = dict(res.metadata)
        md["multi_theorem"] = {"protocol": protocol, **extra}
        return AgentResult(res.solution, md)

    def _result(self, solution, accepted, protocol, calls_q, calls_g, lean_checks,
                slot_report) -> AgentResult:
        return AgentResult(solution, {
            "arm": self.arm,
            "protocol": "multi_theorem",
            "multi_theorem_stage": protocol,
            "accepted_by_repl": accepted,
            "stop_reason": protocol,
            "calls_q": calls_q,
            "calls_g": calls_g,
            "lean_checks": lean_checks,
            "slots": slot_report,
        })


def make_multitheorem(*, arm: str, make_inner: Callable[[], Agent]) -> MultiTheoremAgent:
    return MultiTheoremAgent(arm=arm, make_inner=make_inner)
