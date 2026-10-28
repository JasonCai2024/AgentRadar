"""Network TCP Socket and Traffic Activity Probe.
"""

from typing import Dict, List, Optional, Tuple
import psutil
from loguru import logger
from ..adapters.base import AgentDefinition


class NetworkProbe:
    """Monitors active TCP socket connections to AI endpoints and detects network streams."""

    def __init__(self):
        pass

    def check_network_activity(
        self,
        pids: List[int],
        agent_def: AgentDefinition
    ) -> Tuple[int, bool]:
        """Check whether any of the agent's processes have active ESTABLISHED TCP sockets.

        Returns:
            Tuple of (established_count, is_actively_communicating)
        """
        if not pids:
            return (0, False)

        established_count = 0
        has_api_connection = False

        for pid in pids:
            try:
                proc = psutil.Process(pid)
                connections = proc.net_connections(kind="tcp")
                for conn in connections:
                    if conn.status == "ESTABLISHED":
                        established_count += 1
                        # Remote port 443 indicates external HTTPS API/WebSocket stream
                        if conn.raddr and conn.raddr.port == 443:
                            has_api_connection = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as e:
                # Some processes or sockets may be restricted
                pass

        return (established_count, has_api_connection)
