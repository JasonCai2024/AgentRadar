"""Win32 Window Manager for AgentRadar.

Provides window discovery, desktop-station bridging, and reliable
foreground activation using Win32 AttachThreadInput and SetForegroundWindow.
"""

import ctypes
from ctypes import wintypes
import time
from typing import Optional, List, Tuple
from loguru import logger
import win32gui
import win32process
import win32con
import win32api

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def ensure_default_desktop() -> bool:
    """Ensure current thread is attached to the interactive Default desktop.

    Returns True if successfully attached or already on Default desktop.
    """
    try:
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
            return True
    except Exception as e:
        logger.warning(f"Failed to attach to Default desktop: {e}")
    return False


def find_window_by_pids_or_titles(
    pids: List[int],
    title_keywords: List[str]
) -> Optional[Tuple[int, str]]:
    """Find the top-level main window HWND for the given PIDs and title keywords.

    Returns (hwnd, window_title) or None.
    """
    found: List[Tuple[int, str, int]] = []  # (hwnd, title, priority_score)

    def enum_cb(hwnd, _):
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return True

        # Must not be a child control or tooltip
        parent = win32gui.GetParent(hwnd)
        if parent != 0:
            return True

        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return True

        # Check PID
        try:
            _, wpid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return True

        lower_title = title.lower()
        score = 0

        if wpid in pids:
            score += 10
            # Higher score if title matches known keywords
            for kw in title_keywords:
                if kw.lower() in lower_title:
                    score += 20
        else:
            # Fallback title match even if PID not in direct list (e.g. UWP child or host)
            for kw in title_keywords:
                if kw.lower() in lower_title:
                    score += 5

        # Ignore tiny off-screen utility windows
        try:
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            if width > 300 and height > 200:
                score += 5
        except Exception:
            pass

        if score > 0:
            found.append((hwnd, title, score))

        return True

    try:
        # Prefer enumerating default interactive desktop
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            win32gui.EnumDesktopWindows(h_desk, enum_cb, None)
            user32.CloseDesktop(h_desk)
        else:
            win32gui.EnumWindows(enum_cb, None)
    except Exception as e:
        logger.debug(f"EnumDesktopWindows fallback: {e}")
        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception as e2:
            logger.error(f"EnumWindows error: {e2}")

    if not found:
        return None

    # Sort by highest score
    found.sort(key=lambda item: item[2], reverse=True)
    best_hwnd, best_title, _ = found[0]
    return (best_hwnd, best_title)


def force_bring_to_front(hwnd: int) -> bool:
    """Force bring target HWND to the foreground and activate it.

    Bypasses Windows foreground lock restrictions using AttachThreadInput and
    simulated keypresses if necessary.
    """
    ensure_default_desktop()

    if not win32gui.IsWindow(hwnd):
        logger.warning(f"Invalid HWND {hwnd}")
        return False

    try:
        # 1. Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # 2. Get thread IDs
        fore_hwnd = win32gui.GetForegroundWindow()
        fore_thread, _ = win32process.GetWindowThreadProcessId(fore_hwnd) if fore_hwnd else (0, 0)
        target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
        current_thread = kernel32.GetCurrentThreadId()

        # 3. Attach input queues to inherit foreground permissions
        attached_fore = False
        attached_target = False

        if fore_thread and fore_thread != current_thread:
            attached_fore = bool(user32.AttachThreadInput(current_thread, fore_thread, True))
        if target_thread and target_thread != current_thread:
            attached_target = bool(user32.AttachThreadInput(current_thread, target_thread, True))

        # 4. Simulate a dummy Alt key to unlock SetForegroundWindow
        user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
        user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

        # 5. Bring to front and activate
        win32gui.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        win32gui.SetFocus(hwnd)

        # 6. Detach input queues
        if attached_fore:
            user32.AttachThreadInput(current_thread, fore_thread, False)
        if attached_target:
            user32.AttachThreadInput(current_thread, target_thread, False)

        return True
    except Exception as e:
        logger.error(f"Error in force_bring_to_front({hwnd}): {e}")
        return False
