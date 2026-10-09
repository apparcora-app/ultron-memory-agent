import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
import os
import hashlib
from fastapi.testclient import TestClient

# Must set env before importing app
import secrets
_test_key1 = os.environ.get("ULTRON_TEST_API_KEY_1") or secrets.token_hex(16)
_test_key2 = os.environ.get("ULTRON_TEST_API_KEY_2") or secrets.token_hex(16)
os.environ["API_KEYS"] = f"{_test_key1}, {_test_key2}"
os.environ.pop('TESTING', None)

from app import app
from core.auth import current_caller_id
from governance.rate_limiter import default_rate_limiter
from governance.spend_governor import default_spend_governor

client = TestClient(app)

def test_no_key():
    print("\n[TEST] Missing API Key")
    response = client.get("/api/swarm/squad")
    assert response.status_code == 401
    print("Result: 401 Missing Key - PASSED")

def test_wrong_key():
    print("\n[TEST] Invalid API Key")
    response = client.get("/api/swarm/squad", headers={"X-API-Key": "bad-key"})
    assert response.status_code == 401
    print("Result: 401 Invalid Key - PASSED")

def test_valid_key():
    print("\n[TEST] Valid API Key")
    response = client.get("/api/swarm/squad", headers={"X-API-Key": _test_key1})
    # It might return 200 or something else if not fully initialized, but not 401
    assert response.status_code != 401
    print(f"Result: {response.status_code} Valid Key - PASSED")

def test_rate_limiter_per_key():
    print("\n[TEST] Rate Limiter Attribution per Key")
    # Simulate first caller
    current_caller_id.set("hash-caller-A")
    bucket_A = default_rate_limiter._get_bucket("gemini")
    
    # Simulate second caller
    current_caller_id.set("hash-caller-B")
    bucket_B = default_rate_limiter._get_bucket("gemini")
    
    assert bucket_A is not bucket_B
    print("Result: Rate Limiter buckets are isolated per caller - PASSED")

def test_spend_governor_per_key():
    print("\n[TEST] Spend Governor Attribution per Key")
    current_caller_id.set("hash-caller-A")
    default_spend_governor.record_turn_spend("session-1", "turn-1", "claude-sonnet", 100, 100)
    totals_A = default_spend_governor.get_session_totals("session-1")
    
    current_caller_id.set("hash-caller-B")
    # Caller B should have 0 tokens for session-1
    totals_B = default_spend_governor.get_session_totals("session-1")
    
    assert totals_A["total_tokens"] == 200
    assert totals_B["total_tokens"] == 0
    print("Result: Spend Governor totals are isolated per caller - PASSED")

def test_health_check_no_key():
    print("\n[TEST] Health Check Bypass")
    # Assuming health isn't implemented but let's check what the middleware does
    # The middleware skips /health
    # We don't have a /health endpoint in app.py maybe? Let's see if 404
    response = client.get("/health")
    # As long as it's not 401
    assert response.status_code != 401
    print("Result: Health endpoint bypasses auth - PASSED")

if __name__ == "__main__":
    print("--- API Auth & Caller Identity Tests ---")
    test_no_key()
    test_wrong_key()
    test_valid_key()
    test_health_check_no_key()
    test_rate_limiter_per_key()
    test_spend_governor_per_key()
    print("\nAll tests passed successfully.")
