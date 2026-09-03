"""R-Q: Qwen propose → Lean → Qwen targeted repair."""

from .common import QWEN
from .repair import make_repair_agent


def create_agent():
    return make_repair_agent(arm="R-Q", propose_model=QWEN, repair_model=QWEN)
