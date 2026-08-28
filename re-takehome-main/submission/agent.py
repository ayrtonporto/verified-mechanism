"""Submission agent — a universal, budget-aware escalation ladder.

The judge runs THIS agent on a private holdout (~a dozen problems, same format as
`sample-problems`), one problem at a time, under a $1 and 8 h wall-clock cap, and scores a
point iff the Lean comparator accepts the returned file. So the agent must be *universal*
(no per-problem or per-category routing — the verifier is the only "difficulty classifier")
and must spend the ample budget headroom on the hard problems while returning instantly on
the easy ones.

Design: escalate cheap → aggressive and stop the moment the REPL accepts an
integrity-preserving file. The two fixed models collaborate throughout — GPT-OSS plans /
proves the hard steps, Qwen formalizes cheaply, and NearMiss rescues near-misses:

  T0  zero-model tactic-battery sweep on the whole problem (incl. `grind`).
  ──  split into theorem slots (breaks a conjunction so slots needn't be clean together).
  T1  per slot: cheap tactic sweep, then one Qwen HintedProver sample.
  T2  per slot: a concurrent batch of HintedProver samples (GPT-OSS proves with the
      cast-ℤ + `nlinarith [hints]` + squeeze idiom; G-plans-Q-formalizes; Qwen), model
      calls overlapping over one serial Lean container; NearMiss rescue on near-misses.
  T3  per slot: a larger sample batch if budget/time remain.
  ──  combine slot winners, final REPL check + integrity, checkpoint, return.

Every tier is problem-agnostic. Nothing here inspects the problem id or a hand-labelled
category; triggers look only at the goal/error shape via Lean diagnostics. No proof is
hardcoded and no `native_decide` (the comparator rejects `Lean.ofReduceBool`).
"""

from __future__ import annotations

import asyncio
import os
import time

from re_harness import AgentResult, MODEL_A, MODEL_B, Problem, Services

from experiments_agents.common import (
    SWEEP_CHECK_TIMEOUT_S,
    integrity_check,
    required_decl_names,
    tactic_sweep_variants,
)
from experiments_agents.hintedprover import HintedProver
from experiments_agents.nearmiss import rescue
from experiments_agents.multitheorem import (
    split_declarations,
    _block_has_sorry,
    _merge_preambles,
    _preamble_lines,
)

QWEN, GPT_OSS = MODEL_A, MODEL_B

# Soft wall-clock reserve: stop STARTING new work this many seconds before the hard cap so
# the outer runner keeps the last checkpoint instead of killing mid-check.
_RESERVE_S = 240
_HARD_CAP_S = 8 * 3600


def _time_budget_s() -> float:
    raw = os.environ.get("VM_TIME_LIMIT_S", "").strip()
    try:
        cap = float(raw) if raw else _HARD_CAP_S
    except ValueError:
        cap = _HARD_CAP_S
    return max(600.0, min(cap, _HARD_CAP_S) - _RESERVE_S)


def _accepted(check, cand: str, challenge: str) -> bool:
    return (
        check.accepted
        and not check.has_sorry
        and not check.timed_out
        and integrity_check(cand, challenge)[0]
    )


def _n_errors(check) -> int:
    return sum(1 for m in check.messages if m.get("severity") == "error")


def _dedup_decls(source: str) -> str:
    """Drop duplicate top-level declarations, keeping the FIRST of each name.

    When a problem's answer `def`/`abbrev` and its theorem are solved in separate slots,
    the theorem slot re-declares the answer to make its file self-contained; merging then
    produces the SAME name twice (`abbrev p06_answer := 49` + `def p06_answer := 49`),
    which Lean rejects. Values agree (both slots read the same challenge), so keeping the
    first declaration per name yields a valid file. Universal and structural — no problem
    identity, no answer knowledge."""
    try:
        pre, blocks = split_declarations(source)
    except Exception:
        return source
    seen: set[str] = set()
    kept: list[str] = []
    for b in blocks:
        names = required_decl_names(b)
        primary = names[0] if names else None
        if primary and primary in seen:
            continue
        if primary:
            seen.add(primary)
        kept.append(b.rstrip())
    if not kept:
        return source
    return pre.rstrip() + "\n\n" + "\n\n".join(kept) + "\n"


