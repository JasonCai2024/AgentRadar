import os
import glob
import json
import sqlite3
import time

print("=== 1. Searching for '7-1' in Qoder ===")
q_dirs = [os.path.expanduser("~/.qoder"), os.path.expanduser("~/AppData/Roaming/com.qoder.app.stable")]
for qd in q_dirs:
    if os.path.exists(qd):
        for root, dirs, files in os.walk(qd):
            for f in files:
                if f.endswith((".json", ".jsonl", ".sqlite", ".log", ".txt", ".ldb")):
                    fp = os.path.join(root, f)
                    try:
                        if os.path.getsize(fp) < 10 * 1024 * 1024:
                            with open(fp, "rb") as f_obj:
                                data = f_obj.read()
                                if b"7-1" in data:
                                    print("FOUND '7-1' in:", fp)
                    except Exception:
                        pass

print("\n=== 2. Inspecting MiniMax Code Recent Session Files ===")
now = time.time()
mm_dirs = [
    os.path.expanduser("~/.minimax-agent"),
    os.path.expanduser("~/AppData/Roaming/MiniMax"),
    os.path.expanduser("~/AppData/Roaming/MiniMax Agent"),
    os.path.expanduser("~/AppData/Local/Programs/MiniMax Code")
]
for md in mm_dirs:
    if os.path.exists(md):
        for root, dirs, files in os.walk(md):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    mt = os.path.getmtime(fp)
                    if now - mt < 900:  # modified within 15 minutes
                        sz = os.path.getsize(fp)
                        print(f"MiniMax modified file ({now - mt:.1f}s ago, {sz}B): {fp}")
                except Exception:
                    pass

print("\n=== 3. Inspecting Codex Active Sessions ===")
codex_sessions = glob.glob(os.path.expanduser(r"~/.codex/sessions/2026/10/25/*.jsonl"))
print(f"Total Codex session files today: {len(codex_sessions)}")
for s in sorted(codex_sessions, key=os.path.getmtime, reverse=True)[:5]:
    diff = now - os.path.getmtime(s)
    print(f"Codex session ({diff:.1f}s ago): {s}")

codex_idx = os.path.expanduser(r"~/.codex/session_index.jsonl")
if os.path.exists(codex_idx):
    with open(codex_idx, "r", encoding="utf-8", errors="ignore") as f:
        entries = [json.loads(l.strip()) for l in f if l.strip()]
        entries.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        print("Codex top 5 most recently updated sessions:")
        for e in entries[:5]:
            print(f"  ID: {e.get('id')} | Thread Name: {repr(e.get('thread_name'))} | Title: {repr(e.get('title'))} | Updated: {e.get('updated_at')}")
