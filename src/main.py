"""AgentRadar Main Entry Point.

Starts the PySide6 application, initializes the hybrid sensing engine on
a dedicated background worker thread, and displays the fluid HUD status card.
Supports single-instance IPC: double-clicking the shortcut or launching a second
instance automatically wakes up and brings the running HUD card to the front.
"""

import sys
import os
import ctypes
from loguru import logger
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# Ensure src can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.engine import AgentRadarEngine
from src.ui.hud_card import HUDCard
from src.ui.tray_app import TrayApp
from src.win32.window_manager import force_bring_to_front, ensure_default_desktop

IPC_SERVER_NAME = "AgentRadar_SingleInstance_IPC_v1"


def get_app_asset_path(filename: str) -> str:
    """Resolve asset path for both normal script execution and PyInstaller onefile mode."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", filename)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", filename))


def get_log_dir() -> str:
    """Resolve log directory (APPDATA when frozen, project root in dev)."""
    if getattr(sys, "frozen", False):
        log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AgentRadar", "logs")
    else:
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logging():
    """Configure Loguru logger safely for both console and pythonw (NoneType stderr)."""
    log_dir = get_log_dir()
    log_file = os.path.join(log_dir, "agent_radar.log")

    logger.remove()
    if sys.stderr is not None:
        try:
            logger.add(sys.stderr, level="INFO")
        except Exception:
            pass

    logger.add(log_file, rotation="10 MB", retention="7 days", level="DEBUG", encoding="utf-8")


def main():
    # 0. Always attach to the interactive Default desktop before creating GUI
    ensure_default_desktop()

    # Set Windows App ID for proper taskbar grouping
    try:
        myappid = "agentradar.desktop.observer.v1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    setup_logging()

    # Prevent app from closing when HUD card is hidden
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)
    app.setApplicationName("AgentRadar")

    # Set application icon
    icon_path = get_app_asset_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Single instance IPC check:
    # If an instance is already running, notify it to show HUD and exit immediately
    socket = QLocalSocket()
    socket.connectToServer(IPC_SERVER_NAME)
    if socket.waitForConnected(300):
        logger.info("Existing AgentRadar instance detected. Sent wake-up signal to show HUD.")
        socket.write(b"SHOW\n")
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return 0

    logger.info("Initializing AgentRadar v0.4.0 (Single Instance IPC Server)...")

    # Start IPC Server for future wake-up requests
    QLocalServer.removeServer(IPC_SERVER_NAME)
    ipc_server = QLocalServer()
    if not ipc_server.listen(IPC_SERVER_NAME):
        logger.warning(f"Failed to listen on IPC server {IPC_SERVER_NAME}")

    # 1. Create HUD Card & Tray in GUI Main Thread
    hud_card = HUDCard()
    tray_app = TrayApp(hud_card)

    def handle_ipc_connection():
        client_socket = ipc_server.nextPendingConnection()
        if client_socket:
            logger.info("Received wake-up request from another process. Activating HUD.")
            tray_app.show_hud()
            try:
                force_bring_to_front(int(hud_card.winId()))
            except Exception:
                pass
            client_socket.close()

    ipc_server.newConnection.connect(handle_ipc_connection)

    # 2. Create Core Sensing Engine & Move to dedicated Background QThread
    worker_thread = QThread()
    engine = AgentRadarEngine(poll_interval_ms=3000)
    engine.moveToThread(worker_thread)

    # Wire worker lifecycle
    worker_thread.started.connect(engine.start)

    # Wire cross-thread Signals smoothly
    engine.state_updated.connect(hud_card.update_states)
    engine.state_updated.connect(tray_app.update_states)
    tray_app.request_exit.connect(app.quit)

    # Clean shutdown handling
    def cleanup():
        logger.info("Stopping AgentRadar worker thread and engine...")
        try:
            ipc_server.close()
        except Exception:
            pass
        engine.stop()
        worker_thread.quit()
        worker_thread.wait(1500)

    app.aboutToQuit.connect(cleanup)

    # 3. Start worker thread
    worker_thread.start()

    # 4. Show HUD Card immediately on launch
    tray_app.show_hud()

    # Show initial welcome balloon from tray
    try:
        tray_app.tray_icon.showMessage(
            "AgentRadar 已启动",
            "正在后台实时监控 5 大 GUI 智能体会话。\n双击桌面快捷方式可随时呼出看板。",
            tray_app.tray_icon.icon(),
            3000
        )
    except Exception:
        pass

    logger.info("AgentRadar GUI event loop running.")
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            crash_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "crash.log"))
            with open(crash_path, "w", encoding="utf-8") as f:
                f.write(err_msg)
            ctypes.windll.user32.MessageBoxW(
                0,
                f"AgentRadar 启动发生异常:\n\n{err_msg}\n详情已保存至 crash.log",
                "AgentRadar 错误",
                0x10
            )
        except Exception:
            pass
