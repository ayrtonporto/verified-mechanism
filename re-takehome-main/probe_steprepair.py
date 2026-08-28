"""StepRepair viability probe (near-zero model cost). The live p09 candidates have the
RIGHT structure (e.g. ZMod/orderOf) but a failing intermediate `have` (e.g.
`orderOf (2:ZMod 7) = 3` proved with a fabricated lemma — closable by `decide`).
StepRepair keeps the proof skeleton and re-proves each FAILING top-level `have` with
the deterministic battery, iterating. Universal. Test: does it close p09_a / p09_b
from the stored NMBANK-PF fallback candidate?"""
import asyncio
import glob
import re
import textwrap
from pathlib import Path

from re_harness.config import HarnessSettings
from re_harness.events import EventLogger
from re_harness.lean import LeanClient
from experiments_agents.multitheorem import split_declarations, _preamble_lines
from experiments_agents.common import required_decl_names
from experiments_agents import leanprobe as LP

BY = re.compile(r":=\s*by\b")
BATTERY = ["decide", "norm_num", "simp", "simp_all", "rfl", "omega", "ring",
           "aesop", "grind", "norm_num [ZMod]", "positivity", "trivial",
           "simp_all <;> omega", "decide +kernel", "native_decide"]

S = HarnessSettings.from_env(n_workers=1)
ev = EventLogger(Path("steprepair_events.jsonl"), problem_id="steprepair", secrets=(S.api_key,))
lean = LeanClient(image=S.lean_image, events=ev, session_id="steprepair", timeout_s=90)


def isolate(solution, name):
    pre, blocks = split_declarations(solution)
    tgt = [b for b in blocks if name in required_decl_names(b)]
    if not tgt:
        return None
    imports = "\n".join(_preamble_lines(pre)) or "import Mathlib"
    return imports + "\n\n" + tgt[0].rstrip() + "\n"


def header_body(iso):
    m = BY.search(iso)
    return (iso[:m.end()], textwrap.dedent(iso[m.end():]).strip("\n")) if m else None


def top_steps(body):
    """Return list of top-level step texts (each: a base-indent line + its indented tail)."""
    lines = body.split("\n")
    nz = [l for l in lines if l.strip()]
    if not nz:
        return []
    base = min(len(l) - len(l.lstrip()) for l in nz)
    idx = [i for i, l in enumerate(lines) if l.strip()
           and (len(l) - len(l.lstrip())) == base and not l.lstrip().startswith("--")]
    steps = []
    for j in range(len(idx)):
        end = idx[j + 1] if j + 1 < len(idx) else len(lines)
        steps.append("\n".join(lines[idx[j]:end]).rstrip())
    return steps


def build(header, steps, upto, extra="all_goals sorry"):
    body = "\n".join(steps[:upto])
    lines = [header]
    for ln in body.split("\n"):
        lines.append("  " + ln if ln.strip() else ln)
    if extra:
        lines.append("  " + extra)
    return "\n".join(lines) + "\n"


async def ok(header, steps, upto, extra="all_goals sorry"):
    c = await lean.check_file(build(header, steps, upto, extra), timeout_s=90)
    return (not c.timed_out) and not any(m.get("severity") == "error" for m in c.messages)


def repair_have(step, tac):
    """Replace a top-level `have … := by …` step's proof with a single battery tactic."""
    m = BY.search(step)
    if not m or not step.lstrip().startswith("have"):
        return None
    return step[:m.end()] + " " + tac


async def step_repair(header, steps, max_fix=8):
    steps = list(steps)
    for _ in range(max_fix):
        # find first failing prefix boundary
        good = 0
        for k in range(1, len(steps) + 1):
            if await ok(header, steps, k):
                good = k
            else:
                break
        if good == len(steps):
            # all steps elaborate with sorry-stub; check the real close
            if await ok(header, steps, len(steps), extra=""):
                return steps, True
            return steps, False
        f = good  # first failing step index
        fixed = False
        for tac in BATTERY:
            rep = repair_have(steps[f], tac)
            if rep is None:
                break
            trial = steps[:f] + [rep] + steps[f + 1:]
            if await ok(header, trial, f + 1):
                steps = trial
                fixed = True
                break
        if not fixed:
            return steps, False
    return steps, False


async def main():
    sols = sorted(glob.glob("outputs_fast/nmbank_pf_v2/*/p09_imo1964__r*.lean")) \
        + sorted(glob.glob("outputs/*/*/p09_imo1964/solution.lean"))
    tried = 0
    for sol in sols:
        if tried >= 6:
            break
        txt = Path(sol).read_text(encoding="utf-8")
        for name in ("p09_a", "p09_b"):
            iso = isolate(txt, name)
            if not iso:
                continue
            hb = header_body(iso)
            if not hb:
                continue
            header, body = hb
            steps = top_steps(body)
            if not steps:
                continue
            res_steps, closed = await step_repair(header, steps)
            tag = sol.split("/")[-1] if "outputs_fast" in sol else sol.split("/")[2]
            print(f"{name:6s} [{tag[:24]:24s}] steps={len(steps)} closed={closed}")
            if closed:
                Path(f"steprepair_{name}.lean").write_text(
                    build(header, res_steps, len(res_steps), extra=""), encoding="utf-8")
        tried += 1
    print("DONE_0")


asyncio.run(main())
