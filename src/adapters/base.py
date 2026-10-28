"""Base Agent Definitions and Status Models for AgentRadar.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set
import os


class AgentStatus(Enum):
    OFFLINE = "OFFLINE"                    # Gray: Process not running
    IDLE = "IDLE"                          # Blue/Muted: Process alive, waiting for prompt
    THINKING = "THINKING"                  # Green: Running/reasoning, executing tools or API calls
    PENDING_APPROVAL = "PENDING_APPROVAL"  # Yellow: Awaiting user confirmation / authorization


@dataclass
class AgentDefinition:
    """Static configuration and heuristic probes definition for a supported agent."""
    id: str
    display_name: str
    icon_symbol: str
    process_names: List[str]
    window_title_keywords: List[str]
    api_domains: List[str] = field(default_factory=list)
    log_dirs: List[str] = field(default_factory=list)
    approval_patterns: List[str] = field(default_factory=list)
    completion_patterns: List[str] = field(default_factory=list)

    def resolve_log_dirs(self) -> List[str]:
        """Expand user home and environment variables for log dirs."""
        resolved = []
        for d in self.log_dirs:
            exp = os.path.expandvars(os.path.expanduser(d))
            if os.path.isdir(exp):
                resolved.append(exp)
        return resolved


@dataclass
class AgentState:
    """Dynamic live runtime state of an agent or active agent session."""
    agent_id: str
    display_name: str
    status: AgentStatus = AgentStatus.OFFLINE
    status_text: str = "未启动"
    session_name: Optional[str] = None
    duration_seconds: int = 0
    pid: Optional[int] = None
    hwnd: Optional[int] = None
    window_title: Optional[str] = None
    cpu_percent: float = 0.0
    active_connections: int = 0
    last_active_time: float = 0.0
    last_log_mtime: float = 0.0
    row_key: str = ""
    session_id: Optional[str] = None
