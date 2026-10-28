"""High-Performance Win32 Process Tree and Activity Probe for AgentRadar.

Optimized to replace costly repetitive psutil.Process.children() calls
with a single, global Win32 CreateToolhelp32Snapshot (~8ms for the whole OS),
resolving process hierarchies in pure memory with sub-millisecond overhead.
"""

import os
import sys
import time
import ctypes
from ctypes import wintypes
from typing import Dict, List, Optional, Set, Tuple
import psutil
from loguru import logger
from ..adapters.base import AgentDefinition

# Win32 Process Structures
kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260)
    ]


class ProcessProbe:
    """High-efficiency process scanner with single-pass OS process snapshotting."""

    def __init__(self):
        self._proc_cache: Dict[int, psutil.Process] = {}
        self._tree: Dict[int, List[int]] = {}
        self._name_map: Dict[str, List[int]] = {}
        self._all_system_pids: Set[int] = set()
        self._last_snapshot_time: float = 0.0

    def refresh_system_snapshot(self):
        """Capture a single global snapshot of all system processes via Win32 Toolhelp (~8ms)."""
        now = time.time()
        tree: Dict[int, List[int]] = {}
        name_map: Dict[str, List[int]] = {}
        all_pids: Set[int] = set()

        if kernel32 is not None:
            try:
                # 0x00000002 = TH32CS_SNAPPROCESS
                h_snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
                if h_snap != -1 and h_snap != 0:
                    pe = PROCESSENTRY32()
                    pe.dwSize = ctypes.sizeof(PROCESSENTRY32)

                    if kernel32.Process32FirstW(h_snap, ctypes.byref(pe)):
                        while True:
                            pid = pe.th32ProcessID
                            ppid = pe.th32ParentProcessID
                            exe = pe.szExeFile.lower()
                            all_pids.add(pid)
                            tree.setdefault(ppid, []).append(pid)
                            name_map.setdefault(exe, []).append(pid)
                            if not kernel32.Process32NextW(h_snap, ctypes.byref(pe)):
                                break
                    kernel32.CloseHandle(h_snap)
                    self._tree = tree
                    self._name_map = name_map
                    self._all_system_pids = all_pids
                    self._last_snapshot_time = now
                    return
            except Exception as e:
                logger.warning(f"Win32 Toolhelp snapshot failed, falling back to psutil: {e}")

        # Fallback to single psutil pass
        try:
            for p in psutil.process_iter(["pid", "ppid", "name"]):
                try:
                    pid = p.info["pid"]
                    ppid = p.info["ppid"]
                    name = (p.info["name"] or "").lower()
                    all_pids.add(pid)
                    tree.setdefault(ppid, []).append(pid)
                    name_map.setdefault(name, []).append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        self._tree = tree
        self._name_map = name_map
        self._all_system_pids = all_pids
        self._last_snapshot_time = now

    def scan_agent_processes(self, agent_def: AgentDefinition) -> Tuple[List[int], Optional[int], float]:
        """Scan system for processes matching the agent definition using the global snapshot.

        Returns:
            Tuple of (all_pids, main_pid, total_cpu_percent)
        """
        # Auto-refresh snapshot if not yet taken or stale (>1.0s)
        if (time.time() - self._last_snapshot_time) > 1.0 or not self._name_map:
            self.refresh_system_snapshot()

        matched_pids: List[int] = []
        for target_name in agent_def.process_names:
            matched_pids.extend(self._name_map.get(target_name.lower(), []))

        if not matched_pids:
            return ([], None, 0.0)

        # In-memory DFS tree traversal (< 0.05 ms)
        all_pids: Set[int] = set(matched_pids)
        stack = list(matched_pids)
        while stack:
            curr = stack.pop()
            for child in self._tree.get(curr, []):
                if child not in all_pids:
                    all_pids.add(child)
                    stack.append(child)

        # Identify primary main PID (the root ancestor among matched pids)
        matched_set = set(matched_pids)
        main_pid = matched_pids[0]
        for pid in matched_pids:
            # If this pid's parent is not one of our matched pids, it's a top-level parent
            # Search parent
            is_child = False
            for parent_pid, children in self._tree.items():
                if pid in children and parent_pid in matched_set:
                    is_child = True
                    break
            if not is_child:
                main_pid = pid
                break

        # Calculate CPU usage only for main_pid to avoid querying 50+ child renderers
        total_cpu = 0.0
        if main_pid:
            try:
                if main_pid not in self._proc_cache:
                    self._proc_cache[main_pid] = psutil.Process(main_pid)
                proc = self._proc_cache[main_pid]
                total_cpu = proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._proc_cache.pop(main_pid, None)

        # Evict terminated processes from cache
        dead_pids = [pid for pid in self._proc_cache if pid not in self._all_system_pids]
        for pid in dead_pids:
            self._proc_cache.pop(pid, None)

        return (list(all_pids), main_pid, round(total_cpu, 1))
