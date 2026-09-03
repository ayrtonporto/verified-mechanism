"""AT-G: auto-tactics arm — G propose → G repair, plus universal tactic sweep + menu."""

from .common import GPT_OSS
from .tactics import make_tactic_agent


def create_agent():
    return make_tactic_agent(arm="AT-G", propose_model=GPT_OSS, repair_model=GPT_OSS)
