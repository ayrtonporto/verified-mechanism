"""MT-NM-G: multi-theorem split, each theorem solved by G tactic-augmented repair
with a NearMiss rescue post-process (truncate best candidate to its max verified
prefix + composed finisher). Validated to close p09_b from a real near-miss.
Universal; never below the inner baseline.
"""

from .common import GPT_OSS
from .multitheorem import make_multitheorem
from .nearmiss import make_nearmiss
from .tactics import make_tactic_agent


def create_agent():
    return make_multitheorem(
        arm="MT-NM-G",
        make_inner=lambda: make_nearmiss(
            arm="MT-NM-G-slot",
            make_inner=lambda: make_tactic_agent(
                arm="MT-NM-G-inner", propose_model=GPT_OSS, repair_model=GPT_OSS
            ),
        ),
    )
