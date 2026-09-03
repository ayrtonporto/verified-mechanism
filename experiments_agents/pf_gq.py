"""PF-GQ: planner (GPT-OSS) → formalizer (Qwen) → hardened repair (Qwen)."""

from .common import GPT_OSS, QWEN
from .planformalize import PlanFormalizeAgent


def create_agent():
    return PlanFormalizeAgent(arm="PF-GQ", planner_model=GPT_OSS, formalizer_model=QWEN)
