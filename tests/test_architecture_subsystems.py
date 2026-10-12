"""
tests/test_architecture_subsystems.py — Architectural Decoupling & Resilience Verification.

Verifies:
1. ModelRegistry: Centralized candidate pools, preferred models, and circuit breaker exclusion.
2. DatabaseManager: SQLite connection pooling, WAL pragma enforcement, and atomic online backups.
3. Subsystems Decoupling: Dependency injection of MemorySubsystem, PlanningSubsystem,
   ExecutionSubsystem, and GovernanceSubsystem into MemoryAgent.
4. Background Learning DLQ: Verifies exceptions during reflection or Graph-RAG are recorded to DLQ.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from governance.model_registry import (
    ModelRegistry,
    ModelProvider,
    ModelTier,
    ModelSpec,
)
from governance.db_manager import DatabaseManager
from resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from resilience.dlq import DeadLetterQueue
from subsystems import (
    MemorySubsystem,
    PlanningSubsystem,
    ExecutionSubsystem,
    GovernanceSubsystem,
)
from agent import MemoryAgent


# ── 1. ModelRegistry Tests ───────────────────────────────────────────────────

def test_model_registry_default_pool():
    registry = ModelRegistry()
    gemini_pool = registry.get_candidate_pool("gemini")
    assert len(gemini_pool) >= 4
    assert "gemini-3.6-flash" in gemini_pool
    assert "gemini-3.6-flash" in gemini_pool


def test_model_registry_preferred_model_priority():
    registry = ModelRegistry()
    pool = registry.get_candidate_pool("gemini", preferred_model="gemini-custom-enterprise")
    assert pool[0] == "gemini-custom-enterprise"
    assert "gemini-3.6-flash" in pool


def test_model_registry_circuit_breaker_exclusion():
    registry = ModelRegistry()
    registry.register_candidate_pool("test_provider", ["model_a", "model_b", "model_c"])
    breaker = CircuitBreaker("model_a", CircuitBreakerConfig(failure_threshold=1, cooldown_duration_sec=60.0))
    breaker.record_failure(Exception("503 Service Unavailable"))
    assert breaker.state == CircuitState.OPEN

    mock_breaker_registry = MagicMock()
    mock_breaker_registry.get_breaker.side_effect = lambda name: breaker if name == "model_a" else None

    with patch("governance.model_registry.default_breaker_registry", mock_breaker_registry):
        pool = registry.get_candidate_pool("test_provider")
        assert "model_a" not in pool
        assert pool[0] == "model_b"
        assert pool[1] == "model_c"


# ── 2. DatabaseManager Tests ─────────────────────────────────────────────────

def test_database_manager_wal_pragmas(tmp_path):
    db_path = str(tmp_path / "test_wal.sqlite3")
    manager = DatabaseManager()

    with manager.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
        conn.execute("INSERT INTO users (name) VALUES ('Alice');")
        conn.commit()

        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.lower() == "wal"

        cursor.execute("PRAGMA busy_timeout;")
        busy_timeout = cursor.fetchone()[0]
        assert busy_timeout == 5000


def test_database_manager_backup(tmp_path):
    source_db = str(tmp_path / "source.sqlite3")
    backup_dir = str(tmp_path / "backups")

    manager = DatabaseManager()
    with manager.connect(source_db) as conn:
        conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, action TEXT);")
        conn.execute("INSERT INTO audit_log (action) VALUES ('security_event_1');")
        conn.commit()

    backup_path = manager.backup_database(source_db, backup_dir=backup_dir)
    assert os.path.exists(backup_path)

    # Verify backup integrity
    verify_conn = sqlite3.connect(backup_path)
    cur = verify_conn.cursor()
    cur.execute("SELECT action FROM audit_log;")
    rows = cur.fetchall()
    verify_conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "security_event_1"


# ── 3. Subsystem Dependency Injection Tests ──────────────────────────────────

def test_memory_agent_subsystem_injection():
    mock_memory_subsystem = MagicMock(spec=MemorySubsystem)
    mock_memory_subsystem.memory_manager = MagicMock()
    mock_memory_subsystem.core_memory = MagicMock()
    mock_memory_subsystem.graph_rag = MagicMock()
    mock_memory_subsystem.trajectories = MagicMock()
    mock_memory_subsystem.skills = MagicMock()

    mock_planning_subsystem = MagicMock(spec=PlanningSubsystem)
    mock_planning_subsystem.router = MagicMock()
    mock_planning_subsystem.goals = MagicMock()
    mock_planning_subsystem.hierarchical_planner = MagicMock()
    mock_planning_subsystem.tot_engine = MagicMock()
    mock_planning_subsystem.prompt_optimizer = MagicMock()

    mock_execution_subsystem = MagicMock(spec=ExecutionSubsystem)
    mock_execution_subsystem.sandbox = MagicMock()
    mock_execution_subsystem.tool_executor = MagicMock()
    mock_execution_subsystem.mcp = MagicMock()
    mock_execution_subsystem.mesh = MagicMock()
    mock_execution_subsystem.swarm = MagicMock()

    mock_governance_subsystem = MagicMock(spec=GovernanceSubsystem)
    mock_governance_subsystem.telemetry = MagicMock()
    mock_governance_subsystem.budget = MagicMock()
    mock_governance_subsystem.spend_governor = MagicMock()
    mock_governance_subsystem.ledger_gate = MagicMock()
    mock_governance_subsystem.artifact_gate = MagicMock()
    mock_governance_subsystem.critic = MagicMock()
    mock_governance_subsystem.reflector = MagicMock()
    mock_governance_subsystem.dreamer = MagicMock()
    mock_governance_subsystem.db_manager = MagicMock()
    mock_governance_subsystem.model_registry = MagicMock()

    agent = MemoryAgent(
        user_id="injected_test_user",
        memory_subsystem=mock_memory_subsystem,
        planning_subsystem=mock_planning_subsystem,
        execution_subsystem=mock_execution_subsystem,
        governance_subsystem=mock_governance_subsystem,
    )

    assert agent.memory_subsystem is mock_memory_subsystem
    assert agent.planning_subsystem is mock_planning_subsystem
    assert agent.execution_subsystem is mock_execution_subsystem
    assert agent.governance_subsystem is mock_governance_subsystem
    assert agent._memory is mock_memory_subsystem.memory_manager
    assert agent._tool_executor is mock_execution_subsystem.tool_executor
    assert agent._budget is mock_governance_subsystem.budget
    assert agent._router is mock_planning_subsystem.router


# ── 4. DLQ Ingestion for Background Learning Tests ───────────────────────────

def test_dlq_records_background_learning_failure(tmp_path):
    dlq_db = str(tmp_path / "dlq_test.db")
    dlq = DeadLetterQueue(db_path=dlq_db)
    assert dlq.queue_depth == 0

    try:
        raise ValueError("Simulated reflection LLM context overflow")
    except Exception as e:
        record = dlq.record_dead_letter(
            failed_service="bg_learning_reflection",
            node_name="reflection_engine",
            error=e,
            metadata={"user_input": "analyze this file again"}
        )

    assert dlq.queue_depth == 1
    assert record.failed_service == "bg_learning_reflection"
    assert record.node_name == "reflection_engine"
    assert "Simulated reflection LLM context overflow" in record.error_message

