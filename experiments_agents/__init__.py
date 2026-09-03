"""Science-arm package: S / R / H factories for harness --agent module:factory.

Layout (one module per arm so output dirs stay distinct):
  experiments_agents.s_q:create_agent
  experiments_agents.s_g:create_agent
  experiments_agents.r_q:create_agent
  experiments_agents.r_g:create_agent
  experiments_agents.h_qg:create_agent
  experiments_agents.h_gq:create_agent

S uses baselines.simple_agent loop (baseline-faithful).
R/H share TargetedRepairAgent; H only swaps repair_model.
"""

from __future__ import annotations

from .common import GPT_OSS, QWEN
from .repair import TargetedRepairAgent, make_repair_agent
from .solo import SoloBaselineAgent, create_s_g, create_s_q

__all__ = [
    "QWEN",
    "GPT_OSS",
    "SoloBaselineAgent",
    "TargetedRepairAgent",
    "create_s_q",
    "create_s_g",
    "make_repair_agent",
]
