"""ST-G-nop: proof-state search, GPT-OSS actions, NO local premise (ablation)."""

from .common import GPT_OSS
from .statetree import make_state_tree


def create_agent():
    return make_state_tree(arm="ST-G-nop", action_models=[GPT_OSS], premise=False)
