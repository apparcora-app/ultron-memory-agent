import os
import sys
import asyncio
from fastapi.testclient import TestClient

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import app

def test_static_html_served():
    client = TestClient(app); client.headers.update({"X-API-Key": os.environ.get("TEST_API_KEY", "")})
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    html = response.text
    assert "Ultron Protocol" in html
    assert "/static/assets/index-" in html
    print("[PASS] Static HTML index served successfully with Syntrix assets.", flush=True)

def test_skills_api():
    client = TestClient(app); client.headers.update({"X-API-Key": os.environ.get("TEST_API_KEY", "")})
    response = client.get("/api/skills?user_id=boss")
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    skills = data.get("skills", [])
    print(f"[PASS] Skills API returned {len(skills)} skills.", flush=True)

def test_status_api():
    client = TestClient(app); client.headers.update({"X-API-Key": os.environ.get("TEST_API_KEY", "")})
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ("OPERATIONAL", "healthy"), f"Unexpected status: {data}"
    print(f"[PASS] Status API: {data.get('status')}, system: {data.get('system')}", flush=True)

def test_chat_solo_mode():
    client = TestClient(app); client.headers.update({"X-API-Key": os.environ.get("TEST_API_KEY", "")})
    payload = {
        "user_id": "boss",
        "message": "Hello Ultron, confirm your active status.",
        "operation_mode": "DIRECT",
        "module_id": "ultron_prime",
        "model_override": "auto",
        "optimize_prompt": "false",
    }
    print("[RUNNING] Sending chat request to /api/chat in Solo Mode...", flush=True)
    response = client.post("/api/chat", data=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data.get("operation_mode") == "DIRECT"
    print(f"[PASS] Solo Mode Chat successful. Reply preview: {data.get('reply')[:80]}...", flush=True)

if __name__ == "__main__":
    print("=== EMPIRICAL VERIFICATION: ULTRON SYNTRIX INTEGRATION ===", flush=True)
    test_static_html_served()
    test_status_api()
    test_skills_api()
    test_chat_solo_mode()
    print("=== ALL EMPIRICAL INTEGRATION TESTS PASSED ===", flush=True)
