"""NearMissFinisher + verified-lemma bank (universal proof rescue).

Validated 2026-08-27: taking a failed candidate, truncating it to its maximum
Lean-verified prefix of top-level tactic steps, and appending a fixed universal menu
of *composed* finishers (`all_goals`/`rcases … <;>` cascades that the single-tactic
battery lacks) closed `p09_b` from a real model attempt — a near-miss nothing else
closed. This module packages that rescue so any arm can call it as a post-process.

Also provides a verified-lemma bank: extract each `have NAME : STMT := by …` from a
(partially) verified candidate, re-check it in isolation, and expose the ones that
elaborate. A later attempt on a sibling theorem can be offered these already-proven
intermediate facts (indexed by their statement text — universal, no problem routing).

Everything universal: the same finisher menu and the same extraction on every input.
`sorry` appears only in disposable probes; final acceptance stays the strict path.
"""

from __future__ import annotations

import re
from typing import Callable

from re_harness import Agent, AgentResult, Problem, Services

from .common import integrity_check

# Fixed universal composed-finisher menu. Ordered cheap→heavy. No problem-specific
# lemmas: only structural combinators + the standard automation battery.
COMPOSED_FINISHERS: tuple[str, ...] = (
    "all_goals simp_all",
    "all_goals omega",
    "all_goals norm_num",
    "all_goals decide",
    "all_goals (simp_all <;> omega)",
    "all_goals (norm_num at * <;> omega)",
    "all_goals (first | omega | simp_all | norm_num | decide | contradiction)",
    "all_goals (simp_all <;> norm_num <;> omega)",
    "simp_all",
    "omega",
    "simp_all <;> omega",
    "norm_num at *",
    "decide",
)

_BY = re.compile(r":=\s*by\b")
_HAVE = re.compile(r"^(\s*)have\s+([A-Za-z_][A-Za-z0-9_']*)\s*:\s*(.+?):=\s*by\b",
                   re.DOTALL)


def split_header_body(source: str) -> tuple[str, str] | None:
    """Split a single-theorem file at the theorem's own `:= by` (the first one)."""
    m = _BY.search(source)
    if not m:
        return None
    return source[:m.end()], source[m.end():].strip("\n")


def _base_prefixes(body: str) -> list[str]:
    """Cumulative prefixes ending at each top-level (base-indent) tactic step."""
    lines = body.split("\n")
    nz = [l for l in lines if l.strip()]
    if not nz:
        return []
    base = min(len(l) - len(l.lstrip()) for l in nz)
    idx = [i for i, l in enumerate(lines) if l.strip()
           and (len(l) - len(l.lstrip())) == base and not l.lstrip().startswith("--")]
    return ["\n".join(lines[:(idx[j + 1] if j + 1 < len(idx) else len(lines))]).rstrip()
            for j in range(len(idx))]


def _reindent(header: str, prefix: str, extra: str = "") -> str:
    ind = "  "
    body = "\n".join(ind + l if l.strip() else l for l in prefix.split("\n"))
    tail = ("\n" + ind + extra) if extra else ""
    return header + "\n" + body + tail + "\n"


async def rescue(services: Services, source: str, *, timeout_s: int = 90,
                 integrity=None, challenge: str | None = None) -> str | None:
    """Truncate `source` to its max verified prefix, then try composed finishers.

    Returns a strictly-accepted (no-sorry, integrity-preserving) source, or None.
    """
    sh = split_header_body(source)
    if not sh:
        return None
    header, body = sh
    prefixes = _base_prefixes(body)
    if not prefixes:
        return None

    # find the deepest prefix that elaborates (remaining goals stubbed with sorry)
    best_pref = None
    for pref in prefixes:
        probe = _reindent(header, pref, "all_goals sorry")
        c = await services.lean.check_file(probe, timeout_s=timeout_s)
        if not c.timed_out and not any(m.get("severity") == "error" for m in c.messages):
            best_pref = pref
        else:
            break
    if best_pref is None:
        return None

    for fin in COMPOSED_FINISHERS:
        cand = _reindent(header, best_pref, fin)
        c = await services.lean.check_file(cand, timeout_s=timeout_s)
        if c.accepted and not c.has_sorry:
            if integrity and challenge is not None and not integrity(cand, challenge)[0]:
                continue
            return cand
    return None


class NearMissWrapper:
    """Run an inner agent; if it does not close, rescue its best candidate.

    Universal: on any problem, if the inner agent's returned source is not accepted,
    truncate it to its max verified prefix and try the composed-finisher menu. Never
    scores below the inner agent (rescue only ever turns a miss into a solve).
    """

    def __init__(self, *, arm: str, make_inner: Callable[[], Agent], timeout_s: int = 90):
        self.arm = arm
        self.make_inner = make_inner
        self.timeout_s = timeout_s

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        res = await self.make_inner().solve(problem, services)
        if res.metadata.get("accepted_by_repl"):
            return res
        rescued = await rescue(services, res.solution, timeout_s=self.timeout_s,
                               integrity=integrity_check, challenge=problem.challenge)
        if rescued is None:
            return res
        md = dict(res.metadata)
        md.update({"arm": self.arm, "accepted_by_repl": True,
                   "stop_reason": "nearmiss_rescue", "nearmiss_rescued": True})
        return AgentResult(rescued, md)


def make_nearmiss(*, arm: str, make_inner: Callable[[], Agent]) -> NearMissWrapper:
    return NearMissWrapper(arm=arm, make_inner=make_inner)


def extract_verified_have_texts(source: str) -> list[tuple[str, str]]:
    """Return `(statement, full_have_block_text)` for each `have … : … := by …`.

    Statement text only (no proof) is the bank key; the full block is what a later
    attempt can paste. Verification that each elaborates is the caller's job (via a
    probe) — this is a pure-text extractor.
    """
    out: list[tuple[str, str]] = []
    for m in re.finditer(r"(^[ \t]*)have\s+([A-Za-z_][\w']*)\s*:\s*(.+?)\s*:=\s*by",
                         source, flags=re.MULTILINE | re.DOTALL):
        stmt = re.sub(r"\s+", " ", m.group(3)).strip()
        if stmt and len(stmt) < 300:
            out.append((stmt, m.group(0)))
    return out
