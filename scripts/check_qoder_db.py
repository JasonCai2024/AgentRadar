import sqlite3
import os

db = os.path.expanduser("~/AppData/Roaming/com.qoder.app.stable/main.sqlite")
if os.path.exists(db):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]
    print("Tables in Qoder main.sqlite:", tables)
    for tbl in tables:
        cur.execute(f"PRAGMA table_info({tbl});")
        cols = [c[1] for c in cur.fetchall()]
        print(f"Table '{tbl}' cols: {cols}")
        cur.execute(f"SELECT * FROM {tbl};")
        rows = cur.fetchall()
        print(f"Total rows in {tbl}: {len(rows)}")
        for r in rows:
            r_str = str(r)
            if "7-1" in r_str:
                print("  FOUND '7-1' ROW:", r_str[:200])
