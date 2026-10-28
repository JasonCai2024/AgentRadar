"""Log and Session Activity Probe for AgentRadar.

Monitors real conversation transcript streams and database statuses across
all 5 GUI frameworks to determine genuine AI thinking/working vs idle states.
Explicitly detects task completion markers to immediately transition to IDLE,
filtering out all background telemetry, sentry, LSP, and chromium noise.
"""

import os
import json
import time
import sqlite3
from typing import Optional, Tuple, Dict
from loguru import logger
from ..adapters.base import AgentDefinition


class LogProbe:
    """Monitors genuine conversation turn progression and detects completion/approval states."""

    def __init__(self, recent_window_seconds: float = 15.0):
        self.recent_window_seconds = recent_window_seconds
        # agent_id -> last observed max mtime
        self._last_seen_mtimes: Dict[str, float] = {}

    def inspect_logs(
        self,
        agent_def: AgentDefinition
    ) -> Tuple[float, bool, bool, bool, Optional[str], bool]:
        """Inspect genuine conversation stores and return state indicators.

        Returns:
            Tuple of:
            - latest_mtime: float
            - is_new_write: bool (timestamp advanced since last check)
            - is_recent_write: bool (actively generating within recent_window_seconds)
            - is_approval_pending: bool (waiting for user permission / input)
            - matched_pattern: Optional[str]
            - is_task_completed: bool (explicitly marked done / idle)
        """
        aid = agent_def.id
        now = time.time()

        if aid == "antigravity":
            return self._inspect_antigravity(agent_def, now)
        elif aid == "codex":
            return self._inspect_codex(agent_def, now)
        elif aid == "minimax_code":
            return self._inspect_minimax(agent_def, now)
        elif aid == "qoder":
            return self._inspect_qoder(agent_def, now)
        elif aid == "workbuddy":
            return self._inspect_workbuddy(agent_def, now)

        return (0.0, False, False, False, None, True)

    def _inspect_antigravity(
        self, agent_def: AgentDefinition, now: float
    ) -> Tuple[float, bool, bool, bool, Optional[str], bool]:
        """Inspect AntiGravity via its native conversation_summaries.db state.

        Completely eliminates intermediate-step flickering by checking the overarching
        cascade status ('CASCADE_RUN_STATUS_RUNNING' / 'not_fully_idle').
        """
        db = os.path.expanduser(r"~/.gemini/antigravity/conversation_summaries.db")
        if os.path.exists(db):
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute(
                    "SELECT status, not_fully_idle, last_modified_time "
                    "FROM conversation_summaries "
                    "WHERE killed = 0 "
                    "ORDER BY last_modified_time DESC LIMIT 10;"
                )
                rows = cur.fetchall()
                conn.close()

                is_running = any(
                    r[0] == "CASCADE_RUN_STATUS_RUNNING" or r[1] == 1
                    for r in rows
                )

                mtime = 0.0
                if rows and rows[0][2]:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(rows[0][2].replace("Z", "+00:00"))
                        mtime = dt.timestamp()
                    except Exception:
                        pass

                prev = self._last_seen_mtimes.get("antigravity", 0.0)
                is_new = (mtime > prev) and (prev > 0.0)
                self._last_seen_mtimes["antigravity"] = mtime

                if is_running:
                    # Steady, sustained working state throughout entire turn
                    return (mtime, is_new, True, False, None, False)
                else:
                    return (mtime, is_new, False, False, None, True)
            except Exception as e:
                logger.warning(f"Failed to query AntiGravity db: {e}")

        return (0.0, False, False, False, None, True)

    def _inspect_codex(
        self, agent_def: AgentDefinition, now: float
    ) -> Tuple[float, bool, bool, bool, Optional[str], bool]:
        """Inspect OpenAI Codex rollout-*.jsonl sessions using targeted date folders."""
        sessions_dir = os.path.expanduser(r"~/.codex/sessions")
        if not os.path.exists(sessions_dir):
            return (0.0, False, False, False, None, True)

        from datetime import datetime, timedelta
        today = datetime.now().date()
        target_dirs = [
            os.path.join(sessions_dir, (today - timedelta(days=i)).strftime("%Y/%m/%d"))
            for i in range(3)
        ]

        latest_file = None
        max_mtime = 0.0

        for d in target_dirs:
            if os.path.exists(d):
                try:
                    for entry in os.scandir(d):
                        if entry.name.endswith(".jsonl") and entry.name.startswith("rollout-"):
                            try:
                                m = entry.stat().st_mtime
                                if m > max_mtime:
                                    max_mtime = m
                                    latest_file = entry.path
                            except OSError:
                                pass
                except OSError:
                    pass

        if not latest_file:
            return (0.0, False, False, False, None, True)

        prev_mtime = self._last_seen_mtimes.get("codex", 0.0)
        is_new_write = (max_mtime > prev_mtime) and (prev_mtime > 0.0)
        self._last_seen_mtimes["codex"] = max_mtime
        time_diff = now - max_mtime

        tail = self._read_tail(latest_file, max_bytes=8192)
        is_approval, matched_pat = self._check_approval(tail, agent_def.approval_patterns)

        lines = [l.strip() for l in tail.splitlines() if l.strip()]
        if lines:
            try:
                last_obj = json.loads(lines[-1])
                payload = last_obj.get("payload", {})
                ptype = payload.get("type") if isinstance(payload, dict) else ""

                # Explicit turn completions / idle markers in Codex
                if ptype in ["task_complete", "turn_aborted", "thread_settings_applied", "item_completed"]:
                    return (max_mtime, is_new_write, False, is_approval, matched_pat, True)

                # Active turn in progress
                if time_diff <= self.recent_window_seconds:
                    return (max_mtime, is_new_write, True, is_approval, matched_pat, False)
            except Exception:
                pass

        is_completed = time_diff > self.recent_window_seconds
        return (max_mtime, is_new_write, not is_completed, is_approval, matched_pat, is_completed)

    def _inspect_minimax(
        self, agent_def: AgentDefinition, now: float
    ) -> Tuple[float, bool, bool, bool, Optional[str], bool]:
        """Inspect MiniMax Code via runtime SQLite state and running background tasks."""
        db = os.path.expanduser(r"~/.minimax/v2/sqlite/runtime-state.sqlite")
        if os.path.exists(db):
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cur = conn.cursor()
                # 1. Check latest session status ('started' indicates active working)
                cur.execute(
                    "SELECT status, updated_at_ms FROM local_runtime_sessions "
                    "WHERE (archived = 0 OR archived IS NULL) "
                    "ORDER BY updated_at_ms DESC LIMIT 1;"
                )
                row = cur.fetchone()

                # 2. Check running background tasks
                cur.execute(
                    "SELECT count(1) FROM local_runtime_background_tasks WHERE status = 'running';"
                )
                running_tasks = cur.fetchone()[0]
                conn.close()

                if row:
                    mst, mtime_ms = row[0], row[1]
                    mtime_s = mtime_ms / 1000.0 if mtime_ms else 0.0
                    prev = self._last_seen_mtimes.get("minimax_code", 0.0)
                    is_new = (mtime_s > prev) and (prev > 0.0)
                    self._last_seen_mtimes["minimax_code"] = mtime_s

                    # In MiniMax, 'started', 'busy', 'running', 'thinking', 'generating' mean working!
                    is_working = (mst in ["started", "busy", "running", "thinking", "generating"]) or (running_tasks > 0)
                    if is_working:
                        return (mtime_s, is_new, True, False, None, False)
                    elif mst == "idle":
                        return (mtime_s, is_new, False, False, None, True)
            except Exception as e:
                logger.warning(f"Failed to query MiniMax db: {e}")

        return (0.0, False, False, False, None, True)

    def _inspect_qoder(
        self, agent_def: AgentDefinition, now: float
    ) -> Tuple[float, bool, bool, bool, Optional[str], bool]:
        """Inspect Qoder chat history."""
        p_dir = os.path.expanduser(r"~/.qoder/projects")
        latest_file = None
        max_mtime = 0.0

        if os.path.exists(p_dir):
            for root, _, files in os.walk(p_dir):
                for f in files:
                    if f.endswith(".jsonl"):
                        fp = os.path.join(root, f)
                        try:
                            m = os.path.getmtime(fp)
                            if m > max_mtime:
                                max_mtime = m
                                latest_file = fp
                        except OSError:
                            pass

        if not latest_file:
            return (0.0, False, False, False, None, True)

        prev = self._last_seen_mtimes.get("qoder", 0.0)
        is_new = (max_mtime > prev) and (prev > 0.0)
        self._last_seen_mtimes["qoder"] = max_mtime
        time_diff = now - max_mtime

        tail = self._read_tail(latest_file, max_bytes=4096)
        is_approval, matched_pat = self._check_approval(tail, agent_def.approval_patterns)

        if time_diff <= self.recent_window_seconds:
            return (max_mtime, is_new, True, is_approval, matched_pat, False)

        return (max_mtime, is_new, False, is_approval, matched_pat, True)

    def _inspect_workbuddy(
        self, agent_def: AgentDefinition, now: float
    ) -> Tuple[float, bool, bool, bool, Optional[str], bool]:
        """Inspect WorkBuddy session activity directly via SQLite database."""
        db = os.path.expanduser(r"~/.workbuddy/workbuddy.db")
        if not os.path.exists(db):
            return (0.0, False, False, False, None, True)

        max_mtime = 0.0
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT max(updated_at) FROM sessions WHERE deleted_at IS NULL;")
            r = cur.fetchone()
            conn.close()
            if r and r[0]:
                val = r[0]
                if isinstance(val, (int, float)):
                    max_mtime = float(val) if val < 1e11 else (val / 1000.0)
                elif isinstance(val, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                        max_mtime = dt.timestamp()
                    except Exception:
                        pass
        except Exception:
            pass

        if max_mtime == 0.0:
            return (0.0, False, False, False, None, True)

        prev = self._last_seen_mtimes.get("workbuddy", 0.0)
        is_new = (max_mtime > prev) and (prev > 0.0)
        self._last_seen_mtimes["workbuddy"] = max_mtime
        time_diff = now - max_mtime

        if time_diff <= self.recent_window_seconds:
            return (max_mtime, is_new, True, False, None, False)

        return (max_mtime, is_new, False, False, None, True)

    def _check_approval(self, tail_content: str, patterns: list) -> Tuple[bool, Optional[str]]:
        if not tail_content:
            return (False, None)
        lower = tail_content.lower()
        for pat in patterns:
            if pat.lower() in lower:
                return (True, pat)
        return (False, None)

    def _read_tail(self, file_path: str, max_bytes: int = 8192) -> str:
        """Safely read the last bytes of a file."""
        try:
            size = os.path.getsize(file_path)
            if size == 0:
                return ""
            read_size = min(size, max_bytes)
            with open(file_path, "rb") as f:
                f.seek(size - read_size)
                data = f.read(read_size)
                return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""
