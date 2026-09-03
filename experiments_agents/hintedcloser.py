"""HintedCloser (HC) — narrow, incrementally-verified `nlinarith`-hint interface.

Rationale. HintedProver (free-form file + repair) gets 0/16 on rmo_2000_2 even though a
comparator-passing proof exists in the cast-ℤ + `nlinarith [hints]` + squeeze idiom, and
§2.9 says the models produce the right *strategy* but not the exact multi-step Lean
certificate. HC removes the two remaining failure surfaces:

  * SYNTAX/STRUCTURE — the model never writes raw Lean scaffolding. It returns a JSON
    proof plan (a list of steps, each a *statement* + a *closer* from a fixed menu +
    a *hint-term list*), and WE assemble the `have NAME : STMT := by nlinarith [HINTS]`
    boilerplate. The model authors only mathematical content.
  * WHOLE-FILE COUPLING — steps are verified INCREMENTALLY. Each accepted step is locked
    into the verified prefix; when a step fails, only THAT step's brackets are re-sampled
    (given the goal state after the prefix and the Lean error), so a single wrong hint no
    longer discards the whole proof. This is the "fill the bracket" action interface at
    its narrowest.

Universal: identical JSON schema, identical assembly, identical closer menu on every
problem; nothing is keyed to a problem id or answer. The ℤ-cast and every hint term are
authored by the models, never by us. `sorry` is used only to stub the tail while probing a
prefix; a returned proof is strict (no sorry, integrity-checked).
"""

from __future__ import annotations

import json
import re
from typing import Any

from re_harness import AgentResult, Problem, Services

from .common import (
    QWEN,
    GPT_OSS,
    count_model_calls,
    format_messages,
    integrity_check,
    require_model,
)
from .nearmiss import split_header_body

# Fixed closer menu the model may pick per step (universal automation only).
_CLOSERS = ("nlinarith", "linarith", "positivity", "omega", "norm_num", "ring", "simp")

_SYSTEM = (
    "You are proving a Lean 4 + Mathlib theorem by emitting a STRUCTURED PLAN, not raw "
    "Lean. Return a single ```json block with this schema:\n"
    "{\n"
    '  "prep": ["<optional raw tactic lines run first, e.g. a nat->int cast>", ...],\n'
    '  "steps": [ {"name":"h1", "stmt":"<Lean prop, no `by`>", '
    '"closer":"nlinarith", "hints":["<Lean term>", ...]}, ... ],\n'
    '  "finish": {"closer":"omega", "hints":[]}\n'
    "}\n"
    "We assemble each step as `have <name> : <stmt> := by <closer> [<hints>]` and check it "
    "in Lean incrementally, then run `finish` on the main goal. Rules that make hard "
    "arithmetic close:\n"
    "- If a hypothesis/goal has ℕ subtraction (`a-b` truncates at 0), put a guard + cast in "
    "`prep`, e.g. [\"have hnn : b ≤ a := by nlinarith [...]\", \"zify [hnn] at h\"], and "
    "state later steps over ℤ.\n"
    "- Each step should be a polynomial (in)equality closable by its closer with the RIGHT "
    "hints: squares of differences `sq_nonneg (E)`, products of sign-known factors "
    "`mul_nonneg hA hB` / `mul_pos hA hB`, or explicit products `(A)*(B)`. Choosing these "
    "certificates is the whole game.\n"
    "- To squeeze an integer t between consecutive values, add steps `lo < t` and `t < lo+2` "
    "then `finish` with omega.\n"
    "- `hints` are Lean terms (may reference hypotheses and earlier step names). Keep stmts "
    "and hints valid Lean expressions. Output ONLY the json block."
)


def _extract_json(text: str) -> dict[str, Any] | None:
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text or "", flags=re.DOTALL)
    cands = blocks + [text or ""]
    for c in cands:
        c = c.strip()
        # tolerate leading prose: grab the outermost {...}
        i, j = c.find("{"), c.rfind("}")
        if i < 0 or j <= i:
            continue
        try:
            return json.loads(c[i : j + 1])
        except Exception:
            continue
    return None


