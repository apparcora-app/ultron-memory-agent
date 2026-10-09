"""
computer_contracts.py — OpenBot Computer Execution Contracts & Data Models for Project Ultron.

Strictly typed contracts for computer action execution, policy rules,
audit records, and browser perception snapshots.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    """Supported execution action categories for computer automation."""

    SHELL_EXEC = "SHELL_EXEC"
    BROWSER_NAVIGATE = "BROWSER_NAVIGATE"
    BROWSER_CLICK = "BROWSER_CLICK"
    BROWSER_TYPE = "BROWSER_TYPE"
    FS_READ = "FS_READ"
    FS_WRITE = "FS_WRITE"


class PolicyRule(BaseModel):
    """Rule defining permitted or denied computer action patterns."""

    model_config = ConfigDict(extra="forbid")

    name: str
    action_type: ActionType
    pattern: str
    effect: Literal["ALLOW", "DENY"]


class ComputerAction(BaseModel):
    """Specification of an intended computer execution action."""

    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    target: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    bot_id: str
    session_id: str


class AuditRecord(BaseModel):
    """Immutable audit trail record capturing action evaluation and execution state."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    timestamp: str
    action: ComputerAction
    status: Literal["PENDING", "PERMITTED", "REFUSED", "FAILED", "COMPLETED"]
    result_summary: Optional[str] = None
    error: Optional[str] = None


class BrowserSnapshot(BaseModel):
    """Perception snapshot of a browser state for computer vision and DOM navigation."""

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str
    aria_tree: str
    interactive_elements: List[Dict[str, Any]] = Field(default_factory=list)
    screenshot_b64: Optional[str] = None
