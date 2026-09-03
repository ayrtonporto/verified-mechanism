"""Lean interaction layer for verified proof-state search (StateTree/LocalPremise).

All of this works through the existing ``services.lean.check_file`` — no harness
change. Confirmed live: ``trace_state`` emits the exact goal state as an [info]
message; ``exact?``/``apply?`` emit the concrete tactic as an [apply] message;
warm checks are sub-second. Everything here is problem-agnostic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .common import sha16

# A probe is "valid" (a well-formed partial proof) if Lean raised no error and did
# not time out. `sorry` warnings are allowed *inside disposable probes only* — the
# final returned file is always checked with the strict comparator path.
GOAL_MARK = "⊢"


def probe_valid(check) -> bool:
    if check.timed_out:
        return False
    return not any(m.get("severity") == "error" for m in check.messages)


def parse_goal_state(messages: list[dict]) -> str:
    """Join the trace_state [info] blocks that contain a goal turnstile."""
    blocks = [
        str(m.get("data", "")).strip()
        for m in messages
        if m.get("severity") == "info" and GOAL_MARK in str(m.get("data", ""))
    ]
    return "\n\n".join(blocks).strip()


def count_goals(goal_state: str) -> int:
    return goal_state.count(GOAL_MARK)


_TRY_PREFIX = re.compile(r"^\s*Try this:\s*", re.IGNORECASE)


_TAG = re.compile(r"^\s*\[[a-zA-Z]+\]\s*")


def _clean_suggestion(data: str) -> str:
    """Reduce a raw suggestion message to a single usable tactic line.

    apply?/exact? data can look like `[apply] refine Foo ?_\n  -- Remaining
    subgoals:\n  -- ⊢ …`. Strip a leading `[tag]`, drop trailing `--` annotation
    lines, and keep the first tactic line."""
    data = _TAG.sub("", data.strip())
    data = _TRY_PREFIX.sub("", data)
    line = data.split("\n", 1)[0].strip()
    return line


def parse_suggestions(messages: list[dict], *, limit: int = 12) -> list[str]:
    """Extract concrete tactic suggestions from exact?/apply?/simp?/find output.

    Returned as [apply]-severity messages and/or [info] `Try this: …` lines.
    Return de-duplicated, cleaned tactic strings (closing/`exact` first)."""
    raw: list[str] = []
    for m in messages:
        sev = m.get("severity")
        data = str(m.get("data", "")).strip()
        if not data:
            continue
        if sev == "apply" or (sev == "info" and _TRY_PREFIX.match(data)):
            tac = _clean_suggestion(data)
            if tac and "sorry" not in tac and "admit" not in tac:
                raw.append(tac)
    # de-dup preserving order; put single-shot closers (`exact …`) first
    seen: set[str] = set()
    uniq: list[str] = []
    for t in sorted(raw, key=lambda s: (not s.startswith("exact "), len(s))):
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:limit]


@dataclass(frozen=True)
class TheoremShell:
    """A single-theorem challenge split into the part before the proof body and
    an indent, so tactics can be appended after `:= by`."""
    preamble: str          # everything up to and including `:= by`
    indent: str            # indentation for tactic lines
    ok: bool               # False if we couldn't split (multi-theorem / term mode)


_BY_SORRY = re.compile(r":=\s*by\b", re.MULTILINE)


def theorem_shell(challenge: str) -> TheoremShell:
    """Split a single-theorem `… := by\\n  sorry` challenge.

    Returns ok=False for term-mode (`:= sorry`) or multi-`:= by` (multi-theorem)
    challenges, which StateTree does not handle in v1 (the caller falls back)."""
    matches = list(_BY_SORRY.finditer(challenge))
    if len(matches) != 1:
        return TheoremShell("", "  ", ok=False)
    end = matches[0].end()
    preamble = challenge[:end]
    # indentation = whitespace of the first non-empty line after `:= by`
    tail = challenge[end:]
    indent = "  "
    for line in tail.splitlines():
        if line.strip():
            lead = line[: len(line) - len(line.lstrip())]
            indent = lead if lead else "  "
            break
    return TheoremShell(preamble=preamble, indent=indent, ok=True)


def build_probe(shell: TheoremShell, prefix_tactics: str, *, trace: bool) -> str:
    """Build a disposable probe file: the theorem with `prefix_tactics` applied,
    then (optionally) `trace_state` and `all_goals sorry` to close the rest so the
    partial proof elaborates without an 'unsolved goals' error."""
    lines = [shell.preamble]
    body = prefix_tactics.strip("\n")
    for ln in body.splitlines():
        lines.append(shell.indent + ln if ln.strip() else ln)
    if trace:
        # `try` so a prefix that already closed all goals does not error here;
        # then has_sorry distinguishes solved (no goals → no sorry) from partial.
        lines.append(shell.indent + "try trace_state")
    lines.append(shell.indent + "all_goals sorry")
    return "\n".join(lines) + "\n"


def build_final(shell: TheoremShell, prefix_tactics: str) -> str:
    """Build the strict candidate (no trace/sorry) for real acceptance."""
    lines = [shell.preamble]
    for ln in prefix_tactics.strip("\n").splitlines():
        lines.append(shell.indent + ln if ln.strip() else ln)
    return "\n".join(lines) + "\n"


def build_search(shell: TheoremShell, prefix_tactics: str, search_tac: str) -> str:
    """Build a probe that runs a search tactic (apply?/exact?/…) at the current
    state to harvest real Mathlib premises."""
    lines = [shell.preamble]
    for ln in prefix_tactics.strip("\n").splitlines():
        if ln.strip():
            lines.append(shell.indent + ln)
    lines.append(shell.indent + search_tac)
    lines.append(shell.indent + "all_goals sorry")
    return "\n".join(lines) + "\n"


def state_hash(goal_state: str) -> str:
    """Hash of the normalized goal state for dedup (whitespace-insensitive)."""
    return sha16(re.sub(r"\s+", " ", goal_state).strip())