def _closer(step: dict[str, Any]) -> str:
    c = str(step.get("closer", "nlinarith")).strip()
    return c if c in _CLOSERS else "nlinarith"


def _step_line(step: dict[str, Any]) -> str | None:
    name = str(step.get("name", "")).strip()
    stmt = str(step.get("stmt", "")).strip()
    if not name or not stmt or not re.fullmatch(r"[A-Za-z_][\w']*", name):
        return None
    hints = step.get("hints", []) or []
    hs = ", ".join(str(h).strip() for h in hints if str(h).strip())
    cl = _closer(step)
    bracket = f" [{hs}]" if hs and cl in ("nlinarith", "linarith", "simp") else ""
    return f"have {name} : {stmt} := by {cl}{bracket}"


def _finish_line(fin: dict[str, Any] | None) -> str:
    if not isinstance(fin, dict):
        return "omega"
    cl = _closer(fin)
    hints = fin.get("hints", []) or []
    hs = ", ".join(str(h).strip() for h in hints if str(h).strip())
    return f"{cl}{(' [' + hs + ']') if hs and cl in ('nlinarith','linarith','simp') else ''}"


class HintedCloser:
    def __init__(self, *, arm: str, model: str, planner_model: str | None = None,
                 samples: int = 2, step_retries: int = 2, temperature: float = 0.9,
                 max_tokens: int = 4096, check_timeout_s: int = 90):
        self.arm = arm
        self.model = require_model(model)
        self.planner_model = require_model(planner_model) if planner_model else None
        self.samples = samples
        self.step_retries = step_retries
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.check_timeout_s = check_timeout_s

    def _header(self, challenge: str) -> tuple[str, str] | None:
        return split_header_body(challenge)

    async def _elaborates(self, services: Services, header: str, prefix_lines: list[str]) -> bool:
        body = "\n".join("  " + l for l in prefix_lines)
        probe = f"{header}\n{body}\n  all_goals sorry\n"
        try:
            c = await services.lean.check_file(probe, timeout_s=self.check_timeout_s)
        except Exception:
            return False
        return not c.timed_out and not any(m.get("severity") == "error" for m in c.messages)

    async def _assemble_and_check(self, services: Services, header: str,
                                  prefix_lines: list[str], finish: str, challenge: str):
        body = "\n".join("  " + l for l in prefix_lines + [finish])
        cand = f"{header}\n{body}\n"
        try:
            c = await services.lean.check_file(cand, timeout_s=self.check_timeout_s)
        except Exception:
            return cand, None
        return cand, c

    async def _one_sample(self, problem: Problem, services: Services, plan: str):
        sh = self._header(problem.challenge)
        if not sh:
            return None, 0, 0
        header, _ = sh
        q = g = 0
        user = (
            f"Problem:\n{problem.description}\n\nTarget theorem:\n```lean\n{problem.challenge}\n```"
            + (f"\n\nMathematical plan:\n{plan}" if plan else "")
        )
        resp = await services.llm.complete(model=self.model, temperature=self.temperature,
                                           max_tokens=self.max_tokens,
                                           messages=[{"role": "system", "content": _SYSTEM},
                                                     {"role": "user", "content": user}])
        dq, dg = count_model_calls(self.model, 0, 0); q += dq; g += dg
        spec = _extract_json(resp.content or "")
        if not spec:
            return None, q, g

        prefix: list[str] = [str(p).strip() for p in (spec.get("prep") or []) if str(p).strip()]
        # verify prep elaborates; if not, drop it (model may have mis-cast)
        if prefix and not await self._elaborates(services, header, prefix):
            prefix = []

        for step in (spec.get("steps") or []):
            line = _step_line(step if isinstance(step, dict) else {})
            if not line:
                continue
            trial = prefix + [line]
            if await self._elaborates(services, header, trial):
                prefix = trial
                continue
            # re-sample ONLY this step's hints, given the current goal + error
            fixed = await self._repair_step(services, header, prefix, step, problem)
            q += fixed[1]; g += fixed[2]
            if fixed[0] is not None:
                prefix.append(fixed[0])

        finish = _finish_line(spec.get("finish"))
        cand, check = await self._assemble_and_check(services, header, prefix, finish, problem.challenge)
        ok = bool(check and check.accepted and not check.has_sorry
                  and integrity_check(cand, problem.challenge)[0])
        return (cand if ok else None), q, g

    async def _repair_step(self, services: Services, header: str, prefix: list[str],
                           step: dict[str, Any], problem: Problem):
        # show the model the goal state right after the verified prefix
        body = "\n".join("  " + l for l in prefix)
        probe = f"{header}\n{body}\n  sorry\n"
        try:
            c = await services.lean.check_file(probe, timeout_s=self.check_timeout_s)
            diag = format_messages(c.messages)
        except Exception:
            diag = ""
        q = g = 0
        for _ in range(self.step_retries):
            user = (
                "We are proving a Lean theorem incrementally. The verified prefix so far is:\n"
                f"```lean\n{body if body.strip() else '  (none)'}\n```\n"
                f"The current goal state (as Lean sees it, tail stubbed with sorry):\n```\n{diag}\n```\n"
                f"Propose ONE next step as json: {{\"name\":\"..\",\"stmt\":\"..\",\"closer\":\"nlinarith\",\"hints\":[..]}}. "
                "It must be a Lean-valid `have` that its closer can discharge with the right "
                "square/product hints. Output ONLY the json object."
            )
            resp = await services.llm.complete(model=self.model, temperature=self.temperature,
                                               max_tokens=1500,
                                               messages=[{"role": "system", "content": _SYSTEM},
                                                         {"role": "user", "content": user}])
            dq, dg = count_model_calls(self.model, 0, 0); q += dq; g += dg
            spec = _extract_json(resp.content or "")
            if not isinstance(spec, dict):
                continue
            line = _step_line(spec)
            if line and await self._elaborates(services, header, prefix + [line]):
                return line, q, g
        return None, q, g

    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        plan, q0, g0 = "", 0, 0
        if self.planner_model:
            try:
                r = await services.llm.complete(
                    model=self.planner_model, temperature=self.temperature, max_tokens=self.max_tokens,
                    messages=[{"role": "system",
                               "content": "Give a concise correct mathematical plan (key bounds, "
                                          "the squeeze/case structure, the identity that pins the "
                                          "answer). No Lean."},
                              {"role": "user", "content": f"{problem.description}\n\n```lean\n{problem.challenge}\n```"}])
                plan = (r.content or "").strip()[:3500]
                q0, g0 = count_model_calls(self.planner_model, 0, 0)
            except Exception:
                pass
        calls_q, calls_g = q0, g0
        for s in range(self.samples):
            try:
                sol, q, g = await self._one_sample(problem, services, plan)
            except Exception:
                sol, q, g = None, 0, 0
            calls_q += q; calls_g += g
            if sol is not None:
                services.checkpoint(sol, {"arm": self.arm, "sample": s})
                return AgentResult(sol, {"arm": self.arm, "protocol": "hinted_closer",
                                         "accepted_by_repl": True, "sample": s,
                                         "calls_q": calls_q, "calls_g": calls_g})
        return AgentResult(problem.challenge, {"arm": self.arm, "protocol": "hinted_closer",
                                               "accepted_by_repl": False,
                                               "calls_q": calls_q, "calls_g": calls_g})


def create_agent():
    return HintedCloser(arm="HC-GP", model=GPT_OSS, planner_model=GPT_OSS, samples=2)


def create_g():
    return HintedCloser(arm="HC-G", model=GPT_OSS, samples=2)


def create_gp():
    return HintedCloser(arm="HC-GP", model=GPT_OSS, planner_model=GPT_OSS, samples=2)


def create_q():
    return HintedCloser(arm="HC-Q", model=QWEN, samples=2)
