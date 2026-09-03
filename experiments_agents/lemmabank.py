"""Cross-slot verified-lemma bank over multi-theorem (universal path to p09).

Observation (2026-08-27): p09_b's solved proof contains the exact periodicity `have`
(`2^n%7 = 2^(n%3)%7`) that p09_a's crux needs; p09_a fails only on assembling/naming
it. So: solve slots independently (pass 1), harvest the verified `have` blocks from
whatever solved, then RE-solve the still-unsolved slots (pass 2) with those verified
facts offered in the prompt. Universal — facts are indexed by their statement text,
triggered by "a sibling slot proved something", never by problem id or category.

Two passes over a fresh inner agent per slot (nearmiss-wrapped tactic repair). Never
below baseline (whole-file fallback if not all slots solve).
"""

from __future__ import annotations

from typing import Callable

from re_harness import Agent, AgentResult, Problem, Services

from .common import integrity_check, required_decl_names
from .multitheorem import (
    split_declarations, _block_has_sorry, _preamble_lines, _merge_preambles,
)
from .nearmiss import extract_verified_have_texts


class LemmaBankAgent:
    def __init__(self, *, arm: str, make_inner: Callable[[], Agent], max_bank: int = 8):
        self.arm = arm
        self.make_inner = make_inner
        self.max_bank = max_bank

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        challenge = problem.challenge
        pre, blocks = split_declarations(challenge)
        prov_idx = [i for i, b in enumerate(blocks) if _block_has_sorry(b)]
        if len(prov_idx) <= 1:
            return self._tag(await self.make_inner().solve(problem, services), "single")

        cq = cg = lc = 0
        sol: dict[int, str] = {}
        done: dict[int, bool] = {}

        # ---- pass 1: independent per-slot ----
        for i in prov_idx:
            r = await self._slot(services, problem, pre, blocks[i], extra="")
            sol[i], done[i] = r[0], r[1]
            cq += r[2]; cg += r[3]; lc += r[4]

        # ---- bank: verified have-blocks from solved slots ----
        bank: list[str] = []
        for i in prov_idx:
            if done[i]:
                for _stmt, block in extract_verified_have_texts(sol[i]):
                    if block not in bank:
                        bank.append(block)
        bank = bank[: self.max_bank]
        bank_text = ""
        if bank:
            bank_text = ("\n\nAlready-proven intermediate facts from a sibling theorem "
                         "(you MAY restate and reuse these verbatim as `have` steps):\n"
                         + "\n\n".join(bank))

        # ---- pass 2: retry unsolved slots with the bank ----
        if bank_text:
            for i in prov_idx:
                if done[i]:
                    continue
                r = await self._slot(services, problem, pre, blocks[i], extra=bank_text)
                cq += r[2]; cg += r[3]; lc += r[4]
                if r[1]:
                    sol[i], done[i] = r[0], True

        # ---- reassemble if every slot solved ----
        if all(done[i] for i in prov_idx):
            final = self._reassemble(pre, blocks, prov_idx, sol)
            check = await services.lean.check_file(final)
            lc += 1
            if check.accepted and integrity_check(final, challenge)[0]:
                return self._result(final, True, "lemma_bank_solved", cq, cg, lc, done)

        # ---- fallback ----
        res = await self.make_inner().solve(problem, services)
        md = res.metadata
        cq += int(md.get("calls_q", 0) or 0); cg += int(md.get("calls_g", 0) or 0)
        lc += int(md.get("lean_checks", 0) or 0)
        return self._result(res.solution, bool(md.get("accepted_by_repl")),
                            "lemma_bank_fallback", cq, cg, lc, done)

    async def _slot(self, services, problem, pre, block, *, extra):
        name = (required_decl_names(block) or ["?"])[0]
        imports = "\n".join(_preamble_lines(pre)) or "import Mathlib"
        mini = imports + "\n\n" + block.rstrip() + "\n"
        desc = (f"{problem.description}\n\n[Focus] Prove exactly `{name}` from a larger "
                f"challenge; keep its statement/name unchanged.{extra}")
        mp = Problem(id=f"{problem.id}::{name}", description=desc, challenge=mini,
                     metadata=dict(problem.metadata))
        res = await self.make_inner().solve(mp, services)
        md = res.metadata
        return (res.solution, bool(md.get("accepted_by_repl")),
                int(md.get("calls_q", 0) or 0), int(md.get("calls_g", 0) or 0),
                int(md.get("lean_checks", 0) or 0))

    def _reassemble(self, pre, blocks, prov_idx, sol):
        merged = _merge_preambles([pre] + [sol[i] for i in prov_idx])
        bodies = []
        for i, b in enumerate(blocks):
            if i in sol:
                _p, sb = split_declarations(sol[i])
                bodies.append("\n\n".join(x.rstrip() for x in sb) if sb else sol[i].rstrip())
            elif _block_has_sorry(b):
                bodies.append(b.rstrip())
            else:
                bodies.append(b.rstrip())
        return merged + "\n\n" + "\n\n".join(x for x in bodies if x.strip()) + "\n"

    def _tag(self, res, protocol):
        md = dict(res.metadata); md["lemma_bank_stage"] = protocol
        return AgentResult(res.solution, md)

    def _result(self, solution, accepted, stop, cq, cg, lc, done):
        return AgentResult(solution, {
            "arm": self.arm, "protocol": "lemma_bank", "accepted_by_repl": accepted,
            "stop_reason": stop, "calls_q": cq, "calls_g": cg, "lean_checks": lc,
            "slots_solved": sum(1 for v in done.values() if v), "n_slots": len(done),
        })


def make_lemma_bank(*, arm: str, make_inner: Callable[[], Agent]) -> LemmaBankAgent:
    return LemmaBankAgent(arm=arm, make_inner=make_inner)
