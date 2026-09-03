"""H-GQ: GPT-OSS propose → Lean → Qwen repair (same caps as R)."""

from .common import GPT_OSS, QWEN
from .repair import make_repair_agent


def create_agent():
    return make_repair_agent(arm="H-GQ", propose_model=GPT_OSS, repair_model=QWEN)
