"""Configuration loading with safe local ``.env`` behavior."""

from __future__ import annotations

import os
import math
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

# A tag may be supplied during local image development with LEAN_IMAGE.
DEFAULT_LEAN_IMAGE = (
    "ghcr.io/verifiedmechanisms/re-takehome-lean"
    "@sha256:ee48287cd31c0a7df572093a879ed7289c2f01fec6c7af8716c605fc8c670c39"
)


def load_local_env(root: Path = ROOT) -> None:
    """Load ``root/.env`` without overriding an exported judge environment."""

    load_dotenv(root / ".env", override=False)


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value < 1:
        raise ValueError(f"{name} must be >= 1, got {value}")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be > 0, got {value}")
    return value


@dataclass(frozen=True)
class HarnessSettings:
    api_key: str
    lean_image: str
    budget_usd: float
    time_limit_s: float
    n_workers: int
    lean_check_timeout_s: int = 120
    comparator_timeout_s: int = 180
    verify_reserve_s: int = 120

    def __post_init__(self) -> None:
        if not self.lean_image or self.lean_image.startswith("-") or any(
            character.isspace() for character in self.lean_image
        ):
            raise ValueError("lean_image must be a non-empty Docker image reference")
        for name in (
            "n_workers", "lean_check_timeout_s", "comparator_timeout_s", "verify_reserve_s"
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")
        for name in ("budget_usd", "time_limit_s"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")

    @classmethod
    def from_env(cls, *, n_workers: int | None = None) -> "HarnessSettings":
        load_local_env()
        return cls(
            api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
            lean_image=os.environ.get("LEAN_IMAGE", DEFAULT_LEAN_IMAGE).strip(),
            budget_usd=_positive_float("VM_BUDGET_USD", 1.0),
            time_limit_s=_positive_float("VM_TIME_LIMIT_S", 28800.0),
            n_workers=n_workers if n_workers is not None else _positive_int("N_WORKERS", 1),
            lean_check_timeout_s=_positive_int("LEAN_CHECK_TIMEOUT_S", 120),
            comparator_timeout_s=_positive_int("COMPARATOR_TIMEOUT_S", 180),
            verify_reserve_s=_positive_int("VM_VERIFY_RESERVE_S", 120),
        )
