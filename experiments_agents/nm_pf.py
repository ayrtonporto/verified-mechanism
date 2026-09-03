"""NM-PF: single-theorem plan->formalize (G plans, Q formalizes) + NearMiss rescue."""
from .common import GPT_OSS, QWEN
from .nearmiss import make_nearmiss
from .planformalize import PlanFormalizeAgent


def create_agent():
    return make_nearmiss(
        arm="NM-PF",
        make_inner=lambda: PlanFormalizeAgent(
            arm="NM-PF-inner", planner_model=GPT_OSS, formalizer_model=QWEN),
    )