class SubmissionAgent:
    def __init__(
        self,
        *,
        check_timeout_s: int = 150,
        t2_batch: int = 4,
        t3_batch: int = 6,
        slot_t2_batch: int = 6,
        slot_t3_batch: int = 10,
        min_slot_time_s: float = 600.0,
    ):
        self.check_timeout_s = check_timeout_s
        self.t2_batch = t2_batch
        self.t3_batch = t3_batch
        # heavier per-slot budgets for the multi-theorem split path, where a hard slot
        # (e.g. p09_a's periodicity) needs enough independent samples to hit its low rate.
        self.slot_t2_batch = slot_t2_batch
        self.slot_t3_batch = slot_t3_batch
        self.min_slot_time_s = min_slot_time_s

    # ----- helpers -----
    async def _check(self, services: Services, src: str, *, timeout_s: int | None = None):
        return await services.lean.check_file(src, timeout_s=timeout_s or self.check_timeout_s)

    async def _sweep(self, services: Services, challenge: str, time_left, *, tag: str):
        """Zero-model tactic-battery sweep; returns accepted source or None."""
        for tac, variant in tactic_sweep_variants(challenge):
            if time_left() < 90:
                return None
            try:
                c = await self._check(services, variant, timeout_s=SWEEP_CHECK_TIMEOUT_S)
            except Exception:
                continue
            if _accepted(c, variant, challenge):
                return variant
        return None

    def _batch_configs(self, n: int) -> list:
        """A diverse batch mixing the two proof idioms so the ladder covers both a
        modular/number-theory problem (nm_pf: plan→formalize + tactic battery + NearMiss —
        the p09 winner) and an arithmetic/Diophantine one (HintedProver: cast-ℤ +
        `nlinarith [hints]` + squeeze). Both models collaborate throughout."""
        try:
            from experiments_agents.nm_pf import create_agent as _nm_pf
        except Exception:
            _nm_pf = None
        _nm = _nm_pf or (lambda: HintedProver(arm="HP-GP", prove_model=GPT_OSS,
                                              planner_model=GPT_OSS, turns=3))
        factories = [
            _nm,                                                                # nm_pf
            lambda: HintedProver(arm="HP-G", prove_model=GPT_OSS, turns=3),
            _nm,                                                                # nm_pf
            lambda: HintedProver(arm="HP-GP", prove_model=GPT_OSS, planner_model=GPT_OSS, turns=3),
            _nm,                                                                # nm_pf
            lambda: HintedProver(arm="HP-PF", prove_model=QWEN, planner_model=GPT_OSS, turns=3),
        ]
        return [factories[i % len(factories)]() for i in range(n)]

    async def _sample_batch(self, prob: Problem, services: Services, n: int):
        """Run n HintedProver samples concurrently; model calls overlap, Lean checks
        serialise through the shared client. Return (accepted_src|None, best_near_miss)."""
        async def one(agent):
            try:
                return await agent.solve(prob, services)
            except Exception:
                return None

        results = await asyncio.gather(*(one(a) for a in self._batch_configs(n)))
        best_near = None
        best_errs = 10_000
        for res in results:
            if res is None:
                continue
            if res.metadata.get("accepted_by_repl") and integrity_check(res.solution, prob.challenge)[0]:
                return res.solution, None
            # HintedProver reports its lowest-error candidate + residual error count, so we
            # pick the best near-miss without spending extra (serial) Lean checks here.
            src = res.solution
            e = int(res.metadata.get("residual_errors", 9999))
            if src and src != prob.challenge and e < best_errs:
                best_errs, best_near = e, src
        return None, (best_near if best_errs <= 4 else None)

    async def _solve_slot(self, prob: Problem, services: Services, time_left,
                          *, t2: int | None = None, t3: int | None = None) -> str | None:
        """Escalate on one theorem slot until accepted or budget/time exhausted."""
        challenge = prob.challenge
        t2 = self.t2_batch if t2 is None else t2
        t3 = self.t3_batch if t3 is None else t3
        # T1a: per-slot tactic sweep (cheap)
        got = await self._sweep(services, challenge, time_left, tag="slot")
        if got:
            return got
        # T1b: one cheap Qwen sample
        if time_left() > self.min_slot_time_s:
            got, near = await self._sample_batch(prob, services, 1)
            if got:
                return got
        # T2: concurrent diverse batch
        near_all = None
        if time_left() > self.min_slot_time_s:
            got, near = await self._sample_batch(prob, services, t2)
            if got:
                return got
            near_all = near
        # T3: larger batch if budget/time remain
        if time_left() > self.min_slot_time_s:
            got, near = await self._sample_batch(prob, services, t3)
            if got:
                return got
            near_all = near or near_all
        # final NearMiss rescue on the best near-miss we saw
        if near_all is not None and time_left() > 180:
            try:
                r = await rescue(services, near_all, timeout_s=75,
                                 integrity=integrity_check, challenge=challenge)
            except Exception:
                r = None
            if r is not None:
                return r
        return None

    # ----- entry point -----
    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        start = time.monotonic()
        budget = _time_budget_s()

        def time_left() -> float:
            return budget - (time.monotonic() - start)

        # T0: whole-problem zero-model sweep (catches the easy problems for free)
        got = await self._sweep(services, problem.challenge, time_left, tag="whole")
        if got:
            services.checkpoint(got, {"tier": "T0"})
            return AgentResult(got, {"tier": "T0_sweep", "accepted_by_repl": True})

        # Inspect structure.
        try:
            pre, blocks = split_declarations(problem.challenge)
            prov = [b for b in blocks if _block_has_sorry(b)]
            imports = "\n".join(_preamble_lines(pre)) or "import Mathlib"
        except Exception:
            pre, prov, imports = "", [], "import Mathlib"

        # SINGLE-DECLARATION: prove the whole file directly.
        if len(prov) < 2:
            whole = await self._solve_slot(problem, services, time_left)
            if whole:
                services.checkpoint(whole, {"tier": "whole"})
                return AgentResult(whole, {"tier": "whole", "accepted_by_repl": True})
            return AgentResult(problem.challenge, {"tier": "exhausted"})

        # MULTI-DECLARATION: solve each slot as a self-contained file (the models prove far
        # better with a complete file than with a headless fragment), combine the winners,
        # then DE-DUPLICATE — the theorem slot re-declares the answer to compile, so the
        # merge would otherwise carry the same name twice. Handles both dependent
        # (answer+theorem) and independent (p09's two theorems) multi-decl problems.
        winners: dict[str, str] = {}
        slot_names: list[str] = []
        for block in prov:
            name = (required_decl_names(block)[:1] or ["_"])[0]
            slot_names.append(name)
            mini = imports + "\n\n" + block.rstrip() + "\n"
            miniprob = Problem(
                id=f"{problem.id}::{name}",
                description=f"{problem.description}\n\n[Focus] Prove exactly `{name}`.",
                challenge=mini,
                metadata=dict(problem.metadata),
            )
            if time_left() < self.min_slot_time_s:
                break
            sol = await self._solve_slot(miniprob, services, time_left,
                                         t2=self.slot_t2_batch, t3=self.slot_t3_batch)
            if sol:
                winners[name] = sol
                services.checkpoint(sol, {"tier": "slot", "slot": name})

        if slot_names and all(n in winners for n in slot_names):
            merged = _merge_preambles([pre] + [winners[n] for n in slot_names])
            bodies = []
            for n in slot_names:
                _p, sb = split_declarations(winners[n])
                bodies.append("\n\n".join(x.rstrip() for x in sb) if sb else winners[n])
            final = _dedup_decls(merged + "\n\n" + "\n\n".join(bodies) + "\n")
            try:
                c = await self._check(services, final, timeout_s=180)
            except Exception:
                c = None
            if c is not None and _accepted(c, final, problem.challenge):
                services.checkpoint(final, {"tier": "combined", "slots": slot_names})
                return AgentResult(final, {"tier": "combined", "slots": slot_names,
                                           "accepted_by_repl": True})
            services.checkpoint(final, {"tier": "combined_unverified"})

        # LAST RESORT: some slots unsolved (or combine failed) — try the whole file in one
        # shot (may catch what the split missed).
        if time_left() > self.min_slot_time_s:
            whole = await self._solve_slot(problem, services, time_left)
            if whole:
                services.checkpoint(whole, {"tier": "whole_fallback"})
                return AgentResult(whole, {"tier": "whole_fallback", "accepted_by_repl": True})

        if winners:
            any_src = _dedup_decls(next(iter(winners.values())))
            services.checkpoint(any_src, {"tier": "partial"})
            return AgentResult(any_src, {"tier": "partial", "solved_slots": list(winners)})
        return AgentResult(problem.challenge, {"tier": "exhausted"})


def create_agent() -> SubmissionAgent:
    return SubmissionAgent()
