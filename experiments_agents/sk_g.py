"""SK-G: skeleton/sorry-first arm — GPT-OSS, with extra repair turns to fill holes."""

from .common import GPT_OSS
from .skeleton import SkeletonAgent


def create_agent():
    return SkeletonAgent(
        arm="SK-G", propose_model=GPT_OSS, repair_model=GPT_OSS, max_repair_turns=6
    )
