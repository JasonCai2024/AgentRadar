"""System Tray Application for AgentRadar.

Provides dynamic status indicator icon, context menu, and HUD positioning.
"""

from typing import Dict, Optional
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication
)
from PySide6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QAction
)
from loguru import logger

from ..adapters.base import AgentState, AgentStatus
from .hud_card import HUDCard
from ..win32.window_manager import force_bring_to_front


def generate_tray_icon(status: AgentStatus) -> QIcon:
    """Dynamically render a clean radar icon with color indicating current state."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Determine colors
    if status == AgentStatus.PENDING_APPROVAL:
        ring_color = QColor(234, 179, 8, 200)      # Amber / Yellow
        center_color = QColor(250, 204, 21, 255)
    elif status == AgentStatus.THINKING:
        ring_color = QColor(34, 197, 94, 200)      # Green
        center_color = QColor(74, 222, 128, 255)
    elif status == AgentStatus.IDLE:
        ring_color = QColor(14, 165, 233, 180)     # Sky Blue
        center_color = QColor(56, 189, 248, 240)
    else:  # OFFLINE
        ring_color = QColor(100, 116, 139, 140)    # Slate Gray
        center_color = QColor(148, 163, 184, 200)

    # Outer radar ring
    pen = QPen(ring_color)
    pen.setWidth(4)
    painter.setPen(pen)
    painter.drawEllipse(6, 6, size - 12, size - 12)

    # Inner radar ring
    pen.setWidth(2)
    pen.setStyle(Qt.DashLine)
    painter.setPen(pen)
    painter.drawEllipse(18, 18, size - 36, size - 36)

    # Center glowing pulse dot
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(center_color))
    painter.drawEllipse(24, 24, 16, 16)

    painter.end()
    return QIcon(pixmap)


class TrayApp(QObject):
    """Manages the Windows taskbar tray icon and HUD interactions."""

    request_exit = Signal()

    def __init__(self, hud_card: HUDCard, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.hud_card = hud_card

        self.tray_icon = QSystemTrayIcon(self)
        self.current_status = AgentStatus.OFFLINE
        self.update_icon(AgentStatus.OFFLINE)

        self._build_menu()
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1e293b;
                color: #38bdf8;
            }
            QMenu::separator {
                height: 1px;
                background-color: #334155;
                margin: 4px 6px;
            }
        """)

        action_show = QAction("🛰️ 显示状态看板", menu)
        action_show.triggered.connect(self.show_hud)
        menu.addAction(action_show)

        action_hide = QAction("🗕 隐藏状态看板", menu)
        action_hide.triggered.connect(self.hud_card.hide)
        menu.addAction(action_hide)

        menu.addSeparator()

        action_exit = QAction("✕ 退出 AgentRadar", menu)
        action_exit.triggered.connect(self.request_exit.emit)
        menu.addAction(action_exit)

        self.tray_icon.setContextMenu(menu)

    def update_icon(self, status: AgentStatus):
        """Update tray icon according to aggregated status."""
        self.current_status = status
        icon = generate_tray_icon(status)
        self.tray_icon.setIcon(icon)

    def update_states(self, states: Dict[str, AgentState]):
        """Aggregate states and set tray tooltip and icon."""
        has_approval = any(s.status == AgentStatus.PENDING_APPROVAL for s in states.values())
        has_thinking = any(s.status == AgentStatus.THINKING for s in states.values())
        has_idle = any(s.status == AgentStatus.IDLE for s in states.values())

        if has_approval:
            new_status = AgentStatus.PENDING_APPROVAL
            tooltip = "AgentRadar: ⚠️ 有智能体正在等待您的确认！"
        elif has_thinking:
            new_status = AgentStatus.THINKING
            active_names = [f"{s.display_name}({s.session_name})" if s.session_name else s.display_name for s in states.values() if s.status == AgentStatus.THINKING]
            tooltip = f"AgentRadar: ⚡ 正在工作中: {', '.join(active_names)}"
        elif has_idle:
            new_status = AgentStatus.IDLE
            tooltip = "AgentRadar: 所有已启动智能体均处于空闲状态"
        else:
            new_status = AgentStatus.OFFLINE
            tooltip = "AgentRadar: 所有智能体均未启动"

        if new_status != self.current_status:
            self.update_icon(new_status)

        self.tray_icon.setToolTip(tooltip)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            # Single Left-Click toggles HUD
            if self.hud_card.isVisible():
                self.hud_card.hide()
            else:
                self.show_hud()

    def show_hud(self):
        """Position HUD near the bottom-right tray area and display it."""
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            self.hud_card.adjustSize()
            hint = self.hud_card.sizeHint()
            card_w = 340
            card_h = hint.height() if hint.height() > 80 else 240
            x = max(20, geom.right() - card_w - 20)
            y = max(20, geom.bottom() - card_h - 20)
            self.hud_card.setGeometry(x, y, card_w, card_h)

        self.hud_card.showNormal()
        self.hud_card.show()
        self.hud_card.raise_()
        self.hud_card.activateWindow()
        try:
            force_bring_to_front(int(self.hud_card.winId()))
        except Exception:
            pass
