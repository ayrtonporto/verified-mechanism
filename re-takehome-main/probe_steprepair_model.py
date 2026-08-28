"""StepRepair + model. Keep the proof skeleton; at the first failing top-level step,
try the deterministic battery, then ask G to fix THAT step only from the exact Lean
error (a far easier task than the whole theorem). Iterate. Universal. Decisive test:
does targeted per-step model repair close p09_a / p09_b from a stored near-proof?"""
import asyncio
import glob
import json
import re
import textwrap
from pathlib import Path

from re_harness.config import HarnessSettings
from re_harness.events import EventLogger
from re_harness.lean import LeanClient
from re_harness.llm import LLMClient
from re_harness.budget import BudgetLedger
from experiments_agents.multitheorem import split_declarations, _preamble_lines
from experiments_agents.common import required_decl_names, format_messages, GPT_OSS

BY = re.compile(r":=\s*by\b")
BATTERY = ["decide", "norm_num", "simp", "simp_all", "rfl", "omega", "ring", "aesop",
           "grind", "positivity", "trivial", "native_decide", "simp_all <;> omega"]

S = HarnessSettings.from_env(n_workers=1)
ev = EventLogger(Path("srm_events.jsonl"), problem_id="srm", secrets=(S.api_key,))
lean = LeanClient(image=S.lean_image, events=ev, session_id="srm", timeout_s=90)
budget = BudgetLedger(1.0)
llm = LLMClient(api_key=S.api_key, budget=budget, events=ev)


def isolate(sol, name):
    pre, blocks = split_declarations(sol)
    tgt = [b for b in blocks if name in required_decl_names(b)]
    if not tgt:
        return None
    return ("\n".join(_preamble_lines(pre)) or "import Mathlib") + "\n\n" + tgt[0].rstrip() + "\n"


def header_body(iso):
    m = BY.search(iso)
    return (iso[:m.end()], textwrap.dedent(iso[m.end():]).strip("\n")) if m else None


def top_steps(body):
    lines = body.split("\n")
    nz = [l for l in lines if l.strip()]
    if not nz:
        return []
    base = min(len(l) - len(l.lstrip()) for l in nz)
    idx = [i for i, l in enumerate(lines) if l.strip()
           and (len(l) - len(l.lstrip())) == base and not l.lstrip().startswith("--")]
    return ["\n".join(lines[idx[j]:(idx[j + 1] if j + 1 < len(idx) else len(lines))]).rstrip()
            for j in range(len(idx))]


def build(header, steps, upto, extra="all_goals sorry"):
    lines = [header]
    for ln in "\n".join(steps[:upto]).split("\n"):
        lines.append("  " + ln if ln.strip() else ln)
    if extra:
        lines.append("  " + extra)
    return "\n".join(lines) + "\n"


async def check(header, steps, upto, extra="all_goals sorry"):
    return await lean.check_file(build(header, steps, upto, extra), timeout_s=90)


def valid(c):
    return (not c.timed_out) and not any(m.get("severity") == "error" for m in c.messages)


async def model_fix_step(step, err):
    m = BY.search(step)
    if not m:
        return []
    stmt = step[:m.end()]
    sys = ("Fix ONE failing Lean 4 (Mathlib) proof step. Return ONLY a JSON array of up "
           "to 6 replacement proofs for the tactic block after `:= by`, most-likely first: "
           '["decide", "simp [..]", "..."]. No sorry/admit/axiom. Keep the step statement.')
    usr = f"Step (keep its `:= by` header):\n{stmt}\n\nExact Lean error:\n{err[:1200]}"
    r = await llm.complete(model=GPT_OSS,
                           messages=[{"role": "system", "content": sys},
                                     {"role": "user", "content": usr}],
                           max_tokens=800, temperature=0.4)
    out = []
    mm = re.search(r"\[.*\]", r.content or "", re.DOTALL)
    if mm:
        try:
            for x in json.loads(mm.group(0)):
                if isinstance(x, str) and x.strip() and "sorry" not in x and len(x) < 300:
                    out.append(x.strip())
        except Exception:
            pass
    return out


async def step_repair(header, steps, max_fix=8):
    steps = list(steps)
    for _ in range(max_fix):
        good = 0
        last = None
        for k in range(1, len(steps) + 1):
            c = await check(header, steps, k)
            if valid(c):
                good = k
            else:
                last = c
                break
        if good == len(steps):
            c = await check(header, steps, len(steps), extra="")
            return steps, valid(c)
        f = good
        base = BY.search(steps[f])
        if not base:
            return steps, False
        stmt = steps[f][:base.end()]
        cands = list(BATTERY)
        err = format_messages(last.messages) if last else ""
        cands += await model_fix_step(steps[f], err)
        fixed = False
        for tac in cands:
            trial = steps[:f] + [stmt + " " + tac] + steps[f + 1:]
            if valid(await check(header, trial, f + 1)):
                steps = trial
                fixed = True
                break
        if not fixed:
            return steps, False
    return steps, False


async def main():
    sols = sorted(glob.glob("outputs_fast/nmbank_pf_v2/*/p09_imo1964__r*.lean")) \
        + sorted(glob.glob("outputs/*/*/p09_imo1964/solution.lean"))
    seen = 0
    for sol in sols:
        if seen >= 8:
            break
        txt = Path(sol).read_text(encoding="utf-8")
        for name in ("p09_a", "p09_b"):
            iso = isolate(txt, name)
            if not iso:
                continue
            hb = header_body(iso)
            if not hb:
                continue
            steps = top_steps(hb[1])
            if not steps:
                continue
            rs, closed = await step_repair(hb[0], steps)
            print(f"{name:6s} [{sol.split('/')[-1][:22]:22s}] steps={len(steps)} closed={closed}")
            if closed:
                Path(f"srm_{name}.lean").write_text(build(hb[0], rs, len(rs), extra=""),
                                                    encoding="utf-8")
        seen += 1
    print(f"spent=${budget.snapshot().spent_usd:.4f}")
    print("DONE_0")


asyncio.run(main())
