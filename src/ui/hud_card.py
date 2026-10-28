"""Ultra-Compact Dark-Themed HUD Status Card for AgentRadar.

Features:
- Minimalist textless single-line rows: [⠿] [Dot] [Agent Name] [Session Name] [✕]
- Pure color dot status indicator (⚪ Offline, 🔵 Ready/Idle, 🟢 Thinking/Active, 🟡 Approval required).
- Ultra-compact footprint (~330px width): saves valuable desktop screen space.
- Per-session dismiss: click '✕' to hide idle sessions you no longer want to watch.
- Auto-unhide: newly created sessions or hidden sessions that start working auto-appear.
- Pure left drag handle (⠿) reordering with smooth global layout positioning.
- Header toggle for "仅看运行" (Hide Offline) mode and quick tray minimize.
- Single-click on card: brings associated agent window to the front.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMenu, QApplication
)
from PySide6.QtGui import QFont, QCursor, QIcon

from ..adapters.base import AgentState, AgentStatus, AgentDefinition
from ..adapters import ALL_AGENTS, AGENTS_MAP
from ..win32.window_manager import force_bring_to_front


def get_config_path() -> str:
    """Resolve order_config.json path (APPDATA when frozen, project root in dev)."""
    if getattr(sys, "frozen", False):
        app_data = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AgentRadar")
        os.makedirs(app_data, exist_ok=True)
        return os.path.join(app_data, "order_config.json")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "order_config.json"))


def get_asset_path(filename: str) -> str:
    """Resolve asset path for both normal script execution and PyInstaller onefile mode."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", filename)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", filename))


CONFIG_PATH = get_config_path()

SHORT_NAMES = {
    "antigravity": "AntiGravity",
    "codex": "Codex",
    "minimax_code": "MiniMax",
    "qoder": "Qoder",
    "workbuddy": "WorkBuddy",
}


