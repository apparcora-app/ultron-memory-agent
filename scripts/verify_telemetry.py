import sqlite3
import sys

import os
from pathlib import Path

def verify():
    data_dir = Path(os.environ.get("ULTRON_DATA_DIR", "data"))
    conn = sqlite3.connect(data_dir / "telemetry.db")
    cur = conn.cursor()
    c1 = cur.execute("SELECT COUNT(*) FROM audit_logs WHERE event_id='old_event_1'").fetchone()[0]
    c2 = cur.execute("SELECT COUNT(*) FROM audit_logs WHERE event_id='new_event_1'").fetchone()[0]
    
    if c1 != 0:
        print("old_event_1 NOT purged!")
        sys.exit(1)
    else:
        print("old_event_1 successfully purged from telemetry.db.")
        
    if c2 != 1:
        print("new_event_1 incorrectly purged!")
        sys.exit(1)
    else:
        print("new_event_1 safely retained in telemetry.db.")

if __name__ == "__main__":
    verify()
