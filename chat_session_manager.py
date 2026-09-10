"""
chat_session_manager.py — Ultron Protocol: Multi-Chat Session Manager and Persistent History Matrix.

Stores each conversation session on disk under ./data/sessions/{user_id}_{session_id}.json.
Supports auto-titling, full message history with tool-action logs, switching between sessions,
and synchronizing raw conversation history with MemoryAgent.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

SESSIONS_DIR = Path(__file__).parent / "data" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class ChatSessionManager:
    """Manages persistent multi-chat sessions on disk."""

    def __init__(self, sessions_dir: Path = SESSIONS_DIR) -> None:
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, user_id: str, session_id: str) -> Path:
        clean_user = re.sub(r"[^a-zA-Z0-9_-]", "_", (user_id or "boss").lower())
        clean_session = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
        return self.sessions_dir / f"{clean_user}_{clean_session}.json"

    def list_sessions(self, user_id: str = "boss") -> list[dict[str, Any]]:
        """List all chat sessions for the given user, sorted by updated_at descending."""
        clean_user = re.sub(r"[^a-zA-Z0-9_-]", "_", (user_id or "boss").lower())
        prefix = f"{clean_user}_"
        sessions = []

        for p in self.sessions_dir.glob(f"{prefix}*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "id": data.get("id"),
                    "title": data.get("title", "Untitled Directive"),
                    "module_id": data.get("module_id", "ultron_prime"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "message_count": len(data.get("messages", [])),
                    "preview": self._get_preview(data.get("messages", [])),
                })
            except Exception as e:
                print(f"  [SESSION] Failed reading {p}: {e}")

        # Sort newest first
        sessions.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
        return sessions

    def _get_preview(self, messages: list[dict[str, Any]]) -> str:
        for m in reversed(messages):
            if m.get("text"):
                return str(m.get("text"))[:80].replace("\n", " ").strip()
        return "New Directive Thread"

    def create_session(
        self,
        user_id: str = "boss",
        title: str = "New Directives",
        module_id: str = "ultron_prime",
    ) -> dict[str, Any]:
        """Create a new chat session on disk."""
        session_id = f"chat_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.utcnow().isoformat() + "Z"

        session_data: dict[str, Any] = {
            "id": session_id,
            "user_id": user_id,
            "title": title,
            "module_id": module_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "messages": [],
            "raw_history": [],
        }

        path = self._get_session_path(user_id, session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        return session_data

    def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        """Load a session from disk."""
        path = self._get_session_path(user_id, session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"  [SESSION] Error loading {path}: {e}")
            return None

    def save_session(self, user_id: str, session_id: str, data: dict[str, Any]) -> bool:
        """Save session data to disk."""
        data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        path = self._get_session_path(user_id, session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"  [SESSION] Error saving {path}: {e}")
            return False

    def rename_session(self, user_id: str, session_id: str, new_title: str) -> dict[str, Any] | None:
        """Update session title."""
        session = self.get_session(user_id, session_id)
        if not session:
            return None
        session["title"] = new_title.strip() or "Untitled Directive"
        self.save_session(user_id, session_id, session)
        return session

    def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete session file from disk."""
        path = self._get_session_path(user_id, session_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception as e:
                print(f"  [SESSION] Error deleting {path}: {e}")
                return False
        return False

    def append_turn(
        self,
        user_id: str,
        session_id: str,
        user_text: str,
        reply_text: str,
        model_used: str = "",
        model_display: str = "",
        tool_actions: list[dict[str, Any]] | None = None,
        files: list[dict[str, Any]] | None = None,
        module_id: str = "ultron_prime",
        skills_used: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Append a full multi-modal turn (user message + Ultron response) to the session.
        Auto-generates title if it is the first turn.
        """
        session = self.get_session(user_id, session_id)
        if not session:
            session = self.create_session(user_id=user_id, module_id=module_id)
            session_id = session["id"]

        now_time = datetime.now().strftime("%H:%M")

        user_msg = {
            "id": f"msg_{len(session['messages']) + 1}",
            "role": "user",
            "sender": "COMMANDER",
            "text": user_text,
            "timestamp": now_time,
            "files": files or [],
        }

        bot_msg = {
            "id": f"msg_{len(session['messages']) + 2}",
            "role": "assistant",
            "sender": "ULTRON CORE",
            "text": reply_text,
            "timestamp": now_time,
            "model_used": model_used,
            "model_display": model_display,
            "tool_actions": tool_actions or [],
            "skills_used": skills_used or [],
        }

        session["messages"].append(user_msg)
        session["messages"].append(bot_msg)

        raw_user = user_text or (f"[Attached {len(files)} files]" if files else "Analyze attached content.")
        session["raw_history"].append({"role": "user", "content": raw_user})
        session["raw_history"].append({"role": "assistant", "content": reply_text})

        if len(session["raw_history"]) > 40:
            session["raw_history"] = session["raw_history"][-40:]

        if len(session["messages"]) <= 2 or session.get("title") in ["New Directives", "Untitled Directive"]:
            auto_title = self._generate_title(user_text)
            if auto_title:
                session["title"] = auto_title

        session["module_id"] = module_id
        self.save_session(user_id, session_id, session)
        return session

    def _generate_title(self, text: str) -> str:
        clean = re.sub(r"[^\w\s-]", "", text).strip()
        words = clean.split()
        if not words:
            return "General Directive"
        title = " ".join(words[:5]).capitalize()
        return title[:35]
