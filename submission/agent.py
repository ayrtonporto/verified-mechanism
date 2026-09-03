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
  T1c per slot: BridgePortfolio generates diverse milestone routes, Lean-validates the
      bridge before proving any milestone, ranks the viable routes, and recursively
      decomposes the first blocked milestone (depth <= 2).
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
import re
import time
from typing import Any, Callable

from re_harness import AgentResult, MODEL_A, MODEL_B, Problem, Services

from experiments_agents.common import (
    SWEEP_CHECK_TIMEOUT_S,
    env_float,
    env_int,
    integrity_check,
    required_decl_names,
    strict_integrity_check,
    tactic_sweep_variants,
)
from experiments_agents.hintedprover import HintedProver
from experiments_agents.bridgeportfolio import BridgePortfolioAgent
from experiments_agents.candidate_guard import GuardResult, validate_solution_candidate
from experiments_agents.programportfolio import ProgramPortfolioAgent
from experiments_agents.repair import TargetedRepairAgent
from experiments_agents.verified_progress import VerifiedProgressGraph
from experiments_agents.error_router import (
    classify_failure_text,
    preferred_residual_mode,
    problem_looks_answer_shaped,
)
from experiments_agents.nearmiss import rescue
from experiments_agents.residual_hygiene import (
    FailedAttemptNotebook,
    build_fail_telemetry,
    locked_goal_text,
    manifest_answer_names,
    promote_goal_shaped_from_text,
)
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
# Default experiment window stays modest so the historical ladder keeps priority in
# ordinary runs.  Long Putnam-style jobs should raise SUBMISSION_EXPERIMENTAL_CAP_S and
# optionally lower the champion/fallback caps so residual time actually reaches Program.
_EXPERIMENTAL_CAP_S = 45 * 60
_DEFAULT_MIN_SLOT_TIME_S = 600.0
# 0 = uncapped (legacy behaviour).  Positive values reserve wall for later stages.
_DEFAULT_CHAMPION_CAP_S = 0.0
_DEFAULT_FALLBACK_CAP_S = 0.0


class StageWindow:
    """A monotonic sub-deadline which can never exceed the enclosing time budget."""

    def __init__(self, time_left: Callable[[], float], allowance_s: float):
        self._outer = time_left
        self._started = time.monotonic()
        self.allowance_s = max(0.0, allowance_s)

    def __call__(self) -> float:
        return min(self._outer(), self.allowance_s - (time.monotonic() - self._started))


def _time_budget_s() -> float:
    raw = os.environ.get("VM_TIME_LIMIT_S", "").strip()
    try:
        cap = float(raw) if raw else _HARD_CAP_S
    except ValueError:
        cap = _HARD_CAP_S
    return max(600.0, min(cap, _HARD_CAP_S) - _RESERVE_S)


