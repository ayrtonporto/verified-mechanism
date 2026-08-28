"""NameGap viability probe on the strongest p09 near-proof (diagnostic, not an arm).

The baseline G p09_a proof is an essentially-correct period-3 argument that dies on a
fabricated lemma name `Nat.mod_mul_left_mod?` (the model even annotates it as a
placeholder for `n = 3*(n/3) + n%3`). This probe tests whether the name-gap thesis is
ACTIONABLE: list all errors of the stored file, then apply the obvious real lemma
(`(Nat.div_add_mod n 3).symm`) and re-check. If the proof otherwise holds, a universal
NameGapRescue mechanism (search names via #check / model, no hardcoding) is worth
building. The hardcoded substitution here is only to measure viability."""
import asyncio
from pathlib import Path
from re_harness.config import HarnessSettings
from re_harness.events import EventLogger
from re_harness.lean import LeanClient

S = HarnessSettings.from_env(n_workers=1)
ev = EventLogger(Path("namegap_p09_events.jsonl"), problem_id="namegap", secrets=(S.api_key,))
lean = LeanClient(image=S.lean_image, events=ev, session_id="namegapp09", timeout_s=120)

SRC = Path("outputs/baseline/openai/gpt-oss-120b/p09_imo1964/solution.lean").read_text(encoding="utf-8")


def errs(c):
    return [m for m in c.messages if m.get("severity") == "error"]


def show(tag, c):
    e = errs(c)
    print(f"--- {tag}: accepted={c.accepted} timed_out={c.timed_out} errors={len(e)} ---")
    for m in e[:12]:
        pos = m.get("pos", {})
        print(f"   L{pos.get('line')}:{pos.get('column')} {str(m.get('data',''))[:140].replace(chr(10),' ')}")


async def main():
    c0 = await lean.check_file(SRC, timeout_s=180)
    show("ORIGINAL", c0)

    # obvious real replacement for the fabricated decomposition lemma
    fixed = SRC.replace(
        "(Nat.mod_mul_left_mod? ).symm   -- `Nat.mod_mul_left_mod?` is a placeholder for the standard lemma `Nat.mod_mul_left_mod` giving the decomposition",
        "(Nat.div_add_mod n 3).symm",
    ).replace("(Nat.mod_mul_left_mod? ).symm", "(Nat.div_add_mod n 3).symm")
    changed = fixed != SRC
    print(f"\n[substitution applied: {changed}]")
    c1 = await lean.check_file(fixed, timeout_s=180)
    show("AFTER Nat.div_add_mod fix", c1)
    Path("p09_namegap_fixed.lean").write_text(fixed, encoding="utf-8")
    print("DONE_0")


asyncio.run(main())
