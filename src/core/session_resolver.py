"""Active Session Title and Multi-Session Resolver for AgentRadar.

Extracts real active conversations, threads, and per-session runtime states
across all 5 GUI agents. Provides disaggregated session resolution so each
active session can be monitored on its own dedicated row in the HUD.
"""

import os
import sqlite3
import json
import time
import glob
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List


class SessionResolver:
    """Extracts and caches active sessions and topic titles for each agent."""

    def __init__(self, cache_ttl_seconds: float = 2.0):
        self.cache_ttl = cache_ttl_seconds
        # agent_id -> (timestamp, List[Dict])
        self._sessions_cache: Dict[str, Tuple[float, List[Dict]]] = {}

    def resolve_sessions(self, agent_id: str, default_window_title: Optional[str] = None) -> List[Dict]:
        """Resolve all active sessions for the given agent.

        Returns:
            List of dicts: [
                {
                    "session_id": str,
                    "title": str,
                    "is_running": bool,
                    "is_approval": bool,
                    "mtime": float,
                    "diff": float,
                    "detail": str,
                }, ...
            ]
        """
        now = time.time()
        cached = self._sessions_cache.get(agent_id)
        if cached and (now - cached[0] < self.cache_ttl):
            return cached[1]

        sessions = []
        try:
            if agent_id == "antigravity":
                sessions = self.resolve_antigravity_sessions()
            elif agent_id == "codex":
                sessions = self.resolve_codex_sessions()
            elif agent_id == "minimax_code":
                sessions = self.resolve_minimax_sessions()
            elif agent_id == "qoder":
                sessions = self.resolve_qoder_sessions()
            elif agent_id == "workbuddy":
                sessions = self.resolve_workbuddy_sessions()
        except Exception:
            sessions = []

        # Fallback if no session found but window title exists
        if not sessions and default_window_title and " - " in default_window_title:
            cleaned = default_window_title.split(" - ")[0].strip()
            if cleaned:
                sessions = [{
                    "session_id": "default",
                    "title": cleaned,
                    "is_running": False,
                    "is_approval": False,
                    "mtime": 0.0,
                    "diff": 0.0,
                    "detail": "就绪",
                }]

        self._sessions_cache[agent_id] = (now, sessions)
        return sessions

    def resolve_antigravity_sessions(self, max_sessions: int = 10) -> List[Dict]:
        """Resolve active sessions for Google AntiGravity with per-session status."""
        now = time.time()
        db = os.path.expanduser(r"~/.gemini/antigravity/conversation_summaries.db")

        # 1. Read metadata from conversation_summaries.db
        meta_map = {}
        if os.path.exists(db):
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute("""
                    SELECT conversation_id, title, preview, status, not_fully_idle, last_modified_time
                    FROM conversation_summaries
                    WHERE killed = 0
                    ORDER BY last_modified_time DESC LIMIT 50;
                """)
                for cid, title, preview, db_st, not_idle, mtime_str in cur.fetchall():
                    clean_title = (title or preview or "未命名会话").strip()
                    meta_map[cid] = {
                        "title": clean_title,
                        "db_st": db_st,
                        "not_idle": not_idle,
                    }
                conn.close()
            except Exception:
                pass

        # 2. Check transcript.jsonl actual file mtimes
        # Note: Windows NTFS does not update folder st_mtime on nested file writes,
        # so we scan transcript.jsonl file mtimes directly to ensure live session tracking.
        brain_dir = os.path.expanduser(r"~/.gemini/antigravity/brain")
        candidates = []
        if os.path.exists(brain_dir):
            try:
                for cid in os.listdir(brain_dir):
                    tpath = os.path.join(brain_dir, cid, ".system_generated", "logs", "transcript.jsonl")
                    try:
                        mtime = os.path.getmtime(tpath)
                        diff = now - mtime
                        # Only consider sessions active or updated within the last 7 days
                        if diff < 86400 * 7:
                            candidates.append((cid, mtime, diff, tpath))
                    except OSError:
                        pass
            except Exception:
                pass

        # Sort by actual file mtime descending (most recent first)
        candidates.sort(key=lambda x: x[1], reverse=True)

        running_sessions = []
        idle_sessions = []

        for cid, mtime, diff, tpath in candidates[:30]:
            meta = meta_map.get(cid, {})
            title = meta.get("title", f"AntiGravity ({cid[:8]})")
            db_st = meta.get("db_st", "")
            not_idle = meta.get("not_idle", 0)

            is_finished = True
            is_approval = False
            last_stype = ""
            st = ""
            tools = []

            try:
                sz = os.path.getsize(tpath)
                if sz > 0:
                    with open(tpath, "rb") as f:
                        f.seek(max(0, sz - 65536))
                        tail = f.read().decode("utf-8", errors="ignore")
                    lines = [l.strip() for l in tail.splitlines() if l.strip()]
                    for l in reversed(lines):
                        try:
                            last_step = json.loads(l)
                            st = last_step.get("status")
                            last_stype = last_step.get("type", "")
                            tools = last_step.get("tool_calls", [])

                            # Turn finishes only when model produces PLANNER_RESPONSE with 0 tool calls
                            is_finished = (st == "DONE" and last_stype == "PLANNER_RESPONSE" and len(tools) == 0)

                            # Check for user input / approval requests (e.g., ask_question)
                            for tc in tools:
                                if isinstance(tc, dict) and "ask_question" in str(tc).lower():
                                    is_approval = True
                                    break
                            break
                        except Exception:
                            continue
            except Exception:
                pass

            is_running = (db_st == "CASCADE_RUN_STATUS_RUNNING") or (not_idle == 1) or (not is_finished and diff <= 180.0)

            session_obj = {
                "session_id": cid,
                "title": title,
                "is_running": is_running,
                "is_approval": is_approval,
                "mtime": mtime,
                "diff": diff,
                "detail": f"Step: {last_stype}" if is_running else "就绪",
            }

            if is_running or is_approval:
                running_sessions.append(session_obj)
            else:
                idle_sessions.append(session_obj)

        final_sessions = list(running_sessions)
        for s in idle_sessions:
            if len(final_sessions) >= max(max_sessions, len(running_sessions)):
                break
            final_sessions.append(s)

        return final_sessions

    def resolve_codex_sessions(self, max_sessions: int = 10) -> List[Dict]:
        """Resolve active sessions for OpenAI Codex with per-session status."""
        sdir = os.path.expanduser(r"~/.codex/sessions")
        if not os.path.exists(sdir):
            return []
        now = time.time()
        rollouts = []

        # High-performance targeted scan: check recent 7 days subdirectories (YYYY/MM/DD)
        today = datetime.now().date()
        target_dirs = [
            os.path.join(sdir, (today - timedelta(days=i)).strftime("%Y/%m/%d"))
            for i in range(7)
        ]
        for d in target_dirs:
            if os.path.exists(d):
                try:
                    for entry in os.scandir(d):
                        if entry.name.endswith(".jsonl") and entry.name.startswith("rollout-"):
                            try:
                                stat = entry.stat()
                                if now - stat.st_mtime < 86400 * 7:
                                    rollouts.append((entry.path, stat.st_mtime))
                            except OSError:
                                pass
                except OSError:
                    pass

        rollouts.sort(key=lambda x: x[1], reverse=True)

        idx_path = os.path.expanduser(r"~/.codex/session_index.jsonl")
        id_map = {}
        if os.path.exists(idx_path):
            try:
                with open(idx_path, "r", encoding="utf-8", errors="ignore") as f:
                    for l in f:
                        if l.strip():
                            d = json.loads(l)
                            id_map[d.get("id")] = d.get("thread_name") or d.get("title")
            except Exception:
                pass

        running_sessions = []
        idle_sessions = []
        seen = set()

        for fp, mtime in rollouts[:15]:
            diff = now - mtime
            try:
                sz = os.path.getsize(fp)
                if sz == 0:
                    continue
                # Read head for meta, and tail 64KB for latest event
                with open(fp, "rb") as f:
                    first_line = f.readline().decode("utf-8", errors="ignore")
                    f.seek(max(0, sz - 65536))
                    tail = f.read().decode("utf-8", errors="ignore")

                first_obj = json.loads(first_line) if first_line.strip() else {}
                tail_lines = [l.strip() for l in tail.splitlines() if l.strip()]
                if not tail_lines:
                    continue

                meta_id = first_obj.get("payload", {}).get("session_id") if first_obj.get("type") == "session_meta" else None
                sid = None
                is_finished = None
                ptype = ""

                # Reverse parse tail lines safely
                for l in reversed(tail_lines):
                    try:
                        obj = json.loads(l)
                        payload = obj.get("payload", {})
                        if not sid and isinstance(payload, dict):
                            sid = payload.get("thread_id") or payload.get("session_id")

                        p_type = payload.get("type") if isinstance(payload, dict) else ""
                        obj_type = obj.get("type")

                        # Significant completion markers
                        if p_type in ["task_complete", "turn_aborted"]:
                            is_finished = True
                            ptype = p_type
                            break
                        elif p_type in ["task_started", "custom_tool_call", "custom_tool_call_output", "reasoning", "message"] or obj_type in ["response_item", "token_usage_record"]:
                            is_finished = False
                            ptype = p_type or obj_type
                            break
                    except Exception:
                        continue

                sid = sid or meta_id or os.path.basename(fp)
                title = (id_map.get(sid) or id_map.get(meta_id) or "Codex 工作会话").strip()

                if sid in seen or title in seen:
                    continue
                seen.add(sid)
                seen.add(title)

                if is_finished is True:
                    is_running = (diff <= 4.0)
                elif is_finished is False:
                    is_running = (diff <= 300.0)
                else:
                    is_running = (diff <= 60.0)

                session_obj = {
                    "session_id": sid,
                    "title": title,
                    "is_running": is_running,
                    "is_approval": False,
                    "mtime": mtime,
                    "diff": diff,
                    "detail": f"Event: {ptype}" if is_running else "就绪",
                }

                if is_running:
                    running_sessions.append(session_obj)
                else:
                    idle_sessions.append(session_obj)
            except Exception:
                pass

        final_sessions = list(running_sessions)
        for s in idle_sessions:
            if len(final_sessions) >= max(max_sessions, len(running_sessions)):
                break
            final_sessions.append(s)

        return final_sessions

    def resolve_minimax_sessions(self, max_sessions: int = 10) -> List[Dict]:
        """Resolve active sessions for MiniMax Code with runtime SQLite check."""
        db = os.path.expanduser(r"~/.minimax/v2/sqlite/runtime-state.sqlite")
        if not os.path.exists(db):
            return []
        now = time.time()
        sessions = []
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("""
                SELECT session_id, title, status, updated_at_ms
                FROM local_runtime_sessions
                WHERE (archived = 0 OR archived IS NULL)
                ORDER BY updated_at_ms DESC LIMIT 15;
            """)
            rows = cur.fetchall()

            for sid, title, mst, mtime_ms in rows:
                diff = (now - mtime_ms / 1000.0) if mtime_ms else 999999.0

                cur.execute("""
                    SELECT role, data_json, created_at_ms
                    FROM local_runtime_message_rows
                    WHERE session_id = ?
                    ORDER BY id DESC LIMIT 1;
                """, (sid,))
                msg_row = cur.fetchone()

                is_running = False
                detail = "就绪"
                if msg_row:
                    m_role, m_data_json, m_created_ms = msg_row
                    m_diff = (now - m_created_ms / 1000.0) if m_created_ms else 999999.0
                    m_data = json.loads(m_data_json) if m_data_json else {}
                    finish_reason = m_data.get("finish_reason")
                    tool_calls = m_data.get("tool_calls", [])

                    if m_role == "user":
                        is_running = (m_diff <= 120.0)
                        detail = "工作中 (模型生成中)"
                    elif m_role == "assistant":
                        if finish_reason in ["toolUse", "tool_use"] or len(tool_calls) > 0:
                            is_running = (m_diff <= 120.0)
                            detail = "工作中 (工具调用中)"
                        elif finish_reason in ["stop", "end_turn"]:
                            is_running = False
                            detail = "就绪"
                        else:
                            is_running = (m_diff <= 60.0)
                            detail = "工作中 (思考中)"

                if not is_running and mst in ["busy", "running", "thinking", "generating"] and diff <= 60.0:
                    is_running = True
                    detail = "工作中"

                # Filter: include if running, or updated recently (<= 3 hours), up to max_sessions
                if is_running or diff <= 10800.0 or len(sessions) < max_sessions:
                    sessions.append({
                        "session_id": sid,
                        "title": (title or "MiniMax 工作会话").strip(),
                        "is_running": is_running,
                        "is_approval": False,
                        "mtime": (mtime_ms / 1000.0) if mtime_ms else 0.0,
                        "diff": diff,
                        "detail": detail if is_running else "就绪",
                    })

                if len(sessions) >= max_sessions and not is_running:
                    break

            conn.close()
        except Exception:
            pass

        return sessions

    def resolve_qoder_sessions(self, max_sessions: int = 10) -> List[Dict]:
        """Resolve active sessions for Qoder with real-time conversational turn progression."""
        now = time.time()

        # 1. Load session titles from main.sqlite
        db = os.path.expandvars(r"%APPDATA%\com.qoder.app.stable\main.sqlite")
        title_map = {}
        if os.path.exists(db):
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute("SELECT session_id, title FROM chat_sessions WHERE deleted_at IS NULL")
                for sid, t in cur.fetchall():
                    title_map[sid] = t.strip() if t else "未命名会话"
                conn.close()
            except Exception:
                pass

        # 2. Find all session jsonl files in ~/.qoder/projects
        p_dir = os.path.expanduser(r"~/.qoder/projects")
        jsonl_candidates = []
        if os.path.exists(p_dir):
            try:
                for root, _, files in os.walk(p_dir):
                    for f in files:
                        if f.endswith(".jsonl"):
                            fp = os.path.join(root, f)
                            try:
                                mtime = os.path.getmtime(fp)
                                sid = f[:-6]
                                jsonl_candidates.append((fp, sid, mtime))
                            except OSError:
                                pass
            except Exception:
                pass

        if not jsonl_candidates:
            return []

        # Sort by mtime descending
        jsonl_candidates.sort(key=lambda x: x[2], reverse=True)

        # Check payload buffer wal mtime
        buf_db = os.path.expandvars(r"%APPDATA%\com.qoder.app.stable\chat-session-turn-payload-buffer.sqlite-wal")
        buf_mtime = 0.0
        if os.path.exists(buf_db):
            try:
                buf_mtime = os.path.getmtime(buf_db)
            except OSError:
                pass

        sessions = []
        for fp, sid, mtime in jsonl_candidates[:max_sessions]:
            diff = now - max(mtime, buf_mtime)
            title = title_map.get(sid, "Qoder 工作会话")

            is_running = False
            last_conv_type = None
            last_stop_reason = None
            detail = "就绪"

            try:
                sz = os.path.getsize(fp)
                if sz > 0:
                    with open(fp, "rb") as f:
                        f.seek(max(0, sz - 65536))
                        tail = f.read().decode("utf-8", errors="ignore")
                    lines = [l.strip() for l in tail.splitlines() if l.strip()]
                    for l in reversed(lines[-25:]):
                        try:
                            d = json.loads(l)
                            t = d.get("type")
                            msg = d.get("message", {})
                            if t in ["user", "assistant"]:
                                last_conv_type = t
                                last_stop_reason = msg.get("stop_reason")
                                break
                        except Exception:
                            pass

                if last_conv_type == "user":
                    # User prompt or tool_result was submitted, waiting for assistant to finish turn
                    is_running = True
                    detail = "工作中 (模型生成中)"
                elif last_conv_type == "assistant":
                    if last_stop_reason == "end_turn":
                        is_running = False
                        detail = "就绪"
                    elif last_stop_reason == "tool_use":
                        is_running = True
                        detail = "工作中 (工具调用中)"
                    else:
                        is_running = True
                        detail = "工作中 (思考推理中)"
                else:
                    is_running = False
                    detail = "就绪"

                # Heartbeat check: if payload buffer or qodercli session log updated within 20s, it is actively generating
                if diff <= 20.0 and not is_running:
                    cli_logs = glob.glob(os.path.expandvars(rf"%APPDATA%\com.qoder.app.stable\logs\*\qodercli\sessions\{sid}.log"))
                    for cl in cli_logs:
                        try:
                            if (now - os.path.getmtime(cl)) <= 15.0:
                                is_running = True
                                detail = "工作中 (数据流通信中)"
                                break
                        except OSError:
                            pass

                # Timeout safety: if completely untouched for > 180s, consider IDLE
                if diff > 180.0:
                    is_running = False
                    detail = "就绪"

            except Exception as e:
                detail = f"解析异常: {e}"

            sessions.append({
                "session_id": sid,
                "title": title,
                "is_running": is_running,
                "is_approval": False,
                "mtime": mtime,
                "diff": diff,
                "detail": detail,
            })

        return sessions

    def resolve_workbuddy_sessions(self, max_sessions: int = 5) -> List[Dict]:
        """Resolve active sessions for WorkBuddy."""
        now = time.time()
        db = os.path.expanduser(r"~/.workbuddy/workbuddy.db")
        sessions = []
        if os.path.exists(db):
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, custom_title, title, status, updated_at, last_activity_at
                    FROM sessions
                    WHERE deleted_at IS NULL
                    ORDER BY updated_at DESC LIMIT 10;
                """)
                rows = cur.fetchall()
                conn.close()

                # Check active session JSON files for live heartbeats
                active_sids = {}
                sess_dir = os.path.expanduser(r"~/.workbuddy/sessions")
                if os.path.exists(sess_dir):
                    for f in glob.glob(os.path.join(sess_dir, "*.json")):
                        try:
                            with open(f, "r", encoding="utf-8") as jf:
                                d = json.load(jf)
                                sid = d.get("sessionId")
                                hb = d.get("lastHeartbeat") or d.get("updatedAt")
                                if sid and hb:
                                    active_sids[sid] = now - (hb / 1000.0)
                        except Exception:
                            pass

                for sid, custom_title, title, st, updated_at, last_act in rows:
                    mtime_ms = updated_at or last_act or 0
                    mtime = (mtime_ms / 1000.0) if mtime_ms else 0.0
                    diff = now - mtime
                    title_clean = (custom_title or title or "WorkBuddy 会话").strip()

                    hb_diff = active_sids.get(sid, 999999.0)
                    is_running = (st in ["running", "busy", "thinking", "generating"]) or (hb_diff <= 30.0)

                    # Include if running or recent (within 3 hours) or up to max_sessions
                    if is_running or diff <= 10800.0 or len(sessions) < max_sessions:
                        sessions.append({
                            "session_id": sid,
                            "title": title_clean,
                            "is_running": is_running,
                            "is_approval": False,
                            "mtime": mtime,
                            "diff": diff,
                            "detail": "工作中" if is_running else "就绪",
                        })

                    if len(sessions) >= max_sessions and not is_running:
                        break
            except Exception:
                pass
        return sessions

    def get_active_session_title(
        self, agent_id: str, default_window_title: Optional[str] = None
    ) -> Optional[str]:
        """Compatibility method for legacy single-title callers."""
        sessions = self.resolve_sessions(agent_id, default_window_title)
        if sessions:
            return sessions[0]["title"]
        return None
