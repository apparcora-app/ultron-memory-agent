import sys
from fastapi.testclient import TestClient
from ultron.cli.web import app

def test_web_endpoints():
    client = TestClient(app)

    print("--- 1. Testing GET / ---")
    res_index = client.get("/")
    print(f"Status: {res_index.status_code}")
    assert res_index.status_code == 200, f"Expected 200, got {res_index.status_code}"
    session_cookie = res_index.cookies.get("ultron_session")
    print(f"Session cookie: {session_cookie}")

    print("\n--- 2. Testing GET /api/providers ---")
    res_prov = client.get("/api/providers")
    print(f"Status: {res_prov.status_code}")
    assert res_prov.status_code == 200, f"Expected 200, got {res_prov.status_code}"
    data_prov = res_prov.json()
    providers = data_prov.get("providers", [])
    print(f"Total providers returned: {len(providers)}")
    for p in providers:
        print(f"  • {p.get('name')} | id: {p.get('id')} | badge: {p.get('badge')}")
    assert len(providers) > 0, "No providers loaded!"

    print("\n--- 3. Testing GET /api/skills ---")
    res_skills = client.get("/api/skills")
    print(f"Status: {res_skills.status_code}")
    assert res_skills.status_code == 200, f"Expected 200, got {res_skills.status_code}"
    data_skills = res_skills.json()
    skills_count = data_skills.get("count", 0)
    print(f"Total active skills: {skills_count}")
    skills = data_skills.get("skills", [])
    for s in skills[:5]:
        print(f"  • {s.get('name')} ({s.get('skill_id')})")
    assert skills_count > 0, "No skills loaded!"

    print("\n--- 4. Testing GET /api/memories (Historical Vector Persistence) ---")
    res_mem = client.get("/api/memories")
    print(f"Status: {res_mem.status_code}")
    assert res_mem.status_code == 200, f"Expected 200, got {res_mem.status_code}"
    data_mem = res_mem.json()
    memories_count = data_mem.get("count", 0)
    print(f"Total long-term vector memories: {memories_count}")
    assert memories_count > 0, "Memories are 0!"
    for m in data_mem.get("memories", [])[:3]:
        print(f"  • [{m.get('id')[:8]}...] {m.get('memory')[:60]}...")

    print("\n--- 5. Testing GET /api/sessions ---")
    res_sess = client.get("/api/sessions")
    print(f"Status: {res_sess.status_code}")
    assert res_sess.status_code == 200, f"Expected 200, got {res_sess.status_code}"
    data_sess = res_sess.json()
    print(f"Total sessions: {len(data_sess.get('sessions', []))}")

    print("\n✅ ALL WEB API ENDPOINTS EMPIRICALLY VERIFIED AND WORKING 100%!")

if __name__ == "__main__":
    test_web_endpoints()
