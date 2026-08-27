"""SF-G: sketch-and-fill, GPT-OSS proposes the skeleton and fills each hole."""

from .common import GPT_OSS
from .sketchfill import make_sketch_fill


def create_agent():
    return make_sketch_fill(arm="SF-G", propose_model=GPT_OSS, fill_model=GPT_OSS)
