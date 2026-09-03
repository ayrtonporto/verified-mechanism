"""Big-changer #1+#2 — verified proof-state search with local Mathlib premises.

StateTree v2 (per the implementation brief): instead of asking a model for a whole
file, search a tree whose nodes are Lean-verified tactic prefixes plus their exact
remaining goal state. Lean — not an LLM — decides validity.

P0 fixes over v1 (which collapsed early and closed nothing natively):
- **per-node retry rounds**: a node is re-inserted and re-expanded until its round
  budget is spent, so one bad batch does not abandon a live state;
- **action-level repair**: invalid actions keep their exact Lean diagnostics; when a
  round makes no progress, the repair model fixes those actions from the errors;
- **tried-list actually reaches the model** (v1 populated it after the only prompt);
- **stratified frontier**: keep the fewest-goals state AND the deepest AND a
  goal-increasing structural branch AND one per root-branch — never prune a valid
  decomposition just because it has more goals.

Universal (same procedure/premises/prompts every problem). Deterministic sweep is
stage 0; a whole-file repair loop is the fallback so the tree can never score below
the tactic-augmented baseline. Internal `sorry` lives only in disposable probes;
final acceptance is the strict comparator path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from re_harness import AgentResult, Problem, Services

from . import leanprobe as LP
from .common import (
    SWEEP_CHECK_TIMEOUT_S,
    count_model_calls,
    env_float,
    env_int,
    format_messages,
    integrity_check,
    require_model,
    sha16,
    tactic_sweep_variants,
)

_FORBIDDEN = ("sorry", "admit", "axiom", "import ", "theorem ", "lemma ")


@dataclass
class Node:
    prefix: str
    goal: str
    depth: int
    n_goals: int
    parent_hash: str
    root_branch: str = ""            # first action taken from the root (diversity key)
    rounds: int = 0                  # remaining expansion rounds
    premise_done: bool = False
    tried: set[str] = field(default_factory=set)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (action, diagnostic)

    def score(self) -> tuple:
        return (self.n_goals, len(self.goal), self.depth)


class StateTreeAgent:
    def __init__(self, *, arm: str, action_models: list[str], premise: bool = True):
        self.arm = arm
        self.action_models = [require_model(m) for m in action_models]
        self.proposer = self.action_models[0]
        self.repairer = self.action_models[-1]
        self.premise = premise
        self.beam = env_int("ST_BEAM", 4, minimum=1, maximum=16)
        self.max_depth = env_int("ST_MAX_DEPTH", 12, minimum=1, maximum=32)
        self.max_model_calls = env_int("ST_MAX_MODEL_CALLS", 14, minimum=1, maximum=96)
        self.max_lean_checks = env_int("ST_MAX_LEAN_CHECKS", 90, minimum=1, maximum=600)
        self.actions_per_call = env_int("ST_ACTIONS_PER_CALL", 4, minimum=1, maximum=8)
        self.repair_actions_per_call = env_int("ST_REPAIR_ACTIONS_PER_CALL", 4, minimum=1, maximum=8)
        self.state_rounds = env_int("ST_STATE_ROUNDS", 3, minimum=1, maximum=8)
        self.child_timeout = env_int("ST_CHILD_TIMEOUT_S", 25, minimum=5, maximum=120)
        self.premise_timeout = env_int("ST_PREMISE_TIMEOUT_S", 75, minimum=5, maximum=300)
        self.premise_depth = env_int("ST_PREMISE_MAX_DEPTH", 4, minimum=0, maximum=32)
        self.diag_limit = env_int("ST_DIAGNOSTIC_LIMIT", 2000, minimum=200, maximum=8000)
        self.max_tokens = env_int("ST_MAX_TOKENS", 1500, minimum=200, maximum=8000)
        self.temperature = env_float("ST_TEMPERATURE", 0.5, minimum=0.0, maximum=2.0)

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        challenge = problem.challenge
        self._calls_q = self._calls_g = self._lean_checks = 0
        stats = {"nodes": 0, "max_depth": 0, "premise_calls": 0, "children_valid": 0,
                 "model_calls": 0, "invalid_actions": 0, "premise_children": 0}

        # ---- stage 0: deterministic tactic sweep (free) ----
        for tactic, variant in tactic_sweep_variants(challenge):
            check = await services.lean.check_file(variant, timeout_s=SWEEP_CHECK_TIMEOUT_S)
            self._lean_checks += 1
            if check.accepted and integrity_check(variant, challenge)[0]:
                return self._result(variant, True, "tactic_sweep", stats, winning_tactic=tactic)

        shell = LP.theorem_shell(challenge)
        if not shell.ok:
            return await self._fallback(problem, services, "fallback_multi", stats)

        rc = await services.lean.check_file(LP.build_probe(shell, "", trace=True),
                                            timeout_s=self.child_timeout)
        self._lean_checks += 1
        if not LP.probe_valid(rc):
            return await self._fallback(problem, services, "fallback_root", stats)
        root_goal = LP.parse_goal_state(rc.messages)
        root = Node("", root_goal, 0, LP.count_goals(root_goal), sha16(challenge),
                    rounds=self.state_rounds)
        frontier: list[Node] = [root]
        seen: set[str] = {LP.state_hash(root_goal)}

        while frontier and stats["model_calls"] < self.max_model_calls \
                and self._lean_checks < self.max_lean_checks:
            frontier.sort(key=lambda n: n.score())
            node = frontier.pop(0)
            if node.rounds <= 0 or node.depth >= self.max_depth:
                continue
            stats["max_depth"] = max(stats["max_depth"], node.depth)

            # ---- gather candidate actions for this round ----
            actions: list[str] = []
            premise_actions: set[str] = set()
            if self.premise and not node.premise_done and node.depth <= self.premise_depth \
                    and self._lean_checks < self.max_lean_checks:
                node.premise_done = True
                for tac in ("exact?", "apply?"):
                    if self._lean_checks >= self.max_lean_checks:
                        break
                    ps = await services.lean.check_file(
                        LP.build_search(shell, node.prefix, tac), timeout_s=self.premise_timeout)
                    self._lean_checks += 1
                    stats["premise_calls"] += 1
                    for s in LP.parse_suggestions(ps.messages, limit=6):
                        premise_actions.add(s)
                        actions.append(s)

            if stats["model_calls"] < self.max_model_calls:
                actions += await self._ask(services, self.proposer,
                                           self._action_messages(problem, node, list(premise_actions)))
                stats["model_calls"] += 1

            solved, new_child = await self._evaluate(
                services, shell, challenge, node, actions, seen, frontier, stats, premise_actions)
            if solved is not None:
                return solved

            # ---- action-level repair on a stalled round (uses exact Lean errors) ----
            if not new_child and node.failed and stats["model_calls"] < self.max_model_calls:
                rep = await self._ask(services, self.repairer,
                                      self._repair_action_messages(problem, node))
                stats["model_calls"] += 1
                solved, child2 = await self._evaluate(
                    services, shell, challenge, node, rep, seen, frontier, stats, set())
                if solved is not None:
                    return solved
                new_child = new_child or child2

            node.rounds -= 1
            if node.rounds > 0:
                frontier.append(node)
            frontier = self._prune(frontier)

        return await self._fallback(problem, services, "state_tree_exhausted", stats)

    async def _evaluate(self, services, shell, challenge, node, actions, seen, frontier,
                        stats, premise_actions):
        """Check each candidate action; returns (solved_result_or_None, made_new_child)."""
        new_child = False
        for act in self._dedup(actions, node.tried):
            if self._lean_checks >= self.max_lean_checks:
                break
            node.tried.add(act)
            new_prefix = (node.prefix + "\n" + act).strip("\n") if node.prefix else act
            pc = await services.lean.check_file(LP.build_probe(shell, new_prefix, trace=True),
                                                timeout_s=self.child_timeout)
            self._lean_checks += 1
            if not LP.probe_valid(pc):
                stats["invalid_actions"] += 1
                node.failed.append((act, format_messages(pc.messages)[: self.diag_limit]))
                continue
            if not pc.has_sorry:
                final = LP.build_final(shell, new_prefix)
                fc = await services.lean.check_file(final, timeout_s=self.child_timeout)
                self._lean_checks += 1
                if fc.accepted and integrity_check(final, challenge)[0]:
                    stats["children_valid"] += 1
                    return self._result(final, True, "state_tree_solved", stats,
                                        depth=node.depth + 1), True
                continue
            goal = LP.parse_goal_state(pc.messages)
            h = LP.state_hash(goal)
            if goal and h not in seen:
                seen.add(h)
                stats["children_valid"] += 1
                stats["nodes"] += 1
                if act in premise_actions:
                    stats["premise_children"] += 1
                frontier.append(Node(new_prefix, goal, node.depth + 1, LP.count_goals(goal),
                                     sha16(new_prefix),
                                     root_branch=node.root_branch or act,
                                     rounds=self.state_rounds))
                new_child = True
        return None, new_child

    def _prune(self, frontier: list[Node]) -> list[Node]:
        """Stratified/Pareto keep: never drop a valid decomposition just for goal count."""
        if len(frontier) <= self.beam:
            return frontier
        keep: list[Node] = []
        pool = sorted(frontier, key=lambda n: n.score())
        # 1) fewest goals, 2) deepest, 3) a goal-increasing structural branch
        picks = [min(pool, key=lambda n: n.n_goals),
                 max(pool, key=lambda n: n.depth),
                 max(pool, key=lambda n: n.n_goals)]
        for p in picks:
            if p not in keep:
                keep.append(p)
        # 4) one representative per distinct root branch
        seen_branch = {n.root_branch for n in keep}
        for n in pool:
            if len(keep) >= self.beam:
                break
            if n.root_branch not in seen_branch:
                keep.append(n)
                seen_branch.add(n.root_branch)
        # 5) fill remaining by score
        for n in pool:
            if len(keep) >= self.beam:
                break
            if n not in keep:
                keep.append(n)
        return keep[: self.beam]

    async def _ask(self, services, model, messages):
        resp = await services.llm.complete(model=model, messages=messages,
                                           max_tokens=self.max_tokens, temperature=self.temperature)
        self._calls_q, self._calls_g = count_model_calls(model, self._calls_q, self._calls_g)
        return self._parse_actions(resp.content)

    # -- prompts ----------------------------------------------------------------
    def _action_messages(self, problem: Problem, node: Node, premises: list[str]) -> list[dict]:
        system = "\n".join([
            "You are advancing a Lean 4 (Mathlib) proof ONE small step at a time.",
            "You are given the exact current goal state and real Mathlib lemmas/tactics",
            "that apply here (from Lean's own search). Return ONLY a JSON array of "
            f"{self.actions_per_call} short next actions, most-promising first:",
            '[{"tactic": "...", "intent": "..."}, ...]',
            "Rules for each tactic:",
            "- at most two tactic commands, or a single `have name : stmt := by ...`;",
            "- at most 400 characters; no imports, no theorem/lemma declarations;",
            "- never use sorry, admit, or axiom; never edit the goal/theorem statement;",
            "- prefer named lemmas from the provided premises or standard automation",
            "  (omega, simp, simp_all, norm_num, nlinarith, decide, aesop, rcases, obtain,",
            "  induction, constructor, refine, exact, apply, rw, calc);",
            "- it is fine to `refine`/`constructor`/`induction` into several subgoals;",
            "- make the actions genuinely different: one direct finisher, one structural",
            "  step (case split / induction / refine), one lemma-driven step.",
        ])
        prem = "\n".join(f"- {p}" for p in premises[:12]) or "(none found)"
        tried = "\n".join(f"- {t}" for t in list(node.tried)[:16]) or "(none)"
        user = "\n".join([
            f"Problem id: {problem.id}",
            f"Depth: {node.depth}   Open goals: {node.n_goals}",
            "", "Problem description:", problem.description,
            "", "Exact current goal state:", "```", node.goal, "```",
            "", "Real Mathlib premises that apply at this state:", prem,
            "", "Actions already tried from THIS state (do NOT repeat these):", tried,
        ])
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _repair_action_messages(self, problem: Problem, node: Node) -> list[dict]:
        system = "\n".join([
            "You are repairing failed Lean 4 tactic steps using the EXACT compiler errors.",
            f"Return ONLY a JSON array of {self.repair_actions_per_call} corrected next actions:",
            '[{"tactic": "...", "intent": "..."}, ...]',
            "Same rules: at most two tactic commands or one `have`; <=400 chars; no imports,",
            "theorem/lemma decls, sorry, admit, axiom, or statement edits. Fix the real cause",
            "shown in the diagnostic (wrong lemma name, argument, type, or missing step);",
            "you may also propose a genuinely different approach to the same goal.",
        ])
        fails = "\n\n".join(
            f"FAILED ACTION: {a}\nLEAN ERROR:\n{d}" for a, d in node.failed[-4:]
        )
        user = "\n".join([
            f"Problem id: {problem.id}",
            "Exact current goal state:", "```", node.goal, "```",
            "", "These actions were rejected by Lean at this state — fix them:", "",
            fails,
        ])
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _parse_actions(self, text: str) -> list[str]:
        out: list[str] = []
        m = re.search(r"\[.*\]", text or "", flags=re.DOTALL)
        if m:
            try:
                arr = json.loads(m.group(0))
                for item in arr:
                    if isinstance(item, dict):
                        out.append(str(item.get("tactic", "")))
                    elif isinstance(item, str):
                        out.append(item)
            except (json.JSONDecodeError, TypeError):
                pass
        cleaned = []
        for t in out:
            t = t.strip()
            if t and len(t) <= 400 and not any(f in t.lower() for f in _FORBIDDEN):
                cleaned.append(t)
        return cleaned

    def _dedup(self, actions: list[str], tried: set[str]) -> list[str]:
        seen: set[str] = set()
        out = []
        for a in actions:
            a = a.strip()
            if not a or a in tried or a in seen or any(f in a.lower() for f in _FORBIDDEN):
                continue
            seen.add(a)
            out.append(a)
        return out

    # -- fallback: full hardened sweep+repair loop (StateTree >= baseline) -------
    async def _fallback(self, problem, services, reason, stats):
        from .tactics import make_tactic_agent
        agent = make_tactic_agent(arm=f"{self.arm}-fb", propose_model=self.proposer,
                                  repair_model=self.repairer)
        res = await agent.solve(problem, services)
        md = res.metadata
        self._calls_q += int(md.get("calls_q", 0))
        self._calls_g += int(md.get("calls_g", 0))
        self._lean_checks += int(md.get("lean_checks", 0))
        return self._result(res.solution, bool(md.get("accepted_by_repl")), reason, stats)

    def _result(self, solution, accepted, stop_reason, stats, **extra):
        return AgentResult(solution, {
            "arm": self.arm, "protocol": "state_tree_v2", "action_models": self.action_models,
            "accepted_by_repl": accepted, "stop_reason": stop_reason,
            "calls_q": self._calls_q, "calls_g": self._calls_g, "lean_checks": self._lean_checks,
            "search_stats": stats, **extra,
        })


def make_state_tree(*, arm: str, action_models: list[str], premise: bool = True) -> StateTreeAgent:
    return StateTreeAgent(arm=arm, action_models=action_models, premise=premise)
