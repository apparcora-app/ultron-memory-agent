import os
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memory.memory_manager import MemoryManager

def setup_fake_data():
    base_dir = Path(__file__).resolve().parent.parent
    import os
    data_dir = Path(os.environ.get("ULTRON_DATA_DIR", base_dir / "data"))
    
    # Dates
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=40)
    new_date = now - timedelta(days=5)
    
    # 1. Telemetry DB
    db_path = data_dir / "telemetry.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    module_id TEXT NOT NULL,
                    details TEXT,
                    duration_ms INTEGER,
                    timestamp REAL
                )''')
    cur.execute("INSERT OR REPLACE INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)", 
                ("old_event_1", "boss", "test", "mod", "SSN: 000-00-0000", 100, old_date.timestamp()))
    cur.execute("INSERT OR REPLACE INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)", 
                ("new_event_1", "boss", "test", "mod", "SSN: 111-11-1111", 100, new_date.timestamp()))
    conn.commit()
    conn.close()
    
    # 2. Computer Audit JSONL
    audit_dir = data_dir / "logs"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "computer_audit.jsonl"
    with open(audit_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "old_audit", "timestamp": old_date.isoformat(), "pii": "EIN: 12-3456789"}) + "\n")
        f.write(json.dumps({"id": "new_audit", "timestamp": new_date.isoformat(), "pii": "EIN: 98-7654321"}) + "\n")
        
    # 3. Sessions
    sessions_dir = data_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    old_sess = sessions_dir / "old_sess.json"
    new_sess = sessions_dir / "new_sess.json"
    old_sess.write_text("{}")
    new_sess.write_text("{}")
    os.utime(old_sess, (old_date.timestamp(), old_date.timestamp()))
    os.utime(new_sess, (new_date.timestamp(), new_date.timestamp()))
    
    # 4. Blackboard
    bb_dir = data_dir / "blackboard"
    bb_dir.mkdir(parents=True, exist_ok=True)
    old_bb = bb_dir / "old_bb.json"
    new_bb = bb_dir / "new_bb.json"
    old_bb.write_text("{}")
    new_bb.write_text("{}")
    os.utime(old_bb, (old_date.timestamp(), old_date.timestamp()))
    os.utime(new_bb, (new_date.timestamp(), new_date.timestamp()))
    
    # 5. Mem0/Chroma
    # Skipping Mem0 insertion to avoid API quota errors
    pass
    # Mem0 API doesn't allow overriding created_at easily in `add()`, 
    # but we can try injecting directly to SQLite if we really want to, 
    # or just trust the logic. Wait! We can update sqlite directly since Mem0 uses ChromaDB which uses sqlite.
    # It's usually located at data/chroma/chroma.sqlite3
    
    print("[TEST SETUP] Fake old (40 days) and new (5 days) records injected.")

if __name__ == "__main__":
    setup_fake_data()
