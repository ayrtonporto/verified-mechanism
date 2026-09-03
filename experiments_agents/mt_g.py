"""MT-G: multi-theorem wrapper, each theorem solved by G tactic-augmented repair.

Universal: on single-theorem problems it delegates unchanged to the inner agent; on
multi-theorem problems (e.g. p09_imo1964) it solves each theorem independently
(sweep + tactic-menu propose/repair) and reassembles. Never scores below the inner
baseline (whole-file fallback).
"""

from .common import GPT_OSS
from .multitheorem import make_multitheorem
from .tactics import make_tactic_agent


def create_agent():
    return make_multitheorem(
        arm="MT-G",
        make_inner=lambda: make_tactic_agent(
            arm="MT-G-inner", propose_model=GPT_OSS, repair_model=GPT_OSS
        ),
    )
