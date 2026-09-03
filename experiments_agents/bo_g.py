"""BON-G: diverse best-of-N sampling arm — GPT-OSS."""

from .bestofn import BestOfNAgent
from .common import GPT_OSS


def create_agent():
    return BestOfNAgent(arm="BON-G", model=GPT_OSS)
