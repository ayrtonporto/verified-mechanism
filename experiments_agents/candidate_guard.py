"""Universal answer-shape and non-circularity guards.

Lean acceptance alone is not enough for a challenge containing an answer definition.
For example, defining a requested solution set as ``{x | P x}`` makes the promised
characterisation ``P x <-> x ∈ solution`` tautological.  A bare ``fun k => RHS`` with
``theorem : RHS = solution k := by rfl`` is the same failure mode for closed forms.

The final comparator may still reject answer constants that do not match the challenge
export shape even when the warm REPL accepts the file.  This module therefore:

* locks declaration signatures (strict integrity);
* enforces numeric literal contracts from the manifest when present;
* **infers** answer ``def``/``abbrev`` names from the challenge when the set manifest
  omits ``definition_names`` (common on lab sets);
* rejects **structural** tautologies without Lean (set-builder restating the goal,
  lambda copying the theorem RHS, pure ``rfl`` characterisation);
* runs the Lean definitional probe on remaining non-numeric answer defs.

No problem ids.  Probes contain no ``sorry`` or new axioms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from re_harness import Problem, Services
from re_harness.lean import numeric_answers_are_literals

from .common import strict_integrity_check
from .multitheorem import _merge_preambles, split_declarations


_DECL = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+)*"
    r"(theorem|lemma|def|abbrev|instance|example)\s+"
    r"([A-Za-z_][A-Za-z0-9_.']*)\b",
    re.MULTILINE,
)
_PROOF_START = re.compile(r":=\s*by\b")
_DEF_BODY = re.compile(
    r"(?s)^\s*(?:noncomputable\s+|private\s+|protected\s+)*"
    r"(?:def|abbrev)\s+([A-Za-z_][A-Za-z0-9_.']*)\b"
    r".*?:=\s*(?:by\b\s*)?(.*)\Z"
)
_SET_BUILDER = re.compile(r"\{[^{}]*\|[^{}]+\}")
_FUN_LAMBDA = re.compile(
    r"(?s)^\s*fun\s+([A-Za-z_][A-Za-z0-9_']*)\s*=>\s*(.+)\s*\Z"
)
_TRIVIAL_PROOF = re.compile(
    r"(?s)^\s*(?:by\b\s*)?(?:rfl|simp(?:_all)?|trivial|exact\s+rfl)\s*;?\s*(?:done\s*)?\Z",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GuardResult:
    accepted: bool
    errors: tuple[str, ...] = ()
    lean_checks: int = 0


def _manifest_names(problem: Problem, key: str) -> tuple[str, ...]:
    manifest = problem.metadata.get("__manifest__", {})
    if not isinstance(manifest, dict):
        return ()
    values = manifest.get(key, ())
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value) for value in values)


def _info(block: str) -> tuple[str, str] | None:
    match = _DECL.search(block or "")
    return (match.group(1), match.group(2)) if match else None


def _strict(check) -> bool:
    return bool(
        check
        and check.accepted
        and not getattr(check, "has_sorry", False)
        and not getattr(check, "timed_out", False)
    )


def _norm_expr(text: str) -> str:
    """Whitespace-insensitive expression key for structural comparisons."""

    t = (text or "").strip()
    t = re.sub(r"--[^\n]*", "", t)
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.DOTALL)
    t = re.sub(r"\s+", "", t)
    return t.lower()


def challenge_definition_names(challenge: str) -> set[str]:
    """All top-level ``def``/``abbrev`` names in the locked challenge (no ids)."""

    names: set[str] = set()
    try:
        _pre, blocks = split_declarations(challenge)
    except Exception:
        return names
    for block in blocks:
        info = _info(block)
        if info is not None and info[0] in {"def", "abbrev"}:
            names.add(info[1])
    return names


def _definition_body(block: str) -> str:
    match = _DEF_BODY.search(block or "")
    if match is None:
        return ""
    body = match.group(2).strip()
    # Drop trailing nested decls if any slipped in (should not after split).
    return body


def _theorem_statement(block: str) -> str:
    """Rough theorem type text between name/binders and ``:=``."""

    m = re.search(
        r"(?s)^\s*(?:theorem|lemma)\s+[A-Za-z_][A-Za-z0-9_.']*\b(.*):=\s*by",
        block or "",
    )
    if m is None:
        return block or ""
    return m.group(1)


def _theorem_proof_body(block: str) -> str:
    marker = _PROOF_START.search(block or "")
    if marker is None:
        return ""
    return (block[marker.end() :] or "").strip()


def structurally_circular_definition(
    name: str,
    definition_block: str,
    theorem_blocks: Iterable[str],
) -> str | None:
    """Return an English error if the answer def is a pure restatement (no Lean).

    Catches the overnight Putnam false-hope class:
    - ``solution := {p | P p}`` with theorem ``P ↔ p ∈ solution``
    - ``solution := fun k => E`` with theorem ``E = solution k`` closed by ``rfl``
    """

    body = _definition_body(definition_block)
    if not body or re.search(r"\bsorry\b", body, re.I):
        return None
    body_n = _norm_expr(body)
    name_n = name.lower()

    for theorem in theorem_blocks:
        t_info = _info(theorem)
        if t_info is None or t_info[0] not in {"theorem", "lemma"}:
            continue
        if re.search(rf"\b{re.escape(name)}\b", theorem) is None:
            continue
        stmt = _theorem_statement(theorem)
        stmt_n = _norm_expr(stmt)
        proof = _theorem_proof_body(theorem)
        proof_trivial = bool(_TRIVIAL_PROOF.match(proof))

        # Lambda closed form copied into `E = name k` / `name k = E`.
        lam = _FUN_LAMBDA.match(body.strip())
        if lam is not None:
            binder, expr = lam.group(1), lam.group(2).strip()
            expr_n = _norm_expr(expr)
            # Strip `name binder` / `name binder` applications from both sides.
            left_eq = re.search(
                rf"(?s)(.+?)=(?:\s*){re.escape(name)}\s+{re.escape(binder)}\b",
                stmt,
            )
            right_eq = re.search(
                rf"(?s){re.escape(name)}\s+{re.escape(binder)}\b(?:\s*)=(.+)",
                stmt,
            )
            for side in (
                left_eq.group(1) if left_eq else None,
                right_eq.group(1) if right_eq else None,
            ):
                if side is None:
                    continue
                if _norm_expr(side) == expr_n and (proof_trivial or expr_n in stmt_n):
                    return (
                        f"definition `{name}` restates the theorem RHS as "
                        f"`fun {binder} => …` (definitional/tautological); "
                        "return a closed canonical answer"
                    )
            # Even without binder match: theorem is `… = name _` and proof is only rfl
            # while the def body is a lambda of the same shape as the left/right expr.
            if proof_trivial and name_n in stmt_n and expr_n and expr_n in stmt_n:
                return (
                    f"definition `{name}` is a lambda copy of the characterisation "
                    "(definitional/tautological); return a closed canonical answer"
                )

        # Set-builder answer: membership characterisation becomes immediate.
        if _SET_BUILDER.search(body):
            # Any characterisation theorem mentioning the answer name + membership/iff
            # is treated as the classic "{x | P} + (P ↔ x ∈ solution)" false hope,
            # even when binders were renamed (p vs a,b) or the proof is non-rfl.
            membership = bool(
                "∈" in stmt
                or "\\in" in stmt
                or "mem" in stmt_n
                or "↔" in stmt
                or "\\iff" in stmt
                or "iff" in stmt_n
            )
            if membership and name_n in stmt_n:
                return (
                    f"definition `{name}` is a set-builder restating the goal "
                    "property (definitional/tautological); return a closed canonical answer"
                )
            inner = re.search(r"\{[^{}]*\|([^{}]+)\}", body)
            prop = (inner.group(1) if inner else "").strip()
            prop_n = _norm_expr(prop)
            if prop_n and len(prop_n) >= 8 and prop_n in stmt_n:
                return (
                    f"definition `{name}` is a set-builder restating the goal "
                    "property (definitional/tautological); return a closed canonical answer"
                )
            if proof_trivial and membership:
                return (
                    f"definition `{name}` makes membership characterisation "
                    "definitional/tautological; return a closed canonical answer"
                )

        # Generic: proof is only rfl/simp and the theorem mentions the answer name.
        if proof_trivial and name_n in stmt_n:
            # Avoid flagging hard theorems that happen to end with `rfl` after real work
            # only when the def body is short/copy-like or appears inside the statement.
            if body_n and (body_n in stmt_n or len(body_n) < 400):
                # Require stronger signal: equality involving the name, or iff/membership.
                if (
                    re.search(rf"{re.escape(name)}\s", stmt)
                    or "↔" in stmt
                    or "\\iff" in stmt
                    or "∈" in stmt
                ):
                    return (
                        f"definition `{name}` makes its characterisation theorem "
                        "definitional/tautological; return a closed canonical answer"
                    )
    return None


def resolve_answer_definition_names(
    problem: Problem,
    *,
    challenge_decl_names: set[str],
) -> tuple[set[str], set[str]]:
    """Return ``(all_answer_defs, numeric_answer_defs)`` for guard probes.

    Manifest wins when populated.  When ``definition_names`` is empty (lab sets),
    fall back to every challenge ``def``/``abbrev`` still present in the locked file.
    """

    challenge = getattr(problem, "challenge", "") or ""
    inferred = challenge_definition_names(challenge) & challenge_decl_names
    manifest_defs = {
        name
        for name in _manifest_names(problem, "definition_names")
        if name in challenge_decl_names
    }
    numeric = {
        name
        for name in _manifest_names(problem, "numeric_answer_names")
        if name in challenge_decl_names
    }
    # Prefer explicit manifest list; else inferred challenge defs/abbrevs.
    defs = set(manifest_defs) if manifest_defs else set(inferred)
    # Numeric names always stay in the answer set even if only listed there.
    defs |= set(numeric)
    return defs, set(numeric)


def _definitional_probe(block: str, definition_name: str) -> str | None:
    """Replace one theorem proof by a strict, cheap definitional-only proof."""

    marker = _PROOF_START.search(block or "")
    if marker is None:
        return None
    return (
        block[: marker.end()].rstrip()
        + "\n  first\n"
        + "    | (rfl <;> done)\n"
        + "    | (simp_all <;> done)\n"
        # `simp_all` alone does not necessarily expose membership in an `abbrev`
        # written as `by exact fun p => ...`.  These two symmetric probes force the
        # dependent side of a characterisation to be viewed as an application of the
        # answer definition, then use only transparent reduction and simp.  The `_`
        # keeps this independent of binder names and tuple arity.
        + f"    | (change _ ↔ {definition_name} _; unfold {definition_name}; "
        + "dsimp; simp_all [one_div] <;> done)\n"
        + f"    | (change {definition_name} _ ↔ _; unfold {definition_name}; "
        + "dsimp; simp_all [one_div] <;> done)\n"
        + f"    | (change _ = {definition_name} _; unfold {definition_name}; "
        + "dsimp; rfl)\n"
        + f"    | (change {definition_name} _ = _; unfold {definition_name}; "
        + "dsimp; rfl)\n"
    )


async def definition_is_circular(
    services: Services,
    *,
    preamble: str,
    context_blocks: Iterable[str],
    definition_block: str,
    dependent_blocks: Iterable[str],
    timeout_s: int = 45,
) -> tuple[bool, int]:
    """Return whether a non-numeric definition trivialises a dependent theorem.

    Only declarations needed to elaborate the answer and the probed theorem are kept.
    Earlier theorem proofs are deliberately excluded so a sibling cannot make the probe
    pass for an unrelated reason.
    """

    info = _info(definition_block)
    if info is None:
        return False, 0
    _kind, name = info
    base: list[str] = []
    for block in context_blocks:
        block_info = _info(block)
        if (
            block_info is not None
            and block_info[0] not in {"theorem", "lemma", "example"}
            and block_info[1] != name
        ):
            base.append(block)
    base.append(definition_block)

    checks = 0
    for theorem in dependent_blocks:
        theorem_info = _info(theorem)
        if (
            theorem_info is None
            or theorem_info[0] not in {"theorem", "lemma"}
            or re.search(rf"\b{re.escape(name)}\b", theorem) is None
        ):
            continue
        probe_block = _definitional_probe(theorem, name)
        if probe_block is None:
            continue
        source = _merge_preambles([preamble]) + "\n\n" + "\n\n".join(
            block.rstrip() for block in [*base, probe_block]
        ) + "\n"
        try:
            check = await services.lean.check_file(source, timeout_s=timeout_s)
            checks += 1
        except Exception:
            continue
        if _strict(check):
            return True, checks
    return False, checks


async def validate_solution_candidate(
    problem: Problem,
    services: Services,
    candidate: str,
    *,
    timeout_s: int = 45,
) -> GuardResult:
    """Apply the shape contract, structural tautology filters, and Lean probes."""

    # Final acceptance must lock declaration *signatures*, not only names.  A candidate
    # that unfolds `= answer` into `= 49` can pass the warm REPL and still be rejected by
    # Comparator; the permissive inner `integrity_check` is intentionally not used here.
    ok, errors = strict_integrity_check(candidate, problem.challenge)
    if not ok:
        return GuardResult(False, tuple(errors), 0)

    try:
        _challenge_pre, challenge_blocks = split_declarations(problem.challenge)
        challenge_decl_names = {
            info[1]
            for block in challenge_blocks
            if (info := _info(block)) is not None
        }
    except Exception:
        challenge_decl_names = set()

    answer_defs, numeric_set = resolve_answer_definition_names(
        problem, challenge_decl_names=challenge_decl_names
    )
    numeric_names = tuple(sorted(numeric_set))
    numeric_ok, numeric_errors = numeric_answers_are_literals(candidate, numeric_names)
    if not numeric_ok:
        return GuardResult(False, tuple(numeric_errors), 0)

    nonnumeric = answer_defs - numeric_set
    if not nonnumeric:
        return GuardResult(True)

    try:
        preamble, blocks = split_declarations(candidate)
    except Exception as exc:
        return GuardResult(False, (f"cannot inspect answer definitions: {exc}",), 0)

    by_name = {
        info[1]: block
        for block in blocks
        if (info := _info(block)) is not None
    }
    theorem_blocks = [
        block
        for block in blocks
        if (info := _info(block)) is not None and info[0] in {"theorem", "lemma"}
    ]
    lean_checks = 0
    for name in sorted(nonnumeric):
        definition = by_name.get(name)
        if definition is None:
            return GuardResult(False, (f"missing answer definition `{name}`",), lean_checks)

        # Cheap structural reject first (no Lean) — catches empty-manifest Putnam.
        structural = structurally_circular_definition(
            name, definition, theorem_blocks
        )
        if structural is not None:
            return GuardResult(False, (structural,), lean_checks)

        circular, checks = await definition_is_circular(
            services,
            preamble=preamble,
            context_blocks=blocks,
            definition_block=definition,
            dependent_blocks=theorem_blocks,
            timeout_s=timeout_s,
        )
        lean_checks += checks
        if circular:
            return GuardResult(
                False,
                (
                    f"definition `{name}` makes its characterisation theorem "
                    "definitional/tautological; return a closed canonical answer",
                ),
                lean_checks,
            )
    return GuardResult(True, (), lean_checks)
