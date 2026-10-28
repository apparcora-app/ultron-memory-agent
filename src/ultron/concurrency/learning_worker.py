"""
ultron.concurrency.learning_worker — Supervised Background Learning Worker.

Provides bounded, thread-safe asynchronous processing for:
1. Persistent memory flushes (Mem0 / ChromaDB / Qdrant)
2. Autonomous reflection and skill evolution
3. Graph RAG entity-triple ingestion with SQLite write serialization

Eliminates unmanaged daemon threads, thread race conditions on shared memory,
and disk thrashing caused by unthrottled skill reloading.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("ultron.concurrency.learning_worker")


@dataclass
class LearningTask:
    user_input: str
    assistant_reply: str
    tool_actions: list[dict[str, Any]] = field(default_factory=list)
    turn: list[dict[str, str]] = field(default_factory=list)
    should_update: bool = False
    matched_skill_ids: list[str] | None = None
    skill_context: str = ""
    user_id: str = "default_operator"
    created_at: float = field(default_factory=time.time)


class BackgroundLearningSupervisor:
    """
    Supervises background post-turn learning, memory persistence, and graph ingestion.
    Uses a bounded queue and dedicated worker thread to decouple cognitive response latency
    from heavy vector and graph persistence.
    """

    def __init__(
        self,
        max_queue_size: int = 100,
        worker_name: str = "Ultron-BgLearningWorker",
    ) -> None:
        self.max_queue_size = max_queue_size
        self._queue: queue.Queue[LearningTask | None] = queue.Queue(maxsize=max_queue_size)
        self._sqlite_lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Diagnostics
        self._tasks_submitted: int = 0
        self._tasks_processed: int = 0
        self._tasks_failed: int = 0
        self._tasks_dropped: int = 0

        # References to subsystems configured at runtime
        self._flush_memory_fn: Callable[[], None] | None = None
        self._pending_turns_ref: list[Any] | None = None
        self._reflector: Any = None
        self._skills: Any = None
        self._graph_rag: Any = None

        self._thread = threading.Thread(
            target=self._worker_loop,
            name=worker_name,
            daemon=True,
        )
        self._thread.start()
        logger.info(f"BackgroundLearningSupervisor started [{worker_name}, queue_size={max_queue_size}].")

    def configure_handlers(
        self,
        flush_memory_fn: Callable[[], None] | None = None,
        pending_turns_ref: list[Any] | None = None,
        reflector: Any = None,
        skills: Any = None,
        graph_rag: Any = None,
    ) -> None:
        """Bind subsystem instances to the background supervisor."""
        self._flush_memory_fn = flush_memory_fn
        self._pending_turns_ref = pending_turns_ref
        self._reflector = reflector
        self._skills = skills
        self._graph_rag = graph_rag

    def submit_turn(
        self,
        user_input: str,
        assistant_reply: str,
        tool_actions: list[dict[str, Any]] | None = None,
        turn: list[dict[str, str]] | None = None,
        should_update: bool = False,
        matched_skill_ids: list[str] | None = None,
        skill_context: str = "",
        user_id: str = "default_operator",
    ) -> bool:
        """
        Thread-safe, non-blocking task submission.
        Returns True if enqueued successfully, False if dropped due to full queue.
        """
        if self._stop_event.is_set():
            logger.warning("BackgroundLearningSupervisor is shutting down; task rejected.")
            self._tasks_dropped += 1
            return False

        task = LearningTask(
            user_input=user_input,
            assistant_reply=assistant_reply,
            tool_actions=tool_actions or [],
            turn=turn or [],
            should_update=should_update,
            matched_skill_ids=matched_skill_ids,
            skill_context=skill_context,
            user_id=user_id,
        )

        try:
            self._queue.put_nowait(task)
            self._tasks_submitted += 1
            return True
        except queue.Full:
            logger.error(
                f"BackgroundLearningSupervisor queue full ({self.max_queue_size} items). "
                f"Shedding load for task from user={user_id}."
            )
            self._tasks_dropped += 1
            return False

    def _worker_loop(self) -> None:
        """Sequential consumer loop executing background tasks safely."""
        while not self._stop_event.is_set():
            try:
                task = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if task is None:
                # Sentinel indicating termination
                self._queue.task_done()
                break

            try:
                self._process_single_task(task)
                self._tasks_processed += 1
            except Exception as e:
                self._tasks_failed += 1
                logger.error(f"Background task processing error: {e}", exc_info=True)
            finally:
                self._queue.task_done()

    def _process_single_task(self, task: LearningTask) -> None:
        """Execute the individual stages of background learning for a single turn."""
        # 1. Memory commit
        if task.should_update and self._flush_memory_fn and self._pending_turns_ref is not None:
            try:
                self._pending_turns_ref.extend(task.turn)
                self._flush_memory_fn()
            except Exception as mem_err:
                logger.error(f"[BG Memory Flush Error] {mem_err}")

        # 2. Autonomous Reflection & Skill Evolution
        if self._reflector and task.assistant_reply and len(task.assistant_reply) > 80:
            try:
                skill_active = bool(
                    task.skill_context
                    and task.skill_context != "Standard Ultron Core Protocols Active."
                )
                reflection = self._reflector.reflect(
                    user_input=task.user_input,
                    assistant_reply=task.assistant_reply,
                    tool_actions=task.tool_actions,
                    skill_matched=skill_active,
                    matched_skill_ids=task.matched_skill_ids,
                )
                if reflection and getattr(reflection, "lesson_stored", False):
                    logger.info(f"[LEARN] Lesson stored (score {reflection.score}/10): {reflection.lesson_text[:80]}")
                if reflection and (getattr(reflection, "skill_written", False) or getattr(reflection, "skill_evolved", False)):
                    if self._skills and hasattr(self._skills, "reload_skills"):
                        self._skills.reload_skills(force=False)
            except Exception as ref_err:
                logger.warning(f"[BG Reflection Error] {ref_err}")

        # 3. Knowledge Graph Ingestion (Serialized with Mutex)
        if self._graph_rag and hasattr(self._graph_rag, "ingest_text"):
            try:
                turn_text = f"User: {task.user_input}\nAssistant: {task.assistant_reply}"
                if task.tool_actions:
                    turn_text += f"\nTool Actions: {json.dumps(task.tool_actions[:3])}"

                with self._sqlite_lock:
                    self._graph_rag.ingest_text(turn_text, source_context="chat_turn")
            except Exception as graph_err:
                logger.warning(f"[BG Graph RAG Error] {graph_err}")

    def drain(self, timeout: float = 5.0) -> bool:
        """Wait until all queued tasks are processed."""
        deadline = time.time() + timeout
        while not self._queue.empty():
            if time.time() > deadline:
                return False
            time.sleep(0.05)
        self._queue.join()
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """Gracefully stop the worker thread and join."""
        self._stop_event.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

        if self._thread.is_alive():
            self._thread.join(timeout=timeout)
        try:
            logger.info("BackgroundLearningSupervisor stopped.")
        except Exception:
            pass

    def get_stats(self) -> dict[str, Any]:
        """Return operational queue metrics."""
        return {
            "queue_depth": self._queue.qsize(),
            "tasks_submitted": self._tasks_submitted,
            "tasks_processed": self._tasks_processed,
            "tasks_failed": self._tasks_failed,
            "tasks_dropped": self._tasks_dropped,
            "is_alive": self._thread.is_alive(),
        }
