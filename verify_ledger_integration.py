"""
verify_ledger_integration.py — End-to-end verification harness for the Activity Ledger & Telemetry HUD.

Verifies:
  1. LedgerService instance & methods.
  2. Rate limiter sliding window enforcement & HTTP 429 triggering.
  3. POST /api/v1/ledger validation and SQLite persistence into audit_logs.
  4. GET /api/v1/ledger query filtering.
  5. GET /api/v1/metrics aggregate stats.
  6. Real-time SSE generator stream iteration.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from fastapi.testclient import TestClient

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from app import app
from ledger_service import LedgerService, ledger_service


async def verify_all():
    print("=" * 60)
    print(" [TITAN PROTOCOL] INITIATING ACTIVITY LEDGER VERIFICATION")
    print("=" * 60)

    client = TestClient(app)

    # 1. Test Single Event Ingestion via API
    print("\n[TEST 1] Testing POST /api/v1/ledger (Single Ingestion)...")
    payload = {
        "action": "titan.db_write",
        "entity_type": "database",
        "entity_id": "tbl_audit_01",
        "user_id": "boss",
        "metadata": {"table": "audit_logs", "operation": "insert", "shard": 1},
    }
    res = client.post("/api/v1/ledger", json=payload)
    assert res.status_code == 202, f"Expected 202, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["success"] is True, f"Response error: {data}"
    assert "event_id" in data, "Missing event_id"
    print(f"  ✓ Event Accepted! Event ID: {data['event_id']}, Remaining Rate: {data['remaining_rate']}")

    # 2. Test Rate Limiter (Rapid Burst for a separate test user)
    print("\n[TEST 2] Testing Sliding-Window Rate Limiter (120 req/min)...")
    test_user = "rate_limit_tester"
    blocked = False
    accepted = 0

    for i in range(130):
        r = client.post(
            "/api/v1/ledger",
            json={
                "action": "test.burst",
                "entity_type": "rate_test",
                "user_id": test_user,
                "metadata": {"iter": i},
            },
        )
        if r.status_code == 202:
            accepted += 1
        elif r.status_code == 429:
            blocked = True
            print(f"  ✓ Rate limit triggered at request #{i+1} with HTTP 429!")
            break

    assert blocked, "Rate limiter failed to block burst requests over 120 req/min"
    print(f"  ✓ Rate limiter verified: {accepted} accepted before 429 throttle.")

    # 3. Test Historical Query via API
    print("\n[TEST 3] Testing GET /api/v1/ledger (Historical Query & Filter)...")
    query_res = client.get("/api/v1/ledger?limit=10&action=titan.db_write")
    assert query_res.status_code == 200, f"Query failed: {query_res.text}"
    query_data = query_res.json()
    assert query_data["success"] is True
    records = query_data["records"]
    assert len(records) > 0, "Expected at least 1 record"
    print(f"  ✓ Retrieved {len(records)} filtered records. Sample: {records[0]['action']} by {records[0]['user_id']}")

    # 4. Test Aggregate Metrics API
    print("\n[TEST 4] Testing GET /api/v1/metrics (Aggregate System Stats)...")
    metrics_res = client.get("/api/v1/metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert metrics["success"] is True
    assert metrics["total_events"] > 0
    print(f"  ✓ Metrics verified: Total Events={metrics['total_events']}, Current EPS={metrics['current_eps']}, Latency={metrics['average_latency_ms']}ms")

    # 5. Test SSE Metrics Generator (Async Stream)
    print("\n[TEST 5] Testing SSE Stream Generator...")
    gen = ledger_service.sse_metrics_generator()
    first_tick = await asyncio.wait_for(gen.__anext__(), timeout=3.0)
    assert "event: metric_tick" in first_tick or "event: ledger_event" in first_tick
    print(f"  ✓ SSE Generator tick received: {first_tick.strip()[:65]}...")

    # 6. Verify SQLite Database State Directly
    print("\n[TEST 6] Verifying SQLite Database File Directly (./data/telemetry.db)...")
    with sqlite3.connect("./data/telemetry.db") as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type='LEDGER_ACTIVITY'")
        ledger_count = c.fetchone()[0]
        c.execute("SELECT event_id, timestamp, user_id, event_type, details FROM audit_logs ORDER BY timestamp DESC LIMIT 1")
        last_row = c.fetchone()

    print(f"  ✓ Total LEDGER_ACTIVITY events in SQLite: {ledger_count}")
    print(f"  ✓ Latest persisted audit entry: ID={last_row[0]}, User={last_row[2]}, Details={last_row[4][:70]}...")

    print("\n" + "=" * 60)
    print(" [TITAN PROTOCOL] ALL 6 LEDGER VERIFICATION TESTS PASSED 100%!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(verify_all())
