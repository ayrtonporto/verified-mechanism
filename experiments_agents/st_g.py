"""ST-G: verified proof-state search, GPT-OSS actions + local Mathlib premises."""

from .common import GPT_OSS
from .statetree import make_state_tree


def create_agent():
    return make_state_tree(arm="ST-G", action_models=[GPT_OSS], premise=True)
