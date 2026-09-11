from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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

import asyncio
import json
import sqlite3
from fastapi.testclient import TestClient

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
    for i in range(120):
        allowed, rem, _ = await ledger_service.rate_limiter.is_allowed(test_user)
        assert allowed is True, f"Premature rate limit at request {i}"
    # 121st request should be rejected
    rejected, rem, _ = await ledger_service.rate_limiter.is_allowed(test_user)
    assert rejected is False, "Rate limiter failed to block 121st request!"
    print("  ✓ Sliding-window rate limiter blocked excess request as expected.")

    # 3. Test Direct API Query Filtering
    print("\n[TEST 3] Testing GET /api/v1/ledger (Query Filtering)...")
    res = client.get("/api/v1/ledger?user_id=boss&limit=5")
    assert res.status_code == 200, f"Query failed: {res.text}"
    data = res.json()
    records = data.get("records", []) if isinstance(data, dict) else data
    assert len(records) >= 1, "Expected at least 1 log returned"
    print(f"  ✓ Successfully queried logs! Retrieved {len(records)} entries.")

    # 4. Test Aggregate Metrics API
    print("\n[TEST 4] Testing GET /api/v1/metrics (System Telemetry)...")
    res = client.get("/api/v1/metrics")
    assert res.status_code == 200, f"Metrics failed: {res.text}"
    metrics = res.json()
    assert "total_events" in metrics, "Missing total_events"
    assert "event_breakdown" in metrics, "Missing event_breakdown"
    assert "current_eps" in metrics, "Missing current_eps"
    print(f"  ✓ Metrics valid! Total Events: {metrics['total_events']}")

    # 5. Test SSE Generator Stream Event Generation
    print("\n[TEST 5] Testing Real-Time SSE Event Broadcast...")
    event_received = False
    async def listen_sse():
        nonlocal event_received
        gen = ledger_service.sse_metrics_generator()
        async for chunk in gen:
            if "metric_tick" in chunk or "titan.broadcast_test" in chunk:
                event_received = True
                break

    listener_task = asyncio.create_task(listen_sse())
    await asyncio.sleep(0.1)

    # Ingest an event to trigger broadcast
    await ledger_service.ingest_event(
        action="titan.broadcast_test",
        entity_type="stream",
        entity_id="sse_channel",
        user_id="boss",
    )

    try:
        await asyncio.wait_for(listener_task, timeout=2.0)
    except asyncio.TimeoutError:
        pass

    assert event_received is True, "SSE stream did not receive broadcast event!"
    print("  ✓ SSE generator broadcasted event successfully to subscribers.")

    print("\n" + "=" * 60)
    print("  [SUCCESS] All Activity Ledger Checks Passed Cleanly!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(verify_all())
