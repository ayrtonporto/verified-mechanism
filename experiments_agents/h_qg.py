"""H-QG: Qwen propose → Lean → GPT-OSS repair (same caps as R)."""

from .common import GPT_OSS, QWEN
from .repair import make_repair_agent


def create_agent():
    return make_repair_agent(arm="H-QG", propose_model=QWEN, repair_model=GPT_OSS)
