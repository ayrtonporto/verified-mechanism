"""ST-GQ: proof-state search, G and Q both propose actions from the same state."""

from .common import GPT_OSS, QWEN
from .statetree import make_state_tree


def create_agent():
    return make_state_tree(arm="ST-GQ", action_models=[GPT_OSS, QWEN], premise=True)
