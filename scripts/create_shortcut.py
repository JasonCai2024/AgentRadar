"""Create Desktop Shortcut for AgentRadar.
"""

import os
import sys
import win32com.client


def create_desktop_shortcut():
    desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
    shortcut_path = os.path.join(desktop, "AgentRadar.lnk")

    # Resolve project root dynamically
    script_dir = os.path.dirname(os.path.abspath(__file__))
    work_dir = os.path.abspath(os.path.join(script_dir, ".."))
    target_script = os.path.join(work_dir, "src", "main.py")
    icon_path = os.path.join(work_dir, "assets", "icon.ico")

    # Determine pythonw executable
    py_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(py_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = pythonw
    shortcut.Arguments = f'"{target_script}"'
    shortcut.WorkingDirectory = work_dir
    if os.path.exists(icon_path):
        shortcut.IconLocation = f"{icon_path},0"
    shortcut.Description = "AgentRadar - 5大GUI智能体状态监控与一键切窗"
    shortcut.save()

    print(f"Shortcut created: {shortcut_path}")
    print(f"Target: {pythonw} \"{target_script}\"")
    print(f"Working Dir: {work_dir}")
    print(f"Icon: {icon_path}")


if __name__ == "__main__":
    create_desktop_shortcut()
