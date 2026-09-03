"""Fixed model policy and conservative accounting prices."""

from __future__ import annotations

from dataclasses import dataclass

MODEL_A = "qwen/qwen3.5-flash-02-23"
MODEL_B = "openai/gpt-oss-120b"
ALLOWED_MODELS = frozenset({MODEL_A, MODEL_B})


@dataclass(frozen=True)
class PriceCeiling:
    """Admission-control ceiling in USD per million tokens.

    These are deliberately above the advertised prices at kit release time.
    OpenRouter's returned ``usage.cost`` is always authoritative.
    """

    input_per_million: float
    output_per_million: float


PRICE_CEILINGS = {
    MODEL_A: PriceCeiling(input_per_million=0.15, output_per_million=0.60),
    MODEL_B: PriceCeiling(input_per_million=0.10, output_per_million=0.50),
}