def _accepted(check, cand: str, challenge: str, *, strict: bool = False) -> bool:
    integrity = strict_integrity_check if strict else integrity_check
    return (
        check.accepted
        and not check.has_sorry
        and not check.timed_out
        and integrity(cand, challenge)[0]
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


def _locked_slot_body(
    original_block: str, candidate: str, challenge_names: set[str]
) -> str | None:
    """Graft a verified slot RHS under the machine-owned original declaration header.

    A dependent mini-challenge may prompt a model to unfold a sibling answer in the
    theorem statement.  That file can elaborate, but Comparator correctly rejects the
    changed exported type.  Keep only non-challenge helper declarations from the slot and
    replace the original block's RHS/proof; declarations owned by the challenge always
    retain their exact original prefix through ``:=``.
    """

    target_names = required_decl_names(original_block)
    if not target_names:
        return None
    target = target_names[0]
    _candidate_preamble, candidate_blocks = split_declarations(candidate)
    target_block: str | None = None
    helpers: list[str] = []
    for block in candidate_blocks:
        names = required_decl_names(block)
        name = names[0] if names else None
        if name == target and target_block is None:
            target_block = block
        elif name is not None and name not in challenge_names:
            helpers.append(block.rstrip())
    if target_block is None:
        return None
    original_rhs = original_block.find(":=")
    candidate_rhs = target_block.find(":=")
    if original_rhs < 0 or candidate_rhs < 0:
        return None
    locked = (
        original_block[: original_rhs + 2]
        + target_block[candidate_rhs + 2 :].rstrip()
    )
    return "\n\n".join([*helpers, locked.rstrip()])


class SubmissionAgent:
    def __init__(
        self,
        *,
        check_timeout_s: int = 150,
        t2_batch: int = 4,
        t3_batch: int = 6,
        slot_t2_batch: int = 6,
        slot_t3_batch: int = 10,
        min_slot_time_s: float | None = None,
        experimental_cap_s: float | None = None,
        champion_cap_s: float | None = None,
        fallback_cap_s: float | None = None,
        champion_factories: list[tuple[str, Callable[[], Any]]] | None = None,
        program_factory: Callable[..., Any] | None = None,
    ):
        self.check_timeout_s = check_timeout_s
        self.t2_batch = t2_batch
        self.t3_batch = t3_batch
        # heavier per-slot budgets for the multi-theorem split path, where a hard slot
        # (e.g. p09_a's periodicity) needs enough independent samples to hit its low rate.
        self.slot_t2_batch = slot_t2_batch
        self.slot_t3_batch = slot_t3_batch
        self.min_slot_time_s = (
            float(min_slot_time_s)
            if min_slot_time_s is not None
            else env_float(
                "SUBMISSION_MIN_SLOT_TIME_S",
                _DEFAULT_MIN_SLOT_TIME_S,
                minimum=0.0,
                maximum=3600.0,
            )
        )
        self.experimental_cap_s = (
            float(experimental_cap_s)
            if experimental_cap_s is not None
            else env_float(
                "SUBMISSION_EXPERIMENTAL_CAP_S",
                float(_EXPERIMENTAL_CAP_S),
                minimum=60.0,
                maximum=float(_HARD_CAP_S),
            )
        )
        self.champion_cap_s = (
            float(champion_cap_s)
            if champion_cap_s is not None
            else env_float(
                "SUBMISSION_CHAMPION_CAP_S",
                _DEFAULT_CHAMPION_CAP_S,
                minimum=0.0,
                maximum=float(_HARD_CAP_S),
            )
        )
        self.fallback_cap_s = (
            float(fallback_cap_s)
            if fallback_cap_s is not None
            else env_float(
                "SUBMISSION_FALLBACK_CAP_S",
                _DEFAULT_FALLBACK_CAP_S,
                minimum=0.0,
                maximum=float(_HARD_CAP_S),
            )
        )
        self.champion_factories = champion_factories
        self.program_factory = program_factory
        self._progress_graph = VerifiedProgressGraph()
        self._stage_reports: list[dict[str, Any]] = []
        self._lab_notebook = FailedAttemptNotebook()
        self._extracts_promoted = 0
        self._greedy_close_attempted = 0
        self._residual_rounds_ran = 0
        self._residual_stall_reason = ""
        self._last_residual_detail = ""
        self._residual_fail_kind = "other"
        self._residual_route_mode = "either"

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

    @staticmethod
    def _inner_services(services: Services) -> Services:
        # Inner agents may checkpoint syntactically valid near-misses. The production
        # policy checkpoints only complete, substantive candidates.
        return Services(llm=services.llm, lean=services.lean, checkpoint=lambda *_a, **_k: None)

    async def _guard_candidate(
        self, problem: Problem, services: Services, candidate: str
    ) -> GuardResult:
        return await validate_solution_candidate(problem, services, candidate)

    def _record_stage(
        self,
        name: str,
        started: float,
        *,
        result: AgentResult | None = None,
        substantive: bool = False,
        detail: str = "",
    ) -> None:
        metadata = dict(result.metadata) if result is not None else {}
        self._stage_reports.append({
            "stage": name,
            "wall_s": round(time.monotonic() - started, 3),
            "accepted_by_repl": bool(metadata.get("accepted_by_repl")),
            "substantive": substantive,
            "calls_q": int(metadata.get("calls_q", 0) or 0),
            "calls_g": int(metadata.get("calls_g", 0) or 0),
            "lean_checks": int(metadata.get("lean_checks", 0) or 0),
            "detail": detail,
        })

    def _default_champions(self) -> list[tuple[str, Callable[[], Any]]]:
        return [
            (
                "champion_r_q",
                lambda: TargetedRepairAgent(
                    arm="R-Q-CHAMPION",
                    propose_model=QWEN,
                    repair_model=QWEN,
                    solution_guard=validate_solution_candidate,
                ),
            ),
            (
                "champion_r_g",
                lambda: TargetedRepairAgent(
                    arm="R-G-CHAMPION",
                    propose_model=GPT_OSS,
                    repair_model=GPT_OSS,
                    solution_guard=validate_solution_candidate,
                ),
            ),
        ]

    async def _run_champion_portfolio(
        self,
        problem: Problem,
        services: Services,
        time_left: Callable[[], float],
    ) -> tuple[str | None, str | None]:
        """Run the exact same-model repair mechanisms which formed the old 6/9 union."""

        factories = self.champion_factories or self._default_champions()
        failed_candidates: dict[str, str] = {}
        # Optional hard wall for the whole champion+handoff block so long jobs can
        # reserve residual time for Program/Bridge instead of burning it on R/H.
        champion_time = (
            StageWindow(time_left, self.champion_cap_s)
            if self.champion_cap_s > 0
            else time_left
        )
        for stage, factory in factories:
            if champion_time() <= self.min_slot_time_s:
                break
            started = time.monotonic()
            try:
                result = await factory().solve(problem, self._inner_services(services))
            except Exception as exc:
                self._record_stage(stage, started, detail=f"error:{type(exc).__name__}")
                continue
            substantive = False
            detail = ""
            if result.metadata.get("accepted_by_repl"):
                guard = await self._guard_candidate(problem, services, result.solution)
                substantive = guard.accepted
                detail = "; ".join(guard.errors)
            self._record_stage(
                stage, started, result=result, substantive=substantive, detail=detail
            )
            if substantive:
                return result.solution, stage
            if result.solution and result.solution != problem.challenge:
                failed_candidates[stage] = result.solution

        # Additive cross-model handoff: the exact historical R-Q and R-G arms above keep
        # their full 1+3 turns.  Only after both miss, repair their best verified
        # near-candidates with the other model instead of discarding all accumulated Lean
        # diagnostics and restarting from the original challenge yet again.
        if self.champion_factories is None:
            handoffs = [
                ("additive_handoff_q_to_g", "champion_r_q", QWEN, GPT_OSS),
                ("additive_handoff_g_to_q", "champion_r_g", GPT_OSS, QWEN),
            ]
            for stage, source_stage, propose_model, repair_model in handoffs:
                seed = failed_candidates.get(source_stage)
                if seed is None or champion_time() <= self.min_slot_time_s:
                    continue
                started = time.monotonic()
                agent = TargetedRepairAgent(
                    arm=stage.upper(),
                    propose_model=propose_model,
                    repair_model=repair_model,
                    max_repair_turns=3,
                    solution_guard=validate_solution_candidate,
                    initial_candidate=seed,
                )
                try:
                    result = await agent.solve(
                        problem, self._inner_services(services)
                    )
                except Exception as exc:
                    self._record_stage(
                        stage, started, detail=f"error:{type(exc).__name__}"
                    )
                    continue
                substantive = False
                detail = ""
                if result.metadata.get("accepted_by_repl"):
                    guard = await self._guard_candidate(
                        problem, services, result.solution
                    )
                    substantive = guard.accepted
                    detail = "; ".join(guard.errors)
                self._record_stage(
                    stage,
                    started,
                    result=result,
                    substantive=substantive,
                    detail=detail,
                )
                if substantive:
                    return result.solution, stage
        return None, None

    async def _experimental_bridge(
        self,
        problem: Problem,
        services: Services,
        time_left: Callable[[], float],
        *,
        stage: str,
        max_depth: int | None = None,
        search_waves: int | None = None,
        portfolio_calls: int | None = None,
        min_time_s: float = 60.0,
        arm: str = "VPG-BP-GQ",
        lab_notebook: str = "",
    ) -> str | None:
        started = time.monotonic()
        try:
            bridge_kwargs: dict[str, Any] = {
                "arm": arm,
                "time_left": time_left,
                "min_time_s": min_time_s,
                "progress_graph": self._progress_graph,
                "lab_notebook": lab_notebook,
            }
            if max_depth is not None:
                bridge_kwargs["max_depth"] = max_depth
            if search_waves is not None:
                bridge_kwargs["search_waves"] = search_waves
            if portfolio_calls is not None:
                bridge_kwargs["portfolio_calls"] = portfolio_calls
            bridge = BridgePortfolioAgent(**bridge_kwargs)
            result = await bridge.solve(problem, self._inner_services(services))
        except Exception as exc:
            self._record_stage(stage, started, detail=f"error:{type(exc).__name__}")
            return None
        substantive = False
        detail = ""
        if result.metadata.get("accepted_by_repl"):
            guard = await self._guard_candidate(problem, services, result.solution)
            substantive = guard.accepted
            detail = "; ".join(guard.errors)
        else:
            detail = str(result.metadata.get("stop_reason") or "bridge_no_accept")
            # Near-miss harvest: only when the returned source still carries Lean-clean
            # `have` blocks (Bridge may return challenge on hard fail — then no-op).
            try:
                src = result.solution or ""
                if src and src != problem.challenge:
                    self._extracts_promoted += promote_goal_shaped_from_text(
                        self._progress_graph,
                        source=src,
                        goal_text=locked_goal_text(problem.challenge),
                        context=problem.challenge,
                        answer_names=manifest_answer_names(problem),
                        lean_accepted=True,
                        provenance={"stage": stage, "kind": "near_miss_text"},
                    )
            except Exception:
                pass
        self._record_stage(stage, started, result=result, substantive=substantive, detail=detail)
        return result.solution if substantive else None

    async def _greedy_bank_close(
        self,
        problem: Problem,
        services: Services,
        time_left: Callable[[], float],
        *,
        stage: str,
    ) -> str | None:
        """Mandatory no-LLM full-bank close at residual round end (P0.5)."""

        self._greedy_close_attempted += 1
        started = time.monotonic()
        if time_left() < 25:
            self._record_stage(stage, started, detail="greedy_skipped_low_time")
            return None
        try:
            bridge = BridgePortfolioAgent(
                arm="RESIDUAL-GREEDY-CLOSE",
                time_left=time_left,
                min_time_s=15.0,
                progress_graph=self._progress_graph,
                lab_notebook=self._lab_notebook.as_prompt_block(),
            )
            closed = await bridge.greedy_full_bank_close(
                problem, self._inner_services(services)
            )
        except Exception as exc:
            self._record_stage(
                stage, started, detail=f"greedy_error:{type(exc).__name__}"
            )
            return None
        if closed is None:
            self._record_stage(stage, started, detail="greedy_no_accept")
            return None
        guard = await self._guard_candidate(problem, services, closed)
        self._record_stage(
            stage,
            started,
            substantive=guard.accepted,
            detail="; ".join(guard.errors) or "greedy_accept",
        )
        return closed if guard.accepted else None

    def _note_residual_fail(
        self,
        *,
        stage: str,
        detail: str,
        fail_kind: str,
        round_i: int,
    ) -> None:
        """Append one English notebook bullet after a residual round miss."""

        kind = fail_kind or "other"
        short = re.sub(r"\s+", " ", (detail or "no_accept").strip())[:80]
        self._lab_notebook.add(
            f"r{round_i} {stage}: kind={kind}; {short or 'no_accept'}"
        )
        self._last_residual_detail = short or stage

    async def _residual_recursion(
        self,
        problem: Problem,
        services: Services,
        time_left: Callable[[], float],
        *,
        open_blocks: list[str],
    ) -> AgentResult | None:
        """Post-ladder residual: spend remaining wall on recursive lemma division.

        Keeps the cheap ladder intact.  Only runs when earlier stages failed and budget
        remains.  Bridge/Program keep the verified-lemma bank across route restarts;
        both models propose divisions; Lean validates bridges.

        Phase C + P0: outer rounds while wall remains; stall when bank/extract/notebook
        are flat *and* greedy full-bank close already tried.
        """

        if time_left() < 120:
            return None
        max_rounds = env_int("SUBMISSION_RESIDUAL_ROUNDS", 3, minimum=1, maximum=6)
        stall_limit = env_int("SUBMISSION_RESIDUAL_STALL", 2, minimum=1, maximum=4)
        depth = env_int("BP_MAX_DEPTH", 3, minimum=0, maximum=3)
        waves = env_int("BP_SEARCH_WAVES", 3, minimum=1, maximum=3)
        calls = env_int("BP_PORTFOLIO_CALLS", 4, minimum=1, maximum=4)

        # Phase D/E: route residual emphasis from prior stage details + answer shape
        # (no problem ids). Answer-shaped challenges prefer Program (defs first).
        prior_blob = " | ".join(
            f"{r.get('stage','')}:{r.get('detail','')}"
            for r in self._stage_reports[-8:]
            if isinstance(r, dict)
        )
        fail_kind = classify_failure_text(prior_blob)
        if problem_looks_answer_shaped(problem) and fail_kind == "other":
            fail_kind = "def_circular"  # gentle bias: try defs path first
        route_mode = preferred_residual_mode(fail_kind)
        answer_shaped = problem_looks_answer_shaped(problem)
        # Prefer program when multi-decl OR answer-shaped OR router says so.
        prefer_program = (
            len(open_blocks) >= 2
            or answer_shaped
            or route_mode == "program"
        )
        prefer_bridge = route_mode == "bridge" and not answer_shaped

        self._residual_fail_kind = fail_kind
        self._residual_route_mode = route_mode
        prev_nodes = len(self._progress_graph.nodes)
        prev_extracts = self._extracts_promoted
        stall_rounds = 0
        last_fail_detail = ""
        goal_text = locked_goal_text(problem.challenge)
        answer_names = manifest_answer_names(problem)

        for round_i in range(max_rounds):
            if time_left() < 120:
                break
            self._residual_rounds_ran = round_i + 1
            rounds_left = max(1, max_rounds - round_i)
            slice_s = max(180.0, time_left() / rounds_left)
            round_window = StageWindow(time_left, min(slice_s, max(0.0, time_left())))
            exp_started = time.monotonic()
            notebook_block = self._lab_notebook.as_prompt_block()
            # Alternate emphasis across rounds if "either".
            use_program = prefer_program
            if route_mode == "either" and not answer_shaped:
                use_program = (round_i % 2 == 0 and len(open_blocks) >= 2) or (
                    len(open_blocks) >= 2 and prefer_program
                )
            if prefer_bridge:
                use_program = False
            if answer_shaped or prefer_program and route_mode == "program":
                use_program = True
            # Multi-decl always can use program.
            if len(open_blocks) >= 2 and route_mode != "bridge":
                use_program = True
            if len(open_blocks) >= 2 and prefer_bridge and round_i > 0:
                # after a bridge-leaning round, allow program again
                use_program = round_i % 2 == 1

            round_won_source: str | None = None
            try:
                if use_program and (len(open_blocks) >= 2 or answer_shaped):

                    def theorem_factory(slot_time_left: Callable[[], float]):
                        return BridgePortfolioAgent(
                            arm="RESIDUAL-BP-DUAL",
                            time_left=slot_time_left,
                            min_time_s=30.0,
                            max_depth=depth,
                            search_waves=waves,
                            portfolio_calls=calls,
                            progress_graph=self._progress_graph,
                            lab_notebook=notebook_block,
                        )

                    program = ProgramPortfolioAgent(
                        time_left=round_window,
                        reserve_s=0,
                        progress_graph=self._progress_graph,
                        theorem_factory=theorem_factory,
                    )
                    result = await program.solve(
                        problem, self._inner_services(services)
                    )
                    stage = f"residual_recursion_program_r{round_i}"
                    guard = (
                        await self._guard_candidate(
                            problem, services, result.solution
                        )
                        if result.metadata.get("accepted_by_repl")
                        else GuardResult(False)
                    )
                    detail = "; ".join(guard.errors) or (
                        f"kind={fail_kind};nodes={len(self._progress_graph.nodes)};"
                        f"stop={result.metadata.get('stop_reason', '')}"
                    )
                    # Harvest goal-shaped haves even from non-accepting program attempts.
                    if not guard.accepted:
                        src = result.solution or ""
                        if src and src != problem.challenge:
                            self._extracts_promoted += promote_goal_shaped_from_text(
                                self._progress_graph,
                                source=src,
                                goal_text=goal_text,
                                context=problem.challenge,
                                answer_names=answer_names,
                                lean_accepted=True,
                                provenance={"stage": stage},
                            )
                    if not guard.accepted and guard.errors:
                        fail_kind = classify_failure_text(detail, fail_kind)
                        route_mode = preferred_residual_mode(fail_kind)
                        self._residual_fail_kind = fail_kind
                        self._residual_route_mode = route_mode
                    self._record_stage(
                        stage,
                        exp_started,
                        result=result,
                        substantive=guard.accepted,
                        detail=detail,
                    )
                    if guard.accepted:
                        round_won_source = result.solution
                    else:
                        last_fail_detail = detail or "program_no_accept"
                        self._note_residual_fail(
                            stage=stage,
                            detail=last_fail_detail,
                            fail_kind=fail_kind,
                            round_i=round_i,
                        )
                else:
                    stage = f"residual_recursion_bridge_r{round_i}"
                    source = await self._experimental_bridge(
                        problem,
                        services,
                        round_window,
                        stage=stage,
                        max_depth=depth,
                        search_waves=waves,
                        portfolio_calls=calls,
                        min_time_s=30.0,
                        arm="RESIDUAL-BP-DUAL",
                        lab_notebook=notebook_block,
                    )
                    if source is not None:
                        round_won_source = source
                    else:
                        last_fail_detail = f"bridge_no_accept;kind={fail_kind}"
                        self._note_residual_fail(
                            stage=stage,
                            detail=last_fail_detail,
                            fail_kind=fail_kind,
                            round_i=round_i,
                        )
            except Exception as exc:
                self._record_stage(
                    f"residual_recursion_r{round_i}",
                    exp_started,
                    detail=f"error:{type(exc).__name__};kind={fail_kind}",
                )
                last_fail_detail = f"error:{type(exc).__name__}"
                self._note_residual_fail(
                    stage=f"residual_recursion_r{round_i}",
                    detail=last_fail_detail,
                    fail_kind=fail_kind,
                    round_i=round_i,
                )

            if round_won_source is not None:
                md = {
                    "tier": f"residual_recursion_{'program' if use_program else 'bridge'}_r{round_i}",
                    "stage_winner": f"residual_recursion_{'program' if use_program else 'bridge'}_r{round_i}",
                    "accepted_by_repl": True,
                    "substantive_closure": True,
                    "residual_round": round_i,
                    "failure_kind": fail_kind,
                    "residual_route_mode": route_mode,
                    "stages": self._stage_reports,
                    "progress_graph": self._progress_graph.metadata(),
                    "extracts_promoted": self._extracts_promoted,
                    "greedy_close_attempted": self._greedy_close_attempted,
                    "notebook_size": self._lab_notebook.size(),
                }
                services.checkpoint(round_won_source, md)
                return AgentResult(round_won_source, md)

            # P0.5: mandatory greedy full-bank close once per residual round end.
            greedy = await self._greedy_bank_close(
                problem,
                services,
                round_window,
                stage=f"residual_greedy_close_r{round_i}",
            )
            if greedy is not None:
                md = {
                    "tier": f"residual_greedy_close_r{round_i}",
                    "stage_winner": f"residual_greedy_close_r{round_i}",
                    "accepted_by_repl": True,
                    "substantive_closure": True,
                    "residual_round": round_i,
                    "failure_kind": fail_kind,
                    "residual_route_mode": route_mode,
                    "stages": self._stage_reports,
                    "progress_graph": self._progress_graph.metadata(),
                    "extracts_promoted": self._extracts_promoted,
                    "greedy_close_attempted": self._greedy_close_attempted,
                    "notebook_size": self._lab_notebook.size(),
                }
                services.checkpoint(greedy, md)
                return AgentResult(greedy, md)

            # P0.6 smarter stall: bank flat AND no new extract AND greedy already tried.
            # Notebook bullets always append per-round labels; they do not alone
            # reset stall (otherwise residual never stalls while minting hollow facts).
            now_nodes = len(self._progress_graph.nodes)
            now_extracts = self._extracts_promoted
            bank_grew = now_nodes > prev_nodes
            extract_grew = now_extracts > prev_extracts
            if bank_grew or extract_grew:
                stall_rounds = 0
                prev_nodes = now_nodes
                prev_extracts = now_extracts
                continue
            stall_rounds += 1
            if stall_rounds >= stall_limit and self._greedy_close_attempted > 0:
                self._residual_stall_reason = (
                    f"stall={stall_rounds}; bank_flat; no_new_extract; "
                    f"notebook_size={self._lab_notebook.size()}; "
                    f"greedy_tried={self._greedy_close_attempted}; "
                    f"last={last_fail_detail}; nodes={now_nodes}; "
                    f"kind={fail_kind}; mode={route_mode}"
                )
                self._record_stage(
                    "residual_recursion_stall",
                    exp_started,
                    detail=self._residual_stall_reason,
                )
                break
            if stall_rounds >= stall_limit:
                # Greedy should have run; if somehow skipped, try once more then stop.
                if self._greedy_close_attempted == 0 and time_left() >= 25:
                    greedy = await self._greedy_bank_close(
                        problem,
                        services,
                        time_left,
                        stage="residual_greedy_close_pre_stall",
                    )
                    if greedy is not None:
                        md = {
                            "tier": "residual_greedy_close_pre_stall",
                            "stage_winner": "residual_greedy_close_pre_stall",
                            "accepted_by_repl": True,
                            "substantive_closure": True,
                            "residual_round": round_i,
                            "failure_kind": fail_kind,
                            "residual_route_mode": route_mode,
                            "stages": self._stage_reports,
                            "progress_graph": self._progress_graph.metadata(),
                            "extracts_promoted": self._extracts_promoted,
                            "greedy_close_attempted": self._greedy_close_attempted,
                            "notebook_size": self._lab_notebook.size(),
                        }
                        services.checkpoint(greedy, md)
                        return AgentResult(greedy, md)
                self._residual_stall_reason = (
                    f"stall={stall_rounds}; bank_flat; greedy_tried="
                    f"{self._greedy_close_attempted}; last={last_fail_detail}"
                )
                self._record_stage(
                    "residual_recursion_stall",
                    exp_started,
                    detail=self._residual_stall_reason,
                )
                break

        return None

    async def _solve_slot(self, prob: Problem, services: Services, time_left,
                          *, t2: int | None = None, t3: int | None = None,
                          allow_experimental: bool = False) -> str | None:
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
        # T1c: on goals that survive the cheap direct attempts, switch from whole-proof
        # sampling to bridge-first decomposition.  The portfolio agent validates that a
        # route's milestones really imply the locked goal *before* proving them, ranks
        # only verified routes, and recursively decomposes the first blocked milestone.
        # It owns neither the theorem header nor checkpoints for internal lemma probes,
        # so no repair can silently change the task and a timeout cannot preserve an
        # altered subgoal as the submission.
        if allow_experimental and time_left() > max(self.min_slot_time_s, 900.0):
            got = await self._experimental_bridge(
                prob, services, time_left, stage="verified_progress_bridge_slot"
            )
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
    async def _solve_regressed_legacy_order(
        self, problem: Problem, services: Services
    ) -> AgentResult:
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

        # DEPENDENT MULTI-DECLARATION: definitions/answers must be fixed before the
        # theorems that mention them. ProgramPortfolio branches over Lean-valid
        # definition candidates, proves theorem slots with BridgePortfolio in that
        # immutable context, and retries missed parts after a sibling is solved. Keep
        # the older independent-slot ladder below as a fallback, so this integration
        # can add capability without erasing the established search paths.
        if len(prov) >= 2 and time_left() > max(self.min_slot_time_s, 900.0):
            try:
                program = ProgramPortfolioAgent(time_left=time_left, reserve_s=0)
                program_result = await program.solve(problem, services)
            except Exception:
                program_result = None
            if (
                program_result is not None
                and program_result.metadata.get("accepted_by_repl")
                and integrity_check(program_result.solution, problem.challenge)[0]
            ):
                services.checkpoint(program_result.solution, {
                    "tier": "dependent_program",
                    "program": dict(program_result.metadata),
                })
                return AgentResult(program_result.solution, {
                    "tier": "dependent_program",
                    "accepted_by_repl": True,
                    "program": dict(program_result.metadata),
                })

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

    # Regression-first production ordering. The preceding helper retains the exact bad
    # ordering only as an auditable reference and is never called by the factory.
    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        started = time.monotonic()
        budget = _time_budget_s()
        self._progress_graph = VerifiedProgressGraph()
        self._stage_reports = []
        self._lab_notebook = FailedAttemptNotebook()
        self._extracts_promoted = 0
        self._greedy_close_attempted = 0
        self._residual_rounds_ran = 0
        self._residual_stall_reason = ""
        self._last_residual_detail = ""
        self._residual_fail_kind = "other"
        self._residual_route_mode = "either"

        def time_left() -> float:
            return budget - (time.monotonic() - started)

        def result_metadata(
            tier: str, *, winner: str = "", accepted: bool = False, **extra
        ) -> dict[str, Any]:
            return {
                "tier": tier,
                "stage_winner": winner,
                "accepted_by_repl": accepted,
                "substantive_closure": accepted,
                "stages": self._stage_reports,
                "progress_graph": self._progress_graph.metadata(),
                **extra,
            }

        def exhausted_metadata(**extra) -> dict[str, Any]:
            """Terminal FAIL telemetry (English keys) — always present on exhausted."""

            prior_blob = " | ".join(
                f"{r.get('stage','')}:{r.get('detail','')}"
                for r in self._stage_reports[-12:]
                if isinstance(r, dict)
            )
            fail_kind = self._residual_fail_kind or classify_failure_text(prior_blob)
            if problem_looks_answer_shaped(problem) and fail_kind == "other":
                fail_kind = "def_circular"
            route_mode = self._residual_route_mode or preferred_residual_mode(fail_kind)
            tel = build_fail_telemetry(
                failure_kind=fail_kind,
                residual_route_mode=route_mode,
                progress_graph=self._progress_graph,
                residual_rounds_ran=self._residual_rounds_ran,
                residual_stall_reason=self._residual_stall_reason,
                extracts_promoted=self._extracts_promoted,
                greedy_close_attempted=self._greedy_close_attempted,
                notebook_size=self._lab_notebook.size(),
                last_residual_detail=self._last_residual_detail or prior_blob[:200],
                stages=self._stage_reports,
            )
            md = result_metadata("exhausted", accepted=False, **tel)
            md.update(extra)
            return md

        async def finish(source: str, tier: str, **extra) -> AgentResult | None:
            guard = await self._guard_candidate(problem, services, source)
            if not guard.accepted:
                # Record final-guard rejection so residual routing / notebook see it.
                self._stage_reports.append({
                    "stage": f"final_guard_{tier}",
                    "wall_s": 0.0,
                    "accepted_by_repl": True,
                    "substantive": False,
                    "calls_q": 0,
                    "calls_g": 0,
                    "lean_checks": guard.lean_checks,
                    "detail": "; ".join(guard.errors),
                })
                self._last_residual_detail = "; ".join(guard.errors)[:200]
                self._lab_notebook.add(
                    f"final_guard reject {tier}: "
                    + ("; ".join(guard.errors)[:90] or "rejected")
                )
                return None
            md = result_metadata(tier, winner=tier, accepted=True, **extra)
            services.checkpoint(source, md)
            return AgentResult(source, md)

        # T0 remains the variance-proof zero-model floor.
        stage_started = time.monotonic()
        swept = await self._sweep(services, problem.challenge, time_left, tag="whole")
        if swept is not None:
            guard = await self._guard_candidate(problem, services, swept)
            self._stage_reports.append({
                "stage": "T0_sweep",
                "wall_s": round(time.monotonic() - stage_started, 3),
                "accepted_by_repl": True,
                "substantive": guard.accepted,
                "calls_q": 0,
                "calls_g": 0,
                "lean_checks": guard.lean_checks,
                "detail": "; ".join(guard.errors),
            })
            if guard.accepted:
                finished = await finish(swept, "T0_sweep")
                if finished is not None:
                    return finished

        # The exact historical same-model repair pair gets first claim on time and money.
        champion, champion_stage = await self._run_champion_portfolio(
            problem, services, time_left
        )
        if champion is not None and champion_stage is not None:
            # P0.1: never treat a stage-substantive champion as terminal success until
            # the final guard re-accepts. Answer-shaped false hopes fall through to residual.
            finished = await finish(
                champion, "historical_champion", champion_stage=champion_stage
            )
            if finished is not None:
                return finished
            # Rejected champion: continue ladder/residual (especially Putnam-class).
            self._extracts_promoted += promote_goal_shaped_from_text(
                self._progress_graph,
                source=champion,
                goal_text=locked_goal_text(problem.challenge),
                context=problem.challenge,
                answer_names=manifest_answer_names(problem),
                lean_accepted=True,  # stage already REPL-accepted; guard rejected shape
                provenance={"stage": "champion_rejected", "from": champion_stage},
            )

        try:
            preamble, blocks = split_declarations(problem.challenge)
            open_blocks = [block for block in blocks if _block_has_sorry(block)]
            imports = "\n".join(_preamble_lines(preamble)) or "import Mathlib"
        except Exception:
            preamble, open_blocks, imports = "", [], "import Mathlib"

        # The prior independent whole/slot ladder runs before ProgramPortfolio.  A
        # positive SUBMISSION_FALLBACK_CAP_S hard-stops this block so residual wall can
        # still reach the experiment on long jobs (0 keeps the legacy uncapped path).
        fallback_started = time.monotonic()
        fallback_time = (
            StageWindow(time_left, self.fallback_cap_s)
            if self.fallback_cap_s > 0
            else time_left
        )
        if len(open_blocks) < 2:
            whole = await self._solve_slot(
                problem, services, fallback_time, allow_experimental=False
            )
            guard = (
                await self._guard_candidate(problem, services, whole)
                if whole is not None
                else GuardResult(False)
            )
            self._stage_reports.append({
                "stage": "independent_whole_fallback",
                "wall_s": round(time.monotonic() - fallback_started, 3),
                "accepted_by_repl": whole is not None,
                "substantive": guard.accepted,
                "calls_q": 0,
                "calls_g": 0,
                "lean_checks": guard.lean_checks,
                "detail": "; ".join(guard.errors),
            })
            if whole is not None and guard.accepted:
                finished = await finish(whole, "independent_whole_fallback")
                if finished is not None:
                    return finished
        else:
            winners: dict[str, str] = {}
            slot_names: list[str] = []
            original_by_name: dict[str, str] = {}
            challenge_names = set(required_decl_names(problem.challenge))
            for block in open_blocks:
                name = (required_decl_names(block)[:1] or ["_"])[0]
                slot_names.append(name)
                original_by_name[name] = block
                mini = imports + "\n\n" + block.rstrip() + "\n"
                mini_problem = Problem(
                    id=f"{problem.id}::{name}",
                    description=f"{problem.description}\n\n[Focus] Prove exactly `{name}`.",
                    challenge=mini,
                    metadata=dict(problem.metadata),
                )
                if fallback_time() < self.min_slot_time_s:
                    break
                slot_solution = await self._solve_slot(
                    mini_problem,
                    services,
                    fallback_time,
                    t2=self.slot_t2_batch,
                    t3=self.slot_t3_batch,
                    allow_experimental=False,
                )
                if slot_solution is not None:
                    winners[name] = slot_solution

            if slot_names and all(name in winners for name in slot_names):
                merged = _merge_preambles(
                    [preamble] + [winners[name] for name in slot_names]
                )
                bodies: list[str] = []
                for name in slot_names:
                    locked = _locked_slot_body(
                        original_by_name[name], winners[name], challenge_names
                    )
                    if locked is None:
                        bodies = []
                        break
                    bodies.append(locked)
                combined = (
                    _dedup_decls(
                        merged + "\n\n" + "\n\n".join(bodies) + "\n"
                    )
                    if bodies
                    else ""
                )
                try:
                    combined_check = (
                        await self._check(services, combined, timeout_s=180)
                        if combined
                        else None
                    )
                except Exception:
                    combined_check = None
                if (
                    combined_check is not None
                    and _accepted(
                        combined_check, combined, problem.challenge, strict=True
                    )
                ):
                    guard = await self._guard_candidate(problem, services, combined)
                    if guard.accepted:
                        self._stage_reports.append({
                            "stage": "independent_slot_fallback",
                            "wall_s": round(time.monotonic() - fallback_started, 3),
                            "accepted_by_repl": True,
                            "substantive": True,
                            "calls_q": 0,
                            "calls_g": 0,
                            "lean_checks": guard.lean_checks,
                            "detail": "",
                        })
                        finished = await finish(
                            combined, "independent_slot_fallback", slots=slot_names
                        )
                        if finished is not None:
                            return finished

            whole = None
            if fallback_time() > self.min_slot_time_s:
                whole = await self._solve_slot(
                    problem, services, fallback_time, allow_experimental=False
                )
            guard = (
                await self._guard_candidate(problem, services, whole)
                if whole is not None
                else GuardResult(False)
            )
            self._stage_reports.append({
                "stage": "independent_slot_fallback",
                "wall_s": round(time.monotonic() - fallback_started, 3),
                "accepted_by_repl": whole is not None,
                "substantive": bool(whole is not None and guard.accepted),
                "calls_q": 0,
                "calls_g": 0,
                "lean_checks": guard.lean_checks,
                "detail": "; ".join(guard.errors),
            })
            if whole is not None and guard.accepted:
                finished = await finish(whole, "independent_whole_fallback")
                if finished is not None:
                    return finished

        # Residual budget reaches the additive experiment under an explicit cap
        # (SUBMISSION_EXPERIMENTAL_CAP_S; default 45 min, raise for long Putnam jobs).
        experimental_time = StageWindow(
            time_left, min(self.experimental_cap_s, max(0.0, time_left()))
        )
        if experimental_time() > 60:
            if len(open_blocks) >= 2:
                exp_started = time.monotonic()
                try:
                    if self.program_factory is None:
                        program = ProgramPortfolioAgent(
                            time_left=experimental_time,
                            reserve_s=0,
                            progress_graph=self._progress_graph,
                        )
                    else:
                        try:
                            program = self.program_factory(
                                time_left=experimental_time,
                                progress_graph=self._progress_graph,
                            )
                        except TypeError:
                            program = self.program_factory()
                    program_result = await program.solve(
                        problem, self._inner_services(services)
                    )
                except Exception as exc:
                    program_result = None
                    self._record_stage(
                        "verified_progress_program",
                        exp_started,
                        detail=f"error:{type(exc).__name__}",
                    )
                if program_result is not None:
                    guard = (
                        await self._guard_candidate(
                            problem, services, program_result.solution
                        )
                        if program_result.metadata.get("accepted_by_repl")
                        else GuardResult(False)
                    )
                    self._record_stage(
                        "verified_progress_program",
                        exp_started,
                        result=program_result,
                        substantive=guard.accepted,
                        detail="; ".join(guard.errors),
                    )
                    if guard.accepted:
                        md = result_metadata(
                            "verified_progress_program",
                            winner="verified_progress_program",
                            accepted=True,
                            program=dict(program_result.metadata),
                        )
                        services.checkpoint(program_result.solution, md)
                        return AgentResult(program_result.solution, md)
            else:
                experimental = await self._experimental_bridge(
                    problem,
                    services,
                    experimental_time,
                    stage="verified_progress_bridge",
                )
                if experimental is not None:
                    md = result_metadata(
                        "verified_progress_bridge",
                        winner="verified_progress_bridge",
                        accepted=True,
                    )
                    services.checkpoint(experimental, md)
                    return AgentResult(experimental, md)

        # Post-ladder residual recursion: if the cheap spine failed and wall/money
        # remain, spend them on dual-model lemma division with the shared bank.
        residual = await self._residual_recursion(
            problem, services, time_left, open_blocks=open_blocks
        )
        if residual is not None:
            return residual

        return AgentResult(problem.challenge, exhausted_metadata())


def create_agent() -> SubmissionAgent:
    return SubmissionAgent()