def load_hud_config() -> dict:
    """Load user's preferred agent order and visibility configuration."""
    config = {
        "order": [],
        "hidden_agents": [],
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    saved_order = data.get("order", [])
                    config["order"] = [x for x in saved_order if isinstance(x, str)]
                    config["hidden_agents"] = [x for x in data.get("hidden_agents", []) if isinstance(x, str)]
        except Exception:
            pass
    return config


def save_hud_config(config: dict):
    """Persist user's custom agent display order and visibility configuration."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


class AgentBlockWidget(QFrame):
    """A compact, streamlined single-line block representing one active session or agent."""

    move_requested = Signal(str, int)  # (row_key, direction: -1 up, +1 down)
    hide_requested = Signal(str)       # (row_key)
    activate_requested = Signal(str)   # (row_key)

    def __init__(self, row_key: str, agent_def: AgentDefinition, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.row_key = row_key
        self.agent_def = agent_def
        self.agent_id = agent_def.id
        self._is_dragging_grip = False
        self._drag_start_pos = QPoint()

        self.setObjectName("CompactBlock")
        self.setFixedHeight(32)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet("""
            QFrame#CompactBlock {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QFrame#CompactBlock:hover {
                background-color: #273549;
                border: 1px solid #475569;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 6, 2)
        layout.setSpacing(6)

        # 1. Left Drag Grip
        self.drag_grip = QLabel("⠿")
        self.drag_grip.setToolTip("按住上下拖动以调整卡片位置")
        self.drag_grip.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.drag_grip.setStyleSheet("color: #64748b;")
        self.drag_grip.setCursor(QCursor(Qt.SizeVerCursor))
        self.drag_grip.setFixedWidth(14)
        self.drag_grip.setAlignment(Qt.AlignCenter)
        self.drag_grip.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.drag_grip)

        # 2. Status Dot
        self.dot_label = QLabel("⚪")
        self.dot_label.setFixedWidth(16)
        self.dot_label.setAlignment(Qt.AlignCenter)
        self.dot_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.dot_label)

        # 3. Agent Framework Name
        short_name = SHORT_NAMES.get(agent_def.id, agent_def.display_name)
        self.name_label = QLabel(f"{agent_def.icon_symbol} {short_name}")
        self.name_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.name_label.setStyleSheet("color: #f8fafc;")
        self.name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.name_label)

        # 4. Session Name
        self.session_label = QLabel("")
        self.session_label.setFont(QFont("Segoe UI", 8.5))
        self.session_label.setStyleSheet("color: #38bdf8;")
        self.session_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.session_label, stretch=1)

        # 5. Standby End Time (only shown when IDLE)
        self.time_label = QLabel("")
        self.time_label.setFont(QFont("Segoe UI", 8))
        self.time_label.setStyleSheet("color: #64748b; padding-right: 2px;")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.time_label)

        # 6. Right Dismiss/Close Icon ('✕')
        self.btn_hide = QPushButton("✕")
        self.btn_hide.setToolTip("隐藏此会话 (若该会话有新活动将自动恢复)")
        self.btn_hide.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_hide.setFixedSize(18, 18)
        self.btn_hide.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 10px;
                font-weight: bold;
                border-radius: 3px;
                padding: 0;
            }
            QPushButton:hover {
                background: #334155;
                color: #ef4444;
            }
        """)
        self.btn_hide.clicked.connect(lambda: self.hide_requested.emit(self.row_key))
        layout.addWidget(self.btn_hide)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            # If click is on the left handle area (x < 36), initiate drag reordering
            if event.pos().x() < 36:
                self._is_dragging_grip = True
                self.drag_grip.setStyleSheet("color: #38bdf8;")
            else:
                self._is_dragging_grip = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging_grip and (event.buttons() & Qt.LeftButton):
            dy = event.globalPosition().toPoint().y() - self._drag_start_pos.y()
            threshold = 24
            if dy > threshold:
                self.move_requested.emit(self.row_key, 1)
                self._drag_start_pos = event.globalPosition().toPoint()
            elif dy < -threshold:
                self.move_requested.emit(self.row_key, -1)
                self._drag_start_pos = event.globalPosition().toPoint()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._is_dragging_grip:
                self._is_dragging_grip = False
                self.drag_grip.setStyleSheet("color: #64748b;")
            else:
                # If clicked inside card body (not drag handle or hide button), activate that agent window!
                if (event.globalPosition().toPoint() - self._drag_start_pos).manhattanLength() < 5:
                    self.activate_requested.emit(self.row_key)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activate_requested.emit(self.row_key)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def update_state(self, state: AgentState):
        """Update row display with new AgentState."""
        status = state.status
        short_name = SHORT_NAMES.get(self.agent_def.id, self.agent_def.display_name)

        # Session name
        if state.session_name:
            clean = state.session_name.strip()
            display = clean[:22] + "..." if len(clean) > 22 else clean
            self.session_label.setText(f"· {display}")
            self.session_label.show()
        else:
            if status == AgentStatus.OFFLINE:
                self.session_label.hide()
            else:
                self.session_label.setText("· 默认工作区")
                self.session_label.show()

        if status == AgentStatus.OFFLINE:
            self.dot_label.setText("⚪")
            status_desc = "离线"
        elif status == AgentStatus.IDLE:
            self.dot_label.setText("🔵")
            status_desc = "待命就绪"
        elif status == AgentStatus.THINKING:
            self.dot_label.setText("🟢")
            status_desc = f"工作中 ({state.duration_seconds}s)"
        elif status == AgentStatus.PENDING_APPROVAL:
            self.dot_label.setText("🟡")
            status_desc = "等待确认"
        else:
            self.dot_label.setText("⚪")
            status_desc = "未知"

        # Update end/completion time for standby (IDLE) sessions:
        # Display latest update time to the left of the '✕' hide button; don't show for active sessions.
        time_info = ""
        if status == AgentStatus.IDLE and state.last_active_time and state.last_active_time > 0:
            try:
                dt = datetime.fromtimestamp(state.last_active_time)
                now_dt = datetime.now()
                if dt.date() == now_dt.date():
                    time_str = dt.strftime("%H:%M")
                else:
                    time_str = dt.strftime("%m-%d %H:%M")
                self.time_label.setText(time_str)
                self.time_label.setToolTip(f"结束/最近活动时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                self.time_label.show()
                time_info = f"\n结束时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
            except Exception:
                self.time_label.setText("")
                self.time_label.hide()
        else:
            self.time_label.setText("")
            self.time_label.hide()

        # Rich informative tooltip on the entire card row
        session_text = state.session_name or "默认工作区"
        self.setToolTip(
            f"{short_name} · {session_text}\n"
            f"状态: {status_desc}{time_info}\n"
            f"单击切换窗口，拖拽左侧 ⠿ 排序，点 ✕ 隐藏"
        )


class HUDCard(QWidget):
    """Ultra-responsive, compact dark-slate HUD card with dismissable session rows."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._drag_pos = QPoint()

        self.setWindowTitle("AgentRadar · 智能体监控中心")
        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Frameless, stays on top
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        cfg = load_hud_config()
        self._blocks_order: List[str] = cfg.get("order", [])
        self._hidden_agents: Set[str] = set(cfg.get("hidden_agents", []))

        # row_key -> AgentBlockWidget
        self.blocks_map: Dict[str, AgentBlockWidget] = {}
        self._latest_states: Dict[str, AgentState] = {}

        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        # Main Card Frame
        self.card = QFrame(self)
        self.card.setObjectName("MainCard")
        self.card.setStyleSheet("""
            QFrame#MainCard {
                background-color: #0f172a;
                border: 1.5px solid #334155;
                border-radius: 10px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(5)

        # Header Bar: Clean minimal title + minimize/close actions
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        self.title_label = QLabel("🛰️ AgentRadar")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.title_label.setStyleSheet("color: #f8fafc;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Minimize to tray button
        btn_min = QPushButton("🗕")
        btn_min.setToolTip("隐藏至系统托盘")
        btn_min.setCursor(QCursor(Qt.PointingHandCursor))
        btn_min.setFixedSize(20, 20)
        btn_min.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                font-size: 11px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
            }
        """)
        btn_min.clicked.connect(self.hide)
        header_layout.addWidget(btn_min)

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setToolTip("隐藏至系统托盘 (右键托盘可完全退出)")
        btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                font-size: 11px;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #ef4444;
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.hide)
        header_layout.addWidget(btn_close)

        card_layout.addLayout(header_layout)

        # Agent Blocks Container Layout
        self.blocks_container = QVBoxLayout()
        self.blocks_container.setSpacing(4)

        card_layout.addLayout(self.blocks_container)
        root_layout.addWidget(self.card)

        # Sleek, ultra-compact width
        self.setFixedWidth(340)

    def _save_current_config(self):
        """Persist current order and hidden agents state."""
        save_hud_config({
            "order": self._blocks_order,
            "hidden_agents": list(self._hidden_agents),
        })

    def _on_block_move_requested(self, row_key: str, direction: int):
        """Handle reorder request (-1 up, +1 down) with direct layout indexing."""
        widget = self.blocks_map.get(row_key)
        if not widget:
            return
        current_idx = self.blocks_container.indexOf(widget)
        if current_idx < 0:
            return

        target_idx = current_idx + direction
        if 0 <= target_idx < self.blocks_container.count():
            self.blocks_container.removeWidget(widget)
            self.blocks_container.insertWidget(target_idx, widget)

            # Re-sync _blocks_order from container layout
            self._blocks_order = [
                self.blocks_container.itemAt(i).widget().row_key
                for i in range(self.blocks_container.count())
                if self.blocks_container.itemAt(i).widget() is not None
            ]
            self._save_current_config()

    def _on_block_hide_requested(self, row_key: str):
        """Hide an individual session block or agent and remember in config."""
        self._hidden_agents.add(row_key)
        state = self._latest_states.get(row_key)
        if state and state.agent_id and state.status == AgentStatus.OFFLINE:
            self._hidden_agents.add(state.agent_id)

        if row_key in self.blocks_map:
            self.blocks_map[row_key].setVisible(False)

        self._save_current_config()
        self.adjustSize()

    def unhide_all_agents(self):
        """Unhide all manually hidden sessions and re-apply rules."""
        self._hidden_agents.clear()
        self._apply_visibility_rules()
        self._save_current_config()
        self.adjustSize()

    def _on_block_activate_requested(self, row_key: str):
        """Bring the associated window to the front on card click."""
        state = self._latest_states.get(row_key)
        if state and state.hwnd:
            force_bring_to_front(state.hwnd)

    def _apply_visibility_rules(self):
        """Apply visibility rules based on state and manual hiding."""
        for row_key, block in self.blocks_map.items():
            state = self._latest_states.get(row_key)
            is_offline = (state is None) or (state.status == AgentStatus.OFFLINE)
            aid = state.agent_id if state else ""

            is_hidden = (row_key in self._hidden_agents) or (aid in self._hidden_agents) or is_offline
            block.setVisible(not is_hidden)

        self.adjustSize()

    def update_states(self, states: Dict[str, AgentState]):
        """Update block widgets with fresh session states, preserving custom order."""
        for k, v in states.items():
            self._latest_states[k] = v
        thinking_count = 0
        approval_count = 0

        # Sort incoming states according to saved _blocks_order.
        # Any brand-new session not yet in _blocks_order gets index 999999 so it is appended at the very end.
        def get_order_index(key: str) -> int:
            if key in self._blocks_order:
                return self._blocks_order.index(key)
            return 999999

        sorted_keys = sorted(states.keys(), key=get_order_index)

        now = time.time()

        # 1. Create or update widgets for all incoming states
        for row_key in sorted_keys:
            state = states[row_key]
            agent_def = AGENTS_MAP.get(state.agent_id)
            if not agent_def:
                continue

            # Completely skip OFFLINE agents - no placeholder rows are ever created
            if state.status == AgentStatus.OFFLINE:
                continue

            if row_key not in self.blocks_map:
                is_active = state.status in [AgentStatus.THINKING, AgentStatus.PENDING_APPROVAL]
                is_saved = (row_key in self._blocks_order) and (row_key not in self._hidden_agents)
                is_recent = (state.last_active_time > 0 and (now - state.last_active_time) <= 1800.0 and (row_key not in self._hidden_agents))

                # Do not spam historical inactive sessions that user never tracked;
                # only add if currently active, saved in layout, or freshly active within 30 min.
                if not (is_active or is_saved or is_recent):
                    continue

                block = AgentBlockWidget(row_key, agent_def, self)
                block.move_requested.connect(self._on_block_move_requested)
                block.hide_requested.connect(self._on_block_hide_requested)
                block.activate_requested.connect(self._on_block_activate_requested)
                self.blocks_map[row_key] = block
                self.blocks_container.addWidget(block)
                if row_key not in self._blocks_order:
                    self._blocks_order.append(row_key)
                    self._save_current_config()

            block = self.blocks_map[row_key]
            block.update_state(state)

            # Auto-unhide if a hidden session begins actively working or waiting for approval!
            if state.status == AgentStatus.THINKING or state.status == AgentStatus.PENDING_APPROVAL:
                if row_key in self._hidden_agents:
                    self._hidden_agents.discard(row_key)
                    self._save_current_config()
                if state.agent_id in self._hidden_agents:
                    self._hidden_agents.discard(state.agent_id)
                    self._save_current_config()

            if state.status == AgentStatus.THINKING:
                thinking_count += 1
            elif state.status == AgentStatus.PENDING_APPROVAL:
                approval_count += 1

        # 2. Retain existing session widgets: DO NOT auto-remove or delete them!
        # Once a session is shown on the HUD, it remains visible (in IDLE standby) until the user
        # explicitly clicks the '✕' button to dismiss it.
        for old_key, block in self.blocks_map.items():
            if old_key not in states:
                old_state = self._latest_states.get(old_key)
                if old_state and old_state.status != AgentStatus.IDLE:
                    old_state.status = AgentStatus.IDLE
                    block.update_state(old_state)

        # 3. Apply visibility
        self._apply_visibility_rules()

        # 4. Update header summary
        if approval_count > 0:
            self.title_label.setText(f"🛰️ AgentRadar · ⚠️ {approval_count} 待确认")
        elif thinking_count > 0:
            self.title_label.setText(f"🛰️ AgentRadar · 🟢 {thinking_count} 运行中")
        else:
            self.title_label.setText("🛰️ AgentRadar · 状态就绪")

    def contextMenuEvent(self, event):
        """Show context menu."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #334155;
                color: #38bdf8;
            }
        """)

        act_unhide = menu.addAction("👁️ 显示全部已隐藏会话")
        act_unhide.triggered.connect(self.unhide_all_agents)

        menu.addSeparator()
        act_reset = menu.addAction("↺ 恢复初始顺序")
        act_reset.triggered.connect(self._reset_order)

        menu.exec(event.globalPos())

    def _reset_order(self):
        self._blocks_order = [k for k in self.blocks_map.keys()]
        self._save_current_config()
        self.adjustSize()

    def mousePressEvent(self, event):
        """Enable window dragging when clicking card header or frame."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Silky-smooth window moving without CPU rasterization lag."""
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
