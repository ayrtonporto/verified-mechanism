"""R-G: GPT-OSS propose → Lean → GPT-OSS targeted repair."""

from .common import GPT_OSS
from .repair import make_repair_agent


def create_agent():
    return make_repair_agent(arm="R-G", propose_model=GPT_OSS, repair_model=GPT_OSS)
