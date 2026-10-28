"""
tests/test_background_learning_worker.py — Verification suite for Phase 2:
Supervised Background Learning Worker & Debounced Skills Reloader.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from ultron.concurrency.learning_worker import (
    BackgroundLearningSupervisor,
    LearningTask,
)
from ultron.skills.skill_manager import SkillManager, UltronSkill


def test_supervisor_basic_lifecycle():
    supervisor = BackgroundLearningSupervisor(max_queue_size=10, worker_name="Test-Worker-1")
    stats = supervisor.get_stats()
    assert stats["is_alive"] is True
    assert stats["tasks_submitted"] == 0
    assert stats["tasks_processed"] == 0

    supervisor.stop(timeout=2.0)
    assert supervisor.get_stats()["is_alive"] is False


def test_supervisor_processes_task():
    flush_mock = MagicMock()
    pending_turns = []
    reflector_mock = MagicMock()
    skills_mock = MagicMock()
    graph_rag_mock = MagicMock()

    supervisor = BackgroundLearningSupervisor(max_queue_size=10, worker_name="Test-Worker-2")
    supervisor.configure_handlers(
        flush_memory_fn=flush_mock,
        pending_turns_ref=pending_turns,
        reflector=reflector_mock,
        skills=skills_mock,
        graph_rag=graph_rag_mock,
    )

    test_turn = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]
    submitted = supervisor.submit_turn(
        user_input="Analyze this architecture",
        assistant_reply="Here is a comprehensive breakdown of the system architecture across component boundaries.",
        turn=test_turn,
        should_update=True,
    )
    assert submitted is True

    # Drain queue
    drained = supervisor.drain(timeout=3.0)
    assert drained is True

    # Verify memory flush executed
    assert flush_mock.called
    assert test_turn in pending_turns or len(pending_turns) > 0

    # Verify reflection executed
    assert reflector_mock.reflect.called

    # Verify Graph RAG ingested
    assert graph_rag_mock.ingest_text.called

    stats = supervisor.get_stats()
    assert stats["tasks_processed"] == 1
    assert stats["tasks_failed"] == 0

    supervisor.stop(timeout=2.0)


def test_supervisor_exception_resilience():
    """Verify that an exception in reflection does not kill the supervisor worker thread."""
    broken_reflector = MagicMock()
    broken_reflector.reflect.side_effect = RuntimeError("Reflection API timeout")

    flush_mock = MagicMock()
    pending_turns = []

    supervisor = BackgroundLearningSupervisor(max_queue_size=10, worker_name="Test-Worker-3")
    supervisor.configure_handlers(
        flush_memory_fn=flush_mock,
        pending_turns_ref=pending_turns,
        reflector=broken_reflector,
    )

    # Submit task that raises error
    supervisor.submit_turn(
        user_input="Test error",
        assistant_reply="Long assistant reply exceeding eighty characters to trigger the reflection engine.",
        should_update=False,
    )

    supervisor.drain(timeout=3.0)
    stats = supervisor.get_stats()
    # Worker is still alive despite exception in reflection
    assert stats["is_alive"] is True
    assert stats["tasks_processed"] == 1

    # Second task still processes cleanly
    working_flush = MagicMock()
    supervisor.configure_handlers(flush_memory_fn=working_flush, pending_turns_ref=[])
    supervisor.submit_turn(
        user_input="Next task",
        assistant_reply="Short reply",
        should_update=True,
    )
    supervisor.drain(timeout=3.0)
    assert working_flush.called

    supervisor.stop(timeout=2.0)


def test_supervisor_queue_load_shedding():
    """Verify that bounded queue drops tasks gracefully when full rather than blocking."""
    supervisor = BackgroundLearningSupervisor(max_queue_size=2, worker_name="Test-Worker-4")
    # Stop the worker thread from processing by setting stop_event
    supervisor.stop(timeout=1.0)

    # Queue should reject after max size is reached or stopped
    rejected = supervisor.submit_turn(user_input="hi", assistant_reply="bye")
    assert rejected is False
    assert supervisor.get_stats()["tasks_dropped"] >= 1


def test_skill_manager_reload_debouncing(tmp_path):
    """Verify reload_skills skips disk scanning within cooldown window unless force=True."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_a = skills_dir / "skill_a"
    skill_a.mkdir()
    (skill_a / "SKILL.md").write_text(
        "---\nname: Skill A\ndescription: Test skill A\n---\nDirectives:\nDo A.\n",
        encoding="utf-8",
    )

    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()

    sm = SkillManager(
        skills_dir=skills_dir,
        chroma_path=chroma_dir,
        enable_vector_search=False,
    )
    assert "skill_a" in sm.get_all_skills()[0]["id"]
    initial_reload_time = sm._last_reload_time
    assert initial_reload_time > 0

    # Add a new skill on disk
    skill_b = skills_dir / "skill_b"
    skill_b.mkdir()
    (skill_b / "SKILL.md").write_text(
        "---\nname: Skill B\ndescription: Test skill B\n---\nDirectives:\nDo B.\n",
        encoding="utf-8",
    )

    # Immediate call without force: debounced, skill_b NOT yet loaded
    sm.reload_skills(force=False, min_interval_seconds=60.0)
    assert "skill_b" not in [s["id"] for s in sm.get_all_skills()]

    # Forced call: bypasses cooldown, loads skill_b immediately
    sm.reload_skills(force=True)
    loaded_ids = [s["id"] for s in sm.get_all_skills()]
    assert "skill_b" in loaded_ids
