"""Lean-only capability + power probe for grind and modern automation.
No model calls. Confirms grind exists on the image and tests it on the 3 hard
problems and a few natural subgoals, plus suggestion-tactic syntax."""
import asyncio, sys
from pathlib import Path
from re_harness.config import HarnessSettings
from re_harness.events import EventLogger
from re_harness.lean import LeanClient

S = HarnessSettings.from_env(n_workers=1)
ev = EventLogger(Path("probe_grind_events.jsonl"), problem_id="probe", secrets=(S.api_key,))
lean = LeanClient(image=S.lean_image, events=ev, session_id="probe-grind", timeout_s=180)

IMPORT = "import Mathlib\n"
def rd(pid):
    return Path(f"sets/S_dev/{pid}/challenge.lean").read_text(encoding="utf-8")

# whole-problem grind attempts (replace sorry with a tactic)
def fill(pid, tac):
    src = rd(pid)
    return src.replace("sorry", tac)

CASES = [
    ("grind_exists", IMPORT + "example : True := by grind\n"),
    ("grind_arith",  IMPORT + "example (a b : Nat) (h : a = b) : b = a := by grind\n"),
    ("grindq_exists",IMPORT + "example (a b : Nat) (h : a = b) : b = a := by grind?\n"),
    ("p09a_grind",   fill("p09_imo1964", "grind")),
    ("p09b_grind",   fill("p09_imo1964", "grind")),
    ("rmo2_grind",   fill("rmo_2000_2", "grind")),
    ("rmo3_grind",   fill("rmo_2000_3", "grind")),
    # natural p09_a key subgoal (periodicity), as an isolated example
    ("p09_periodicity", IMPORT + "example (n : Nat) : 2^n % 7 = 2^(n % 3) % 7 := by grind\n"),
    ("p09_periodicity_omega", IMPORT + "example (n : Nat) : 2^n % 7 = 2^(n % 3) % 7 := by omega\n"),
    ("exactq_syntax", IMPORT + "example (a b : Nat) (h : a = b) : b = a := by exact? \n"),
]

async def main():
    for name, src in CASES:
        try:
            c = await lean.check_file(src, timeout_s=180)
            errs = [m for m in c.messages if m.get("severity")=="error"]
            status = "ACCEPTED" if c.accepted else ("TIMEOUT" if c.timed_out else f"ERR({len(errs)})")
            first = (errs[0].get("data","")[:120].replace("\n"," ")) if errs else ""
            print(f"{name:24s} {status:12s} {first}")
        except Exception as e:
            print(f"{name:24s} EXCEPTION {type(e).__name__}: {e}")
    lean.close() if hasattr(lean,"close") else None

asyncio.run(main())
