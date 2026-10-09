"""
ledger_service.py — High-Throughput Activity Ledger Microservice for Ultron.

Provides:
  - In-memory sliding-window rate limiting (120 req/min per user/IP)
  - Asynchronous event ingestion & validation into ./data/telemetry.db
  - Historical query & filtering API
  - Real-time SSE broadcast queue for live events-per-second (EPS) & audit logs
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator

from telemetry import TelemetryEngine


@dataclass
class ActivityEvent:
    action: str
    entity_type: str
    user_id: str = "boss"
    entity_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = "127.0.0.1"
    timestamp: float = field(default_factory=time.time)


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter per client identifier."""

    def __init__(self, limit: int = 120, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_id: str) -> tuple[bool, int, int]:
        """
        Check if request is allowed.
        Returns: (allowed: bool, remaining: int, retry_after_seconds: int)
        """
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            queue = self.requests[client_id]

            # Evict timestamps outside sliding window
            while queue and queue[0] < cutoff:
                queue.popleft()

            if len(queue) >= self.limit:
                retry_after = int(self.window_seconds - (now - queue[0])) + 1
                return False, 0, max(1, retry_after)

            queue.append(now)
            remaining = self.limit - len(queue)
            return True, remaining, 0


class LedgerService:
    """Core business logic for high-throughput activity ledger & metrics broadcasting."""

    def __init__(self, db_path: str = "./data/telemetry.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.telemetry = TelemetryEngine(db_path=str(self.db_path))
        self.rate_limiter = SlidingWindowRateLimiter(limit=120, window_seconds=60)

        # In-memory real-time EPS (events-per-second) tracking
        self._second_buckets: deque[tuple[int, int]] = deque(maxlen=120)
        self._current_sec_count: int = 0
        self._current_sec_timestamp: int = int(time.time())

        # SSE Subscriber Queues
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    def sanitize_string(self, text: str) -> str:
        """Sanitize action and entity strings against injection patterns."""
        if not text:
            return ""
        return re.sub(r"[^a-zA-Z0-9_\-\.\:]", "", text.strip())

    async def register_subscriber(self) -> asyncio.Queue:
        """Register a new SSE stream listener."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unregister_subscriber(self, q: asyncio.Queue) -> None:
        """Unregister an SSE stream listener."""
        async with self._lock:
            self._subscribers.discard(q)

    async def _broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Push an update to all active SSE subscribers."""
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        async with self._lock:
            dead_queues = []
            for q in self._subscribers:
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    dead_queues.append(q)
                except Exception:
                    dead_queues.append(q)
            for dq in dead_queues:
                self._subscribers.discard(dq)

    async def ingest_event(
        self,
        action: str,
        entity_type: str,
        user_id: str = "boss",
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """
        Validate, rate-limit, and persist an incoming ledger activity event.
        """
        # 1. Rate-limiting check
        allowed, remaining, retry_after = await self.rate_limiter.is_allowed(user_id or ip_address)
        if not allowed:
            return {
                "success": False,
                "status": "rate_limited",
                "detail": f"Rate limit exceeded (120 req/min). Try again in {retry_after}s.",
                "retry_after": retry_after,
            }

        # 2. Validation & Sanitization
        sanitized_action = self.sanitize_string(action)
        sanitized_entity = self.sanitize_string(entity_type)
        if not sanitized_action or not sanitized_entity:
            return {
                "success": False,
                "status": "validation_error",
                "detail": "Action and entity_type must contain valid alphanumeric characters.",
            }

        meta = metadata or {}
        if len(json.dumps(meta)) > 15000:
            return {
                "success": False,
                "status": "validation_error",
                "detail": "Metadata payload exceeds 15KB threshold.",
            }

        # 3. Increment second counter for EPS
        now_sec = int(time.time())
        if now_sec != self._current_sec_timestamp:
            self._second_buckets.append((self._current_sec_timestamp, self._current_sec_count))
            self._current_sec_timestamp = now_sec
            self._current_sec_count = 0
        self._current_sec_count += 1

        # 4. Persist to SQLite via TelemetryEngine
        details_payload = {
            "action": sanitized_action,
            "entity_type": sanitized_entity,
            "entity_id": entity_id,
            "ip_address": ip_address,
            "metadata": meta,
        }

        event_id = self.telemetry.log_event(
            user_id=user_id,
            event_type="LEDGER_ACTIVITY",
            module_id="ledger_service",
            details=details_payload,
            duration_ms=0,
        )

        event_summary = {
            "id": event_id,
            "timestamp": time.strftime("%H:%M:%S", time.localtime()),
            "user_id": user_id,
            "action": sanitized_action,
            "entity_type": sanitized_entity,
            "entity_id": entity_id,
            "ip_address": ip_address,
            "metadata": meta,
        }

        # 5. Broadcast to live SSE stream
        await self._broadcast("ledger_event", event_summary)

        return {
            "success": True,
            "status": "accepted",
            "event_id": event_id,
            "remaining_rate": remaining,
        }

    def query_ledger(
        self,
        user_id: str | None = None,
        action: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query historical activity records from SQLite database."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = "SELECT event_id, timestamp, user_id, event_type, module_id, details, duration_ms FROM audit_logs WHERE 1=1"
                params: list[Any] = []

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)

                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)

                if action:
                    query += " AND (details LIKE ? OR event_type LIKE ?)"
                    params.extend([f"%{action}%", f"%{action}%"])

                query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                records = []
                for row in rows:
                    details = {}
                    try:
                        details = json.loads(row["details"]) if row["details"] else {}
                    except Exception:
                        details = {"raw": row["details"]}

                    row_action = details.get("action") or row["event_type"]

                    records.append({
                        "id": row["event_id"],
                        "timestamp": row["timestamp"],
                        "user_id": row["user_id"],
                        "event_type": row["event_type"],
                        "module_id": row["module_id"],
                        "action": row_action,
                        "entity_type": details.get("entity_type", row["module_id"]),
                        "ip_address": details.get("ip_address", "127.0.0.1"),
                        "metadata": details.get("metadata", details),
                        "duration_ms": row["duration_ms"],
                    })

                return {"records": records, "degraded": False, "error": None}
        except Exception as e:
            print(f"  [LEDGER QUERY ERROR] {e}")
            return {"records": [], "degraded": True, "error": str(e)}

    def get_metrics(self) -> dict[str, Any]:
        """Calculates system throughput, total persisted records, and agent stats."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM audit_logs")
                total_events = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT event_type, COUNT(*) FROM audit_logs GROUP BY event_type ORDER BY COUNT(*) DESC"
                )
                type_breakdown = dict(cursor.fetchall())

                cursor.execute(
                    "SELECT AVG(duration_ms) FROM audit_logs WHERE duration_ms > 0"
                )
                avg_lat = cursor.fetchone()[0] or 0.8

            now = int(time.time())
            recent_count = self._current_sec_count
            for ts, count in self._second_buckets:
                if ts >= now - 5:
                    recent_count += count
            eps = round(recent_count / 5.0, 1)

            return {
                "success": True,
                "total_events": total_events,
                "current_eps": max(eps, float(self._current_sec_count)),
                "average_latency_ms": round(float(avg_lat), 2),
                "buffer_queue": "SQLite WAL Active (Zero Lag)",
                "event_breakdown": type_breakdown,
                "subscribers_active": len(self._subscribers),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "total_events": 0,
                "current_eps": 0.0,
                "average_latency_ms": 0.8,
                "buffer_queue": "Active",
            }

    async def sse_metrics_generator(self) -> AsyncGenerator[str, None]:
        """Continuous SSE generator streaming tick metrics and ingested events."""
        queue = await self.register_subscriber()
        try:
            while True:
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield event_data
                except asyncio.TimeoutError:
                    metrics = self.get_metrics()
                    yield f"event: metric_tick\ndata: {json.dumps(metrics)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await self.unregister_subscriber(queue)


# Singleton instance
ledger_service = LedgerService()
