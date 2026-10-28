import os
import time

now = time.time()
base = os.path.expanduser("~/AppData/Roaming/MiniMax")
recent_files = []
for root, _, files in os.walk(base):
    for f in files:
        fp = os.path.join(root, f)
        try:
            mt = os.path.getmtime(fp)
            if now - mt < 1800: # last 30 mins
                recent_files.append((fp, mt))
        except Exception:
            pass

recent_files.sort(key=lambda x: x[1], reverse=True)
print(f"Total recent MiniMax files: {len(recent_files)}")
for fp, mt in recent_files[:15]:
    sz = os.path.getsize(fp)
    print(f"File ({now - mt:.1f}s ago, {sz}B): {fp}")
    try:
        with open(fp, "rb") as f_obj:
            raw = f_obj.read()
            # print printable strings of length > 4
            import re
            strings = re.findall(b"[\x20-\x7e\xe4-\xe9\x80-\xbf]{4,}", raw)
            # look for interesting strings containing session, title, task, name or chinese
            candidates = []
            for s in strings:
                try:
                    s_dec = s.decode("utf-8", errors="ignore")
                    if any(k in s_dec for k in ["session", "title", "name", "task", "project", "topic"]):
                        if len(s_dec) < 80:
                            candidates.append(s_dec)
                    elif any('\u4e00' <= char <= '\u9fff' for char in s_dec):
                        if 2 < len(s_dec) < 80:
                            candidates.append(s_dec)
                except Exception:
                    pass
            if candidates:
                print(f"  Interesting strings in {os.path.basename(fp)} ({len(candidates)}):", candidates[:8])
    except Exception as e:
        print("  Error reading:", e)
