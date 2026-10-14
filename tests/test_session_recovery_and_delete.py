"""
test_session_recovery_and_delete.py — Verify chat session recovery and robust deletion.
"""

import json
from pathlib import Path
from ultron.memory.chat_session_manager import ChatSessionManager, SESSIONS_DIR


def test_recovered_authentic_sessions_exist():
    mgr = ChatSessionManager()
    sessions = mgr.list_sessions(user_id="boss")
    titles = [s["title"] for s in sessions]

    # Verify key historical chats are present
    assert "List all the public repos" in titles, "List all the public repos must be in session list"
    assert "Career & Job Applications Hub (PST.AG / Agentic AI)" in titles, "Career Hub must be in session list"
    assert "LinkedIn Optimization" in titles, "LinkedIn Optimization must be in session list"
    assert "Go to my google profile" in titles, "Google profile chat must be in session list"

    # Verify no synthetic test chats appear
    for t in titles:
        assert "confirm your active" not in t.lower(), f"Synthetic test leaked: {t}"
        assert "stitch verification" not in t.lower(), f"Synthetic test leaked: {t}"

    print(f"\n[PASS] Verified {len(sessions)} authentic sessions loaded with zero synthetic pollution.")


def test_robust_session_deletion(tmp_path):
    mgr = ChatSessionManager(sessions_dir=tmp_path)

    # Create dummy session
    session = mgr.create_session(user_id="boss", title="Temporary Session to Delete")
    sid = session["id"]

    # Test Case 1: Delete via raw session_id
    path = mgr._get_session_path("boss", sid)
    assert path.exists(), f"Session file should exist at {path}"

    ok = mgr.delete_session("boss", sid)
    assert ok is True, "delete_session should return True"
    assert not path.exists(), "Session file should be removed from disk"

    # Test Case 2: Delete via prefixed session_id (e.g. boss_chat_...)
    session2 = mgr.create_session(user_id="boss", title="Prefixed Session to Delete")
    sid2 = session2["id"]
    prefixed_id = f"boss_{sid2}"

    path2 = mgr._get_session_path("boss", sid2)
    assert path2.exists(), f"Session file 2 should exist at {path2}"

    ok2 = mgr.delete_session("boss", prefixed_id)
    assert ok2 is True, "delete_session with prefixed ID should return True"
    assert not path2.exists(), "Prefixed session file should be unlinked from disk"

    # Test Case 3: Delete via filename (with .json)
    session3 = mgr.create_session(user_id="boss", title="Filename Session to Delete")
    sid3 = session3["id"]
    filename_id = f"boss_{sid3}.json"

    path3 = mgr._get_session_path("boss", sid3)
    assert path3.exists(), f"Session file 3 should exist at {path3}"

    ok3 = mgr.delete_session("boss", filename_id)
    assert ok3 is True, "delete_session with filename ID should return True"
    assert not path3.exists(), "Filename session file should be unlinked from disk"

    print("[PASS] Verified robust deletion across clean ID, prefixed ID, and filename format.")
