"""AgentRadar Core Sensing Engine and State Machine.

Features:
- Disaggregated per-session sensing and state tracking.
- Independent, flicker-free status evaluation for each active session/thread.
- Thread-safe background execution with zero GUI stutter.
- Accurate per-session sustained thinking timers.
"""

import time
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from loguru import logger

from ..adapters.base import AgentDefinition, AgentState, AgentStatus
from ..adapters import ALL_AGENTS, AGENTS_MAP
from .process_probe import ProcessProbe
from .network_probe import NetworkProbe
from .log_probe import LogProbe
from .session_resolver import SessionResolver
from ..win32.window_manager import find_window_by_pids_or_titles, force_bring_to_front


class AgentRadarEngine(QObject):
    """Central sensing engine and hybrid state machine for AgentRadar."""

    state_updated = Signal(dict)
    approval_alert = Signal(str, str)

    def __init__(self, poll_interval_ms: int = 3000, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.poll_interval_ms = poll_interval_ms

        self.process_probe = ProcessProbe()
        self.network_probe = NetworkProbe()
        self.log_probe = LogProbe(recent_window_seconds=15.0)
        self.session_resolver = SessionResolver(cache_ttl_seconds=2.0)

        # row_key -> AgentState
        self.states: Dict[str, AgentState] = {}
        # row_key -> timestamp when THINKING started
        self._thinking_start_times: Dict[str, float] = {}
        # agent_id -> hwnd
        self._cached_hwnds: Dict[str, int] = {}
        self._running: bool = False
        self._is_polling: bool = False

        # Initialize default offline states for all agents
        for agent_def in ALL_AGENTS:
            self.states[agent_def.id] = AgentState(
                agent_id=agent_def.id,
                display_name=agent_def.display_name,
                row_key=agent_def.id,
                status=AgentStatus.OFFLINE,
                status_text="未启动"
            )

    @Slot()
    def start(self):
        """Start the background polling worker with chained non-drifting single-shot timers."""
        logger.info(f"Starting AgentRadarEngine with {self.poll_interval_ms}ms poll interval.")
        self._running = True
        self.poll_once()

    def _schedule_next_poll(self):
        """Schedule the next sensing pass after previous pass completes, guaranteeing thread rest."""
        if self._running:
            QTimer.singleShot(self.poll_interval_ms, self.poll_once)

    @Slot()
    def stop(self):
        """Stop the background polling."""
        self._running = False
        logger.info("AgentRadarEngine stopped.")

    @Slot()
    def poll_once(self):
        """Execute one complete sensing cycle across all monitored agents and active sessions."""
        if self._is_polling or not self._running:
            return
        self._is_polling = True

        try:
            now = time.time()
            new_states: Dict[str, AgentState] = {}

            # 0. High-efficiency global process snapshot (~8ms for the whole OS)
            self.process_probe.refresh_system_snapshot()

            for agent_def in ALL_AGENTS:
                aid = agent_def.id

                # 1. Process Probe
                pids, main_pid, cpu_percent = self.process_probe.scan_agent_processes(agent_def)

                if not pids:
                    # Agent is completely offline
                    key = aid
                    self._thinking_start_times.pop(key, None)
                    self._cached_hwnds.pop(aid, None)
                    new_states[key] = AgentState(
                        agent_id=aid,
                        display_name=agent_def.display_name,
                        row_key=key,
                        status=AgentStatus.OFFLINE,
                        status_text="未启动",
                        session_name=None,
                        duration_seconds=0,
                        pid=None,
                        hwnd=None,
                        window_title=None,
                        cpu_percent=0.0,
                        active_connections=0
                    )
                    continue

                # 2. Window Discovery (lazy refresh)
                hwnd = self._cached_hwnds.get(aid)
                win_title = None
                if not hwnd:
                    res = find_window_by_pids_or_titles(pids, agent_def.window_title_keywords)
                    if res:
                        hwnd = res[0]
                        win_title = res[1]
                        self._cached_hwnds[aid] = hwnd

                # 3. Network Probe
                conn_count, _ = self.network_probe.check_network_activity(pids, agent_def)

                # 4. Resolve Active Sessions (One row per session)
                sessions = self.session_resolver.resolve_sessions(aid, win_title)
                if not sessions:
                    # Online but no specific session metadata found
                    sessions = [{
                        "session_id": "default",
                        "title": "默认工作区",
                        "is_running": False,
                        "is_approval": False,
                        "mtime": 0.0,
                        "diff": 0.0,
                        "detail": "就绪",
                    }]

                # 5. Build AgentState for each session
                for s in sessions:
                    sid = s.get("session_id", "default")
                    key = f"{aid}:{sid}" if sid != "default" else aid
                    title = s.get("title", "未命名会话")
                    is_running = s.get("is_running", False)
                    is_approval = s.get("is_approval", False)

                    # Determine status & duration
                    if is_approval:
                        status = AgentStatus.PENDING_APPROVAL
                        status_text = "等待确认"
                        duration = 0
                        self._thinking_start_times.pop(key, None)
                        self.approval_alert.emit(aid, f"{title} 等待确认")
                    elif is_running:
                        status = AgentStatus.THINKING
                        if key not in self._thinking_start_times:
                            self._thinking_start_times[key] = now
                            duration = 0
                        else:
                            duration = int(now - self._thinking_start_times[key])
                        status_text = f"工作中 ({duration}s)"
                    else:
                        status = AgentStatus.IDLE
                        status_text = "就绪 / 等待输入"
                        duration = 0
                        self._thinking_start_times.pop(key, None)

                    new_states[key] = AgentState(
                        agent_id=aid,
                        display_name=agent_def.display_name,
                        row_key=key,
                        session_id=sid,
                        session_name=title,
                        status=status,
                        status_text=status_text,
                        duration_seconds=duration,
                        pid=main_pid,
                        hwnd=hwnd,
                        window_title=win_title,
                        cpu_percent=cpu_percent,
                        active_connections=conn_count,
                        last_active_time=s.get("mtime", 0.0),
                    )

            # Clean up thinking timers for inactive keys
            for old_k in list(self._thinking_start_times.keys()):
                if old_k not in new_states:
                    self._thinking_start_times.pop(old_k, None)

            self.states = new_states
            # Notify UI subscribers
            self.state_updated.emit(self.states)
        finally:
            self._is_polling = False
            self._schedule_next_poll()
