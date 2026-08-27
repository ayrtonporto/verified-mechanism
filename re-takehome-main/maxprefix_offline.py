"""E1 MaxPrefix (offline). Zero model calls. For every stored best-candidate
solution.lean of the UNSOLVED problems, measure the max Lean-verified prefix of
each theorem body: how many top-level tactic steps elaborate before the first
error (remaining goals stubbed with `all_goals sorry`). Builds the shell manually
by splitting at the THEOREM's own `:= by` (the first one), so nested `have := by`
do not break it. Tells us whether the models produce deep partial progress we
currently discard."""
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
from experiments_agents.common import required_decl_names

TARGETS = {
    "p09_imo1964": ["p09_a", "p09_b"],
    "rmo_2000_2": ["rmo_2000_2"],
    "rmo_2000_3": ["rmo_2000_3"],
}
BY = re.compile(r":=\s*by\b")

S = HarnessSettings.from_env(n_workers=1)
ev = EventLogger(Path("maxprefix_events.jsonl"), problem_id="maxprefix", secrets=(S.api_key,))
lean = LeanClient(image=S.lean_image, events=ev, session_id="maxprefix", timeout_s=60)


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
    header = iso[:m.end()]
    body = textwrap.dedent(iso[m.end():]).strip("\n")
    if not body:
        return None
    return header, body


def base_prefixes(body):
    lines = body.split("\n")
    nz = [l for l in lines if l.strip()]
    if not nz:
        return []
    base = min(len(l) - len(l.lstrip()) for l in nz)
    idx = [
        i for i, l in enumerate(lines)
        if l.strip() and (len(l) - len(l.lstrip())) == base
        and not l.lstrip().startswith("--")
    ]
    out = []
    for j in range(len(idx)):
        end = idx[j + 1] if j + 1 < len(idx) else len(lines)
        out.append("\n".join(lines[:end]).rstrip())
    return out


def build(header, prefix):
    ind = "  "
    body = "\n".join(ind + l if l.strip() else l for l in prefix.split("\n"))
    return header + "\n" + body + "\n" + ind + "all_goals sorry\n"


async def measure(solution, name):
    iso = isolate(solution, name)
    if not iso:
        return None
    sh = shell_of(iso)
    if not sh:
        return None
    header, body = sh
    prefixes = base_prefixes(body)
    total = len(prefixes)
    best = 0
    for k, pref in enumerate(prefixes, 1):
        c = await lean.check_file(build(header, pref), timeout_s=60)
        if LP.probe_valid(c):
            best = k
        else:
            break
    return best, total


async def main():
    for pid, names in TARGETS.items():
        sols = sorted(glob.glob(f"outputs/*/*/{pid}/solution.lean"))
        print(f"### {pid}: {len(sols)} stored candidates")
        rows = []
        for sol in sols:
            arm = sol.split("/")[1]
            txt = Path(sol).read_text(encoding="utf-8")
            for name in names:
                r = await measure(txt, name)
                if r:
                    rows.append((arm, name, r[0], r[1]))
        rows.sort(key=lambda x: -x[2])
        for arm, name, b, t in rows:
            print(f"  {arm:10s} {name:12s} verified_prefix={b}/{t} steps")
        deep = [r for r in rows if r[2] > 2]
        print(f"  >>> candidates with verified prefix >2 steps: {len(deep)}")
    print("DONE_0")


asyncio.run(main())
