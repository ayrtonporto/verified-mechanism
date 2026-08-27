"""Resume viability probe (offline, zero model calls). For each unsolved problem,
take the stored candidate with the deepest Lean-verified prefix, show the REMAINING
goal at that prefix, and try to close the whole theorem from there with the
deterministic battery (now incl. grind). If a battery tactic finishes a near-miss,
truncate-and-resume is worth building online."""
import asyncio
import glob
import re
import textwrap
from pathlib import Path

from re_harness.config import HarnessSettings
from re_harness.events import EventLogger
from re_harness.lean import LeanClient
from experiments_agents import leanprobe as LP
from experiments_agents.multitheorem import split_declarations, _preamble_lines
from experiments_agents.common import required_decl_names, CLOSING_TACTICS, integrity_check

TARGETS = {
    "p09_imo1964": ["p09_a", "p09_b"],
    "rmo_2000_2": ["rmo_2000_2"],
    "rmo_2000_3": ["rmo_2000_3"],
}
BY = re.compile(r":=\s*by\b")
S = HarnessSettings.from_env(n_workers=1)
ev = EventLogger(Path("resume_events.jsonl"), problem_id="resume", secrets=(S.api_key,))
lean = LeanClient(image=S.lean_image, events=ev, session_id="resume", timeout_s=90)


def isolate(solution, name):
    pre, blocks = split_declarations(solution)
    tgt = [b for b in blocks if name in required_decl_names(b)]
    if not tgt:
        return None
    imports = "\n".join(_preamble_lines(pre)) or "import Mathlib"
    return imports + "\n\n" + tgt[0].rstrip() + "\n"


def shell_of(iso):
    m = BY.search(iso)
    if not m:
        return None
    return iso[:m.end()], textwrap.dedent(iso[m.end():]).strip("\n")


def base_prefixes(body):
    lines = body.split("\n")
    nz = [l for l in lines if l.strip()]
    if not nz:
        return []
    base = min(len(l) - len(l.lstrip()) for l in nz)
    idx = [i for i, l in enumerate(lines) if l.strip()
           and (len(l) - len(l.lstrip())) == base and not l.lstrip().startswith("--")]
    out = []
    for j in range(len(idx)):
        end = idx[j + 1] if j + 1 < len(idx) else len(lines)
        out.append("\n".join(lines[:end]).rstrip())
    return out


def build(header, prefix, extra=""):
    ind = "  "
    body = "\n".join(ind + l if l.strip() else l for l in prefix.split("\n"))
    tail = ("\n" + ind + extra) if extra else ""
    return header + "\n" + body + tail + "\n"


async def deepest(solution, name):
    iso = isolate(solution, name)
    if not iso:
        return None
    sh = shell_of(iso)
    if not sh:
        return None
    header, body = sh
    prefixes = base_prefixes(body)
    best = 0
    best_pref = ""
    for k, pref in enumerate(prefixes, 1):
        c = await lean.check_file(build(header, pref, "all_goals sorry"), timeout_s=90)
        if LP.probe_valid(c):
            best, best_pref = k, pref
        else:
            break
    return best, len(prefixes), header, best_pref


async def main():
    for pid, names in TARGETS.items():
        sols = sorted(glob.glob(f"outputs/*/*/{pid}/solution.lean"))
        for name in names:
            top = None
            for sol in sols:
                txt = Path(sol).read_text(encoding="utf-8")
                d = await deepest(txt, name)
                if d and (top is None or d[0] > top[0]):
                    top = (d[0], d[1], d[2], d[3], sol.split("/")[1])
            if not top or top[0] == 0:
                print(f"### {name}: no verified prefix > 0")
                continue
            best, total, header, pref, arm = top
            print(f"### {name}: deepest {best}/{total} steps (from {arm})")
            # remaining goal at that prefix
            tc = await lean.check_file(build(header, pref, "trace_state; all_goals sorry"), timeout_s=90)
            goal = LP.parse_goal_state(tc.messages)
            print("REMAINING GOAL:\n" + (goal[:800] if goal else "(none / already closed)"))
            # try to finish from the prefix with each battery tactic
            closed = []
            for tac in CLOSING_TACTICS:
                cand = build(header, pref, tac)
                c = await lean.check_file(cand, timeout_s=90)
                if c.accepted and not c.has_sorry:
                    print(f"  >>> BATTERY CLOSES from prefix with: {tac}")
                    closed.append(tac)
            if not closed:
                print("  battery does not finish from the deepest prefix")
    print("DONE_0")


asyncio.run(main())
