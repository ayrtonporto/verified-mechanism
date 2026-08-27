"""NMBANK-PF: verified-lemma-bank multi-theorem with a plan->formalize proposer
(planner=G, formalizer=Q — the pairing that produced p09_b's 8/11 verified prefix
offline) + NearMiss rescue. Best-odds universal path to a legitimate p09 solve.
"""

from .common import GPT_OSS, QWEN
from .lemmabank import make_lemma_bank
from .nearmiss import make_nearmiss
from .planformalize import PlanFormalizeAgent


def create_agent():
    return make_lemma_bank(
        arm="NMBANK-PF",
        make_inner=lambda: make_nearmiss(
            arm="NMBANK-PF-slot",
            make_inner=lambda: PlanFormalizeAgent(
                arm="NMBANK-PF-inner", planner_model=GPT_OSS, formalizer_model=QWEN
            ),
        ),
    )
