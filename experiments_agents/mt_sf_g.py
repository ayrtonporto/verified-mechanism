"""MT-SF-G: multi-theorem wrapper whose per-theorem solver is sketch-and-fill (G).

Composes the two new levers: split independent theorems (p09), then attack each one
by verified `have`-decomposition. Falls back to whole-file repair, never below
baseline.
"""

from .common import GPT_OSS
from .multitheorem import make_multitheorem
from .sketchfill import make_sketch_fill


def create_agent():
    return make_multitheorem(
        arm="MT-SF-G",
        make_inner=lambda: make_sketch_fill(
            arm="MT-SF-G-inner", propose_model=GPT_OSS, fill_model=GPT_OSS
        ),
    )
