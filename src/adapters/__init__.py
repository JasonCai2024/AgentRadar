"""Adapters registry for all supported AI agents.
"""

from typing import List, Dict
from .base import AgentDefinition, AgentState, AgentStatus
from .antigravity import ANTIGRAVITY_DEF
from .qoder import QODER_DEF
from .minimax_code import MINIMAX_CODE_DEF
from .codex import CODEX_DEF
from .workbuddy import WORKBUDDY_DEF

ALL_AGENTS: List[AgentDefinition] = [
    ANTIGRAVITY_DEF,
    QODER_DEF,
    MINIMAX_CODE_DEF,
    CODEX_DEF,
    WORKBUDDY_DEF,
]

AGENTS_MAP: Dict[str, AgentDefinition] = {
    agent.id: agent for agent in ALL_AGENTS
}

__all__ = [
    "AgentDefinition",
    "AgentState",
    "AgentStatus",
    "ALL_AGENTS",
    "AGENTS_MAP",
    "ANTIGRAVITY_DEF",
    "QODER_DEF",
    "MINIMAX_CODE_DEF",
    "CODEX_DEF",
    "WORKBUDDY_DEF",
]
