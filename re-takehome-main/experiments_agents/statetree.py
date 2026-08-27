"""Big-changer #1+#2 — verified proof-state search with local Mathlib premises.

Instead of asking a model for a whole file, we search a tree whose nodes are
Lean-verified tactic prefixes plus their exact remaining goal state. At each node:
locally harvest real applicable premises (`apply?`), ask the model(s) for a few
short next actions, let Lean check every child, keep only novel verified states,
and expand best-first with backtracking. Lean — not an LLM — decides validity.

Universal: same procedure, premises, and prompts for every problem. Falls back to
a single whole-file model attempt for multi-theorem / term-mode challenges (v1).
Deterministic tactic sweep runs first (stage 0). Final acceptance is the strict
comparator path; internal `sorry` lives only in disposable probes.
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
    extract_lean_ex,
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
    premise_done: bool = False
    tried: set[str] = field(default_factory=set)

    def score(self) -> tuple:
        # lower is better: fewer goals, shorter goal text, shallower-but-not-too
        return (self.n_goals, len(self.goal), self.depth)


class StateTreeAgent:
    def __init__(self, *, arm: str, action_models: list[str], premise: bool = True):
        self.arm = arm
        self.action_models = [require_model(m) for m in action_models]
        self.premise = premise
        self.beam = env_int("ST_BEAM", 4, minimum=1, maximum=16)
        self.max_depth = env_int("ST_MAX_DEPTH", 12, minimum=1, maximum=32)
        self.max_model_calls = env_int("ST_MAX_MODEL_CALLS", 14, minimum=1, maximum=64)
        self.max_lean_checks = env_int("ST_MAX_LEAN_CHECKS", 90, minimum=1, maximum=400)
        self.actions_per_call = env_int("ST_ACTIONS_PER_CALL", 3, minimum=1, maximum=6)
        self.child_timeout = env_int("ST_CHILD_TIMEOUT_S", 25, minimum=5, maximum=120)
        self.premise_timeout = env_int("ST_PREMISE_TIMEOUT_S", 75, minimum=5, maximum=300)
        self.premise_depth = env_int("ST_PREMISE_MAX_DEPTH", 2, minimum=0, maximum=32)
        self.max_tokens = env_int("ST_MAX_TOKENS", 1500, minimum=200, maximum=8000)
        self.temperature = env_float("ST_TEMPERATURE", 0.5, minimum=0.0, maximum=2.0)

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        challenge = problem.challenge
        calls_q = calls_g = lean_checks = 0
        stats = {"nodes": 0, "max_depth": 0, "premise_calls": 0, "children_valid": 0}

        # ---- stage 0: deterministic tactic sweep (free) ----
        for tactic, variant in tactic_sweep_variants(challenge):
            check = await services.lean.check_file(variant, timeout_s=SWEEP_CHECK_TIMEOUT_S)
            lean_checks += 1
            if check.accepted and integrity_check(variant, challenge)[0]:
                return self._result(variant, True, "tactic_sweep", calls_q, calls_g,
                                    lean_checks, stats, winning_tactic=tactic)

        shell = LP.theorem_shell(challenge)
        if not shell.ok:
            sol, q, g, lc = await self._wholefile(problem, services)
            return self._result(sol[0], sol[1], "fallback_multi", calls_q + q,
                                calls_g + g, lean_checks + lc, stats)

        # ---- root state ----
        rc = await services.lean.check_file(LP.build_probe(shell, "", trace=True),
                                            timeout_s=self.child_timeout)
        lean_checks += 1
        if not LP.probe_valid(rc):
            sol, q, g, lc = await self._wholefile(problem, services)
            return self._result(sol[0], sol[1], "fallback_root", calls_q + q,
                                calls_g + g, lean_checks + lc, stats)
        root_goal = LP.parse_goal_state(rc.messages)
        root = Node("", root_goal, 0, LP.count_goals(root_goal), sha16(challenge))
        frontier: list[Node] = [root]
        seen: set[str] = {LP.state_hash(root_goal)}
        model_calls = 0

        while frontier and model_calls < self.max_model_calls and lean_checks < self.max_lean_checks:
            frontier.sort(key=lambda n: n.score())
            node = frontier.pop(0)
            stats["max_depth"] = max(stats["max_depth"], node.depth)
            if node.depth >= self.max_depth:
                continue

            actions: list[str] = []
            # ---- LocalPremise: real Mathlib lemmas applicable here ----
            if self.premise and not node.premise_done and node.depth <= self.premise_depth \
                    and lean_checks < self.max_lean_checks:
                ps = await services.lean.check_file(
                    LP.build_search(shell, node.prefix, "apply?"), timeout_s=self.premise_timeout)
                lean_checks += 1
                stats["premise_calls"] += 1
                node.premise_done = True
                actions += LP.parse_suggestions(ps.messages, limit=6)

            # ---- model-proposed actions (batched: several actions per call) ----
            for model in self.action_models:
                if model_calls >= self.max_model_calls:
                    break
                resp = await services.llm.complete(
                    model=model, messages=self._action_messages(problem, node, actions),
                    max_tokens=self.max_tokens, temperature=self.temperature)
                calls_q, calls_g = count_model_calls(model, calls_q, calls_g)
                model_calls += 1
                actions += self._parse_actions(resp.content)

            # ---- evaluate children ----
            for act in self._dedup(actions, node.tried):
                if lean_checks >= self.max_lean_checks:
                    break
                node.tried.add(act)
                new_prefix = (node.prefix + "\n" + act).strip("\n") if node.prefix else act
                probe = LP.build_probe(shell, new_prefix, trace=True)
                pc = await services.lean.check_file(probe, timeout_s=self.child_timeout)
                lean_checks += 1
                if not LP.probe_valid(pc):
                    continue
                if not pc.has_sorry:
                    # no goals left → candidate solution; verify strictly
                    final = LP.build_final(shell, new_prefix)
                    fc = await services.lean.check_file(final, timeout_s=self.child_timeout)
                    lean_checks += 1
                    if fc.accepted and integrity_check(final, challenge)[0]:
                        stats["children_valid"] += 1
                        return self._result(final, True, "state_tree_solved", calls_q,
                                            calls_g, lean_checks, stats, depth=node.depth + 1)
                    continue
                goal = LP.parse_goal_state(pc.messages)
                h = LP.state_hash(goal)
                if goal and h not in seen:
                    seen.add(h)
                    stats["children_valid"] += 1
                    stats["nodes"] += 1
                    frontier.append(Node(new_prefix, goal, node.depth + 1,
                                         LP.count_goals(goal), sha16(new_prefix)))
            frontier = sorted(frontier, key=lambda n: n.score())[: self.beam]

        # ---- tree exhausted: whole-file fallback so we don't regress below baseline ----
        sol, q, g, lc = await self._wholefile(problem, services)
        return self._result(sol[0], sol[1], "state_tree_exhausted", calls_q + q,
                            calls_g + g, lean_checks + lc, stats)

    # -- model action proposal --------------------------------------------------
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
            "- make the three actions genuinely different: one direct finisher, one",
            "  structural step (case split / induction / refine), one lemma-driven step.",
        ])
        prem = "\n".join(f"- {p}" for p in premises[:12]) or "(none found)"
        tried = "\n".join(f"- {t}" for t in list(node.tried)[:12]) or "(none)"
        user = "\n".join([
            f"Problem id: {problem.id}",
            f"Depth: {node.depth}   Open goals: {node.n_goals}",
            "",
            "Problem description:",
            problem.description,
            "",
            "Exact current goal state:",
            "```",
            node.goal,
            "```",
            "",
            "Real Mathlib premises that apply at this state:",
            prem,
            "",
            "Actions already tried from this state (do NOT repeat):",
            tried,
        ])
        return [{"role": "system", "content": system},
                {"role": "user", "content": user}]

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
        cleaned: list[str] = []
        for t in out:
            t = t.strip()
            if not t or len(t) > 400:
                continue
            low = t.lower()
            if any(f in low for f in _FORBIDDEN):
                continue
            cleaned.append(t)
        return cleaned

    def _dedup(self, actions: list[str], tried: set[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for a in actions:
            a = a.strip()
            low = a.lower()
            if not a or a in tried or a in seen or any(f in low for f in _FORBIDDEN):
                continue
            seen.add(a)
            out.append(a)
        return out

    # -- whole-file fallback (single G attempt) ---------------------------------
    async def _wholefile(self, problem: Problem, services: Services):
        model = self.action_models[0]
        system = "\n".join([
            "Write a complete Lean 4 file using Mathlib that proves the theorem(s).",
            "Return only the complete Lean code in one ```lean code block.",
            "Preserve the theorem names and statements; no sorry, admit, or axioms.",
        ])
        user = "\n".join(["Problem description:", problem.description, "",
                          "Challenge Lean file:", "```lean", problem.challenge, "```"])
        resp = await services.llm.complete(
            model=model, messages=[{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
            max_tokens=8000, temperature=0.2)
        q, g = count_model_calls(model, 0, 0)
        candidate, _ = extract_lean_ex(resp.content, fallback=problem.challenge)
        check = await services.lean.check_file(candidate)
        accepted = check.accepted and integrity_check(candidate, problem.challenge)[0]
        return (candidate, accepted), q, g, 1

    def _result(self, solution, accepted, stop_reason, calls_q, calls_g, lean_checks,
                stats, **extra):
        return AgentResult(solution, {
            "arm": self.arm, "protocol": "state_tree", "action_models": self.action_models,
            "accepted_by_repl": accepted, "stop_reason": stop_reason,
            "calls_q": calls_q, "calls_g": calls_g, "lean_checks": lean_checks,
            "search_stats": stats, **extra,
        })


def make_state_tree(*, arm: str, action_models: list[str], premise: bool = True) -> StateTreeAgent:
    return StateTreeAgent(arm=arm, action_models=action_models, premise=premise)
