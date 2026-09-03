"""NMBANK-G: verified-lemma-bank multi-theorem, each slot solved by G tactic repair
+ NearMiss rescue, with cross-slot lemma sharing (pass 2). The universal path to a
legitimate p09 solve (p09_b's periodicity have → offered to p09_a).
"""

from .common import GPT_OSS
from .lemmabank import make_lemma_bank
from .nearmiss import make_nearmiss
from .tactics import make_tactic_agent


def create_agent():
    return make_lemma_bank(
        arm="NMBANK-G",
        make_inner=lambda: make_nearmiss(
            arm="NMBANK-G-slot",
            make_inner=lambda: make_tactic_agent(
                arm="NMBANK-G-inner", propose_model=GPT_OSS, repair_model=GPT_OSS
            ),
        ),
    )
