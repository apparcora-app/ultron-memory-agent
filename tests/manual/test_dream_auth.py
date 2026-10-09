import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import sys
import os
import sqlite3
import json
import uuid
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from reasoning.dreaming_engine import DreamingEngine

def setup_fake_error():
    db_path = ROOT_DIR / "data" / "telemetry.db"
    conn = sqlite3.connect(str(db_path))
    evt_id = f"evt_{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    details = {
        "tool": "web_automation",
        "input": {"command": "click '#submit'"},
        "success": False,
        "error": "TimeoutError: element '#submit' not found after 5s. Recommendation: always wait for elements to be visible before clicking using page.wait_for_selector."
    }
    
    # ensure it's not buried at the bottom
    conn.execute('DELETE FROM audit_logs')
    conn.execute(
        "INSERT INTO audit_logs (event_id, user_id, event_type, module_id, details, duration_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (evt_id, "boss", "TOOL_CALL", "web_automation", json.dumps(details), 5000, now)
    )
    conn.commit()
    conn.close()
    print(f"Inserted fake error {evt_id} for web_automation")
    return evt_id

def main():
    evt_id = setup_fake_error()
    
    # Initialize gemini
    from google import genai
    import config
    gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    d = DreamingEngine(gemini=gemini_client, provider="gemini")
    print("Running dream cycle...")
    res = d.run_dream_cycle(max_simulations=1)
    for r in res:
        print(f"Domain: {r.domain}")
        print(f"Dream success: {r.success}")
        print(f"Skill patched: {r.skill_patched}")
        if r.skill_patched:
            print(f"Generated code: {r.code_generated}")
            print(f"Hypothesis: {r.hypothesis}")
            
if __name__ == "__main__":
    main()
