"""
tool_bridge.py — OpenBot Tool Bridge & Integrated Dispatcher for Project Ultron.

Provides:
  1. Anthropic-compatible tool schemas matching ULTRON_TOOLS specification:
     - computer_shell: Execute shell command or python script in sandbox.
     - browser_navigate: Open a web page and return the compact ARIA snapshot.
     - browser_act: Click, type, or press keys on target numbered ARIA elements.
     - take_the_wheel_request: Explicit tool call when model detects unresolvable challenge.
  2. Strict Pydantic v2 boundary models for tool inputs.
  3. ComputerToolDispatcher:
     Chains the entire pipeline in the mandated sequence:
       ComputerAction
       -> HandoffManager.is_takeover_active(session_id) check (reject immediately with 'TAKEOVER_IN_PROGRESS' if True)
       -> PolicyEvaluator.evaluate()
       -> AuditLogger.log_intent()
       -> Sandbox / Browser Execution
       -> AuditLogger.log_result()
     Handles errors gracefully and returns clean JSON strings back to Ultron's tool execution engine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ultron.execution.computer_contracts import (
    ActionType,
    BrowserSnapshot,
    ComputerAction,
    PolicyRule,
)
from ultron.execution.drivers.base_sandbox import BaseSandbox
from ultron.execution.drivers.browser_controller import BrowserController
from ultron.execution.gateway.audit_logger import DEFAULT_AUDIT_LOG_PATH, AuditLogger
from ultron.execution.gateway.policy_evaluator import PolicyEvaluator
from ultron.execution.session_registry import (
    DEFAULT_SESSION_TTL_SECONDS,
    SessionRegistry,
)
from ultron.execution.takeover.handoff_manager import HandoffManager

logger = logging.getLogger(__name__)


# ── Anthropic Tool Schemas (ULTRON_TOOLS Style) ──────────────────────────────

COMPUTER_TOOLS: list[dict[str, Any]] = [
    {
        "name": "computer_shell",
        "description": "Execute a shell command or python script in the isolated sandbox. Returns stdout, stderr, and exit code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact shell command or script to execute inside the isolated sandbox.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds (default: 60).",
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional session identifier to scope sandbox workspace (default: 'default').",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "browser_navigate",
        "description": "Open a web page and return the compact ARIA accessibility tree snapshot without raw HTML bloat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The web URL to navigate to (must be an allowlisted public HTTP/HTTPS target).",
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional session identifier to track browser lifecycle (default: 'default').",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_act",
        "description": "Click, type, or press keys on target numbered ARIA elements returned by browser_navigate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["click", "type", "press"],
                    "description": "Action type: 'click' to click an element, 'type' to fill text, 'press' to press a key.",
                },
                "element_id": {
                    "type": "integer",
                    "description": "The numbered element ID from the ARIA catalog (e.g. 1, 2, 3).",
                },
                "text": {
                    "type": "string",
                    "description": "Text to fill into the input field (for 'type') or key to press (for 'press').",
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional session identifier to track browser lifecycle (default: 'default').",
                },
            },
            "required": ["action", "element_id"],
        },
    },
    {
        "name": "take_the_wheel_request",
        "description": "Explicit tool call when the model identifies an unresolvable human challenge (CAPTCHA, Cloudflare, 2FA/MFA) requiring manual human intervention.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Detailed explanation of the challenge or verification prompt requiring human takeover.",
                },
                "session_id": {
                    "type": "string",
                    "description": "The active session ID where takeover is required.",
                },
            },
            "required": ["reason"],
        },
    },
]

# Alias for compatibility with external references
OPENBOT_TOOLS = COMPUTER_TOOLS

END_COMPUTER_SESSION_TOOL: dict[str, Any] = {
    "name": "end_computer_session",
    "description": "Explicitly end the computer execution session and tear down active sandbox and browser resources.",
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Optional session identifier to terminate (default: 'default').",
            },
            "bot_id": {
                "type": "string",
                "description": "Optional bot identifier (default: 'ultron_openbot').",
            },
        },
        "required": [],
    },
}

# Extended tool collection including session lifecycle management
EXTENDED_COMPUTER_TOOLS: list[dict[str, Any]] = COMPUTER_TOOLS + [END_COMPUTER_SESSION_TOOL]


# ── Strict Pydantic v2 Ingress Contracts ─────────────────────────────────────

class StrictToolModel(BaseModel):
    """Base model enforcing strict typing and forbidding extraneous keys."""
    model_config = ConfigDict(extra="forbid", strict=True)


class ComputerShellInput(StrictToolModel):
    command: str
    timeout: int = 60
    session_id: str = "default"


class BrowserNavigateInput(StrictToolModel):
    url: str
    session_id: str = "default"


class BrowserActInput(StrictToolModel):
    action: Literal["click", "type", "press"]
    element_id: int
    text: str | None = ""
    session_id: str = "default"


class TakeTheWheelRequestInput(StrictToolModel):
    reason: str
    session_id: str = "default"


class EndComputerSessionInput(StrictToolModel):
    session_id: str = "default"
    bot_id: str = "ultron_openbot"


# ── Default OpenBot Security Policy Rules ────────────────────────────────────

DEFAULT_OPENBOT_RULES: list[PolicyRule] = [
    PolicyRule(
        name="allow-sandbox-shell",
        action_type=ActionType.SHELL_EXEC,
        pattern=r".*",
        effect="ALLOW",
    ),
    PolicyRule(
        name="allow-web-navigation",
        action_type=ActionType.BROWSER_NAVIGATE,
        pattern=r"^https?://.*",
        effect="ALLOW",
    ),
    PolicyRule(
        name="allow-browser-click",
        action_type=ActionType.BROWSER_CLICK,
        pattern=r".*",
        effect="ALLOW",
    ),
    PolicyRule(
        name="allow-browser-type",
        action_type=ActionType.BROWSER_TYPE,
        pattern=r".*",
        effect="ALLOW",
    ),
    PolicyRule(
        name="allow-fs-read",
        action_type=ActionType.FS_READ,
        pattern=r".*",
        effect="ALLOW",
    ),
    PolicyRule(
        name="allow-fs-write",
        action_type=ActionType.FS_WRITE,
        pattern=r".*",
        effect="ALLOW",
    ),
]


# ── Dedicated Background Loop for Sync Playwright Management ─────────────────

class _SyncLoopManager:
    """
    Maintains a dedicated background worker thread with a live asyncio event loop
    to run async Playwright operations synchronously without event loop conflicts.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _ensure_running(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or self._loop.is_closed():
                ready_event = threading.Event()

                def _run_worker(ready: threading.Event) -> None:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self._loop = loop
                    ready.set()
                    loop.run_forever()

                self._thread = threading.Thread(
                    target=_run_worker,
                    args=(ready_event,),
                    name="OpenBot-SyncLoop",
                    daemon=True,
                )
                self._thread.start()
                ready_event.wait(timeout=5.0)

            return self._loop  # type: ignore[return-value]

    def run_coroutine(self, coro: Any) -> Any:
        loop = self._ensure_running()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def stop(self) -> None:
        with self._lock:
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.stop)
                if self._thread is not None and self._thread.is_alive():
                    self._thread.join(timeout=2.0)
                self._loop = None
                self._thread = None


# ── ComputerToolDispatcher ───────────────────────────────────────────────────

class ComputerToolDispatcher:
    """
    Chains the OpenBot computer execution pipeline in strict order:
      1. ComputerAction construction / validation
      2. HandoffManager.is_takeover_active(session_id) check
         -> Rejects immediately with 'TAKEOVER_IN_PROGRESS' if True (bypassing PolicyEvaluator)
      3. PolicyEvaluator.evaluate()
         -> If refused: logs intent (PENDING) and result (REFUSED), returns safe refusal message
      4. AuditLogger.log_intent()
         -> Records PENDING state before initiating execution
      5. Sandbox / Browser Execution
         -> Dispatches to isolated sandbox or token-compacting browser controller
      6. AuditLogger.log_result()
         -> Records COMPLETED or FAILED state with forensic output summary
    """

    def __init__(
        self,
        policy_evaluator: PolicyEvaluator | None = None,
        audit_logger: AuditLogger | None = None,
        handoff_manager: HandoffManager | None = None,
        browser_controller: BrowserController | None = None,
        sandbox_base_dir: str | None = None,
        session_registry: SessionRegistry | None = None,
        session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ) -> None:
        self.handoff_manager = handoff_manager or HandoffManager()
        self.audit_logger = audit_logger or AuditLogger(log_path=DEFAULT_AUDIT_LOG_PATH)
        self.policy_evaluator = policy_evaluator or PolicyEvaluator(rules=DEFAULT_OPENBOT_RULES)
        self.sandbox_base_dir = sandbox_base_dir
        self._custom_browser_controller = browser_controller
        self._sync_loop_manager = _SyncLoopManager()
        self.session_registry = session_registry or SessionRegistry(
            session_ttl_seconds=session_ttl_seconds,
            sandbox_base_dir=sandbox_base_dir,
            sync_loop_manager=self._sync_loop_manager,
        )

    @property
    def _sandboxes(self) -> dict[str, BaseSandbox]:
        """Backward-compatible mapping of active sandboxes keyed by bot_id:session_id."""
        with self.session_registry._lock:
            return {
                key: entry.sandbox
                for key, entry in self.session_registry._registry.items()
                if entry.sandbox is not None
            }

    @property
    def _browser_controllers(self) -> dict[str, BrowserController]:
        """Backward-compatible mapping of active browser controllers keyed by bot_id:session_id."""
        with self.session_registry._lock:
            controllers = {
                key: entry.browser_controller
                for key, entry in self.session_registry._registry.items()
                if entry.browser_controller is not None
            }
        if self._custom_browser_controller is not None:
            controllers["custom"] = self._custom_browser_controller
        return controllers

    def get_sandbox(
        self,
        bot_id: str = "ultron_openbot",
        session_id: str = "default",
        **kwargs: Any,
    ) -> BaseSandbox:
        """Retrieve or instantiate an isolated workspace sandbox scoped per (bot_id, session_id)."""
        eff_bot_id = kwargs.get("bot_id", bot_id)
        eff_session_id = kwargs.get("session_id", session_id)
        return self.session_registry.get_or_create_sandbox(
            bot_id=eff_bot_id,
            session_id=eff_session_id,
        )

    def get_browser_controller(
        self,
        bot_id: str = "ultron_openbot",
        session_id: str = "default",
        **kwargs: Any,
    ) -> BrowserController:
        """Retrieve or instantiate an ARIA token-compacting browser controller scoped per (bot_id, session_id)."""
        if self._custom_browser_controller is not None:
            return self._custom_browser_controller
        eff_bot_id = kwargs.get("bot_id", bot_id)
        eff_session_id = kwargs.get("session_id", session_id)
        return self.session_registry.get_or_create_browser_controller(
            bot_id=eff_bot_id,
            session_id=eff_session_id,
        )

    def build_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
        bot_id: str | None = None,
    ) -> ComputerAction:
        """
        Translate tool call name and arguments into a strictly typed ComputerAction contract.
        """
        effective_session = str(arguments.get("session_id") or session_id or "default")
        effective_bot = str(arguments.get("bot_id") or bot_id or "ultron_openbot")

        if tool_name == "computer_shell":
            cmd = str(arguments.get("command", ""))
            timeout = int(arguments.get("timeout", 60))
            return ComputerAction(
                action_type=ActionType.SHELL_EXEC,
                target=cmd,
                payload={"command": cmd, "timeout": timeout},
                bot_id=effective_bot,
                session_id=effective_session,
            )

        elif tool_name == "browser_navigate":
            url = str(arguments.get("url", ""))
            return ComputerAction(
                action_type=ActionType.BROWSER_NAVIGATE,
                target=url,
                payload={"url": url},
                bot_id=effective_bot,
                session_id=effective_session,
            )

        elif tool_name == "browser_act":
            act = str(arguments.get("action", "click")).lower()
            element_id = int(arguments.get("element_id", 0))
            text = str(arguments.get("text", "") or "")
            action_type = ActionType.BROWSER_TYPE if act == "type" else ActionType.BROWSER_CLICK
            return ComputerAction(
                action_type=action_type,
                target=str(element_id),
                payload={
                    "action": act,
                    "element_id": element_id,
                    "text": text,
                },
                bot_id=effective_bot,
                session_id=effective_session,
            )

        elif tool_name == "take_the_wheel_request":
            reason = str(arguments.get("reason", "Operator takeover requested."))
            return ComputerAction(
                action_type=ActionType.SHELL_EXEC,
                target="take_the_wheel",
                payload={"reason": reason, "is_takeover_request": True},
                bot_id=effective_bot,
                session_id=effective_session,
            )

        elif tool_name == "end_computer_session":
            return ComputerAction(
                action_type=ActionType.SHELL_EXEC,
                target="end_computer_session",
                payload={"is_end_session": True},
                bot_id=effective_bot,
                session_id=effective_session,
            )

        elif tool_name in ("fs_read", "fs_write"):
            action_type = ActionType.FS_READ if tool_name == "fs_read" else ActionType.FS_WRITE
            path = str(arguments.get("path", ""))
            return ComputerAction(
                action_type=action_type,
                target=path,
                payload=arguments,
                bot_id=effective_bot,
                session_id=effective_session,
            )

        else:
            return ComputerAction(
                action_type=ActionType.SHELL_EXEC,
                target=tool_name,
                payload=arguments,
                bot_id=effective_bot,
                session_id=effective_session,
            )

    async def dispatch_action_async(self, action: ComputerAction) -> str:
        """
        Execute an action asynchronously through the full OpenBot security & execution pipeline.

        Returns:
            str: JSON string representing outcome for Ultron's execution engine.
        """
        start_time = time.perf_counter()

        # Touch the session registry to record ongoing activity
        self.session_registry.touch(action.bot_id, action.session_id)

        # ── Pipeline Step 1: HandoffManager Takeover Check ────────────────────
        # Reject immediately with "TAKEOVER_IN_PROGRESS" if manual intervention is active
        # This occurs BEFORE reaching PolicyEvaluator to prevent any automated actions
        if self.handoff_manager.is_takeover_active(action.session_id):
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return json.dumps({
                "status": "TAKEOVER_IN_PROGRESS",
                "permitted": False,
                "error": (
                    f"Execution halted: manual takeover is active for session '{action.session_id}'. "
                    "Automated actions are paused until wheel release."
                ),
                "session_id": action.session_id,
                "target": action.target,
                "duration_ms": duration_ms,
            })

        # ── Pipeline Step 2: PolicyEvaluator ──────────────────────────────────
        permitted, reason = self.policy_evaluator.evaluate(action)
        if not permitted:
            # Audit log intent as PENDING then REFUSED
            record_id = self.audit_logger.log_intent(action)
            self.audit_logger.log_result(
                record_id=record_id,
                status="REFUSED",
                error=reason,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return json.dumps({
                "status": "REFUSED",
                "permitted": False,
                "error": reason,
                "record_id": record_id,
                "target": action.target,
                "action_type": action.action_type.value,
                "duration_ms": duration_ms,
            })

        # ── Pipeline Step 3: AuditLogger Intent Recording ─────────────────────
        record_id = self.audit_logger.log_intent(action)

        # ── Pipeline Step 4: Sandbox / Browser Execution ──────────────────────
        try:
            result_data = await self._execute_action_async(action)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # ── Pipeline Step 5: AuditLogger Result Recording ─────────────────
            summary = self._summarize_result(result_data)
            self.audit_logger.log_result(
                record_id=record_id,
                status="COMPLETED",
                result_summary=summary,
            )
            return json.dumps({
                "status": "COMPLETED",
                "permitted": True,
                "record_id": record_id,
                "target": action.target,
                "action_type": action.action_type.value,
                "result": result_data,
                "duration_ms": duration_ms,
            })

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            error_msg = str(exc)
            logger.exception("Action execution failed: %s", error_msg)
            self.audit_logger.log_result(
                record_id=record_id,
                status="FAILED",
                error=error_msg,
            )
            return json.dumps({
                "status": "FAILED",
                "permitted": True,
                "record_id": record_id,
                "target": action.target,
                "action_type": action.action_type.value,
                "error": error_msg,
                "duration_ms": duration_ms,
            })

    async def _execute_action_async(self, action: ComputerAction) -> dict[str, Any]:
        """Execute the validated action on the designated driver."""
        # 1. Explicit Take-the-Wheel tool request
        if action.target == "take_the_wheel" or action.payload.get("is_takeover_request"):
            reason = str(action.payload.get("reason", "Operator takeover requested."))
            bc = self.get_browser_controller(action.bot_id, action.session_id)
            if bc._browser is not None:
                try:
                    snapshot = await bc.get_current_snapshot()
                except Exception:
                    snapshot = None
            else:
                snapshot = None

            if snapshot is None:
                snapshot = BrowserSnapshot(
                    url="about:blank",
                    title="Manual Takeover Requested",
                    aria_tree="",
                    interactive_elements=[],
                )
            handoff_event = self.handoff_manager.trigger_takeover(
                session_id=action.session_id,
                snapshot=snapshot,
                reason=reason,
            )
            return {
                "action": "take_the_wheel",
                "status": "TAKEOVER_IN_PROGRESS",
                "session_id": action.session_id,
                "reason": reason,
                "handoff_event": handoff_event,
            }

        # 2. Explicit End Computer Session request
        if action.target == "end_computer_session" or action.payload.get("is_end_session"):
            await self.session_registry.end_session_async(action.bot_id, action.session_id)
            return {
                "action": "end_computer_session",
                "status": "COMPLETED",
                "session_id": action.session_id,
                "bot_id": action.bot_id,
                "message": f"Session '{action.bot_id}:{action.session_id}' terminated and resources released.",
            }

        # 3. Shell Execution in Sandbox
        if action.action_type == ActionType.SHELL_EXEC:
            sandbox = self.get_sandbox(action.bot_id, action.session_id)
            cmd = str(action.payload.get("command") or action.target)
            timeout = int(action.payload.get("timeout", 60))
            return sandbox.execute_command(cmd, timeout=timeout)

        # 3. Browser Navigation
        elif action.action_type == ActionType.BROWSER_NAVIGATE:
            bc = self.get_browser_controller(action.bot_id, action.session_id)
            url = str(action.payload.get("url") or action.target)
            snapshot = await bc.navigate(url)

            # Check if navigation landed on a verification challenge
            needs_takeover, detected_reason = self.handoff_manager.detect_takeover_need(snapshot)
            if needs_takeover:
                event = self.handoff_manager.trigger_takeover(
                    session_id=action.session_id,
                    snapshot=snapshot,
                    reason=detected_reason,
                )
                return {
                    "url": snapshot.url,
                    "title": snapshot.title,
                    "aria_tree": snapshot.aria_tree,
                    "interactive_elements": snapshot.interactive_elements,
                    "takeover_triggered": True,
                    "takeover_reason": detected_reason,
                    "handoff_event": event,
                }

            return {
                "url": snapshot.url,
                "title": snapshot.title,
                "aria_tree": snapshot.aria_tree,
                "interactive_elements": snapshot.interactive_elements,
                "takeover_triggered": False,
            }

        # 4. Browser Interactions (Click, Type, Press)
        elif action.action_type in (ActionType.BROWSER_CLICK, ActionType.BROWSER_TYPE):
            bc = self.get_browser_controller(action.bot_id, action.session_id)
            act = str(action.payload.get("action", "click")).lower()
            element_id = int(action.payload.get("element_id") or action.target)

            if act == "type":
                text = str(action.payload.get("text", "") or "")
                snapshot = await bc.type_text(element_id, text)
            elif act == "press":
                text = str(action.payload.get("text", "Enter") or "Enter")
                locator = bc._element_registry.get(element_id)
                if locator is not None:
                    await locator.press(text)
                elif bc._page is not None:
                    await bc._page.keyboard.press(text)
                snapshot = await bc.get_current_snapshot()
            else:
                snapshot = await bc.click_element(element_id)

            needs_takeover, detected_reason = self.handoff_manager.detect_takeover_need(snapshot)
            if needs_takeover:
                event = self.handoff_manager.trigger_takeover(
                    session_id=action.session_id,
                    snapshot=snapshot,
                    reason=detected_reason,
                )
                return {
                    "url": snapshot.url,
                    "title": snapshot.title,
                    "aria_tree": snapshot.aria_tree,
                    "interactive_elements": snapshot.interactive_elements,
                    "takeover_triggered": True,
                    "takeover_reason": detected_reason,
                    "handoff_event": event,
                }

            return {
                "url": snapshot.url,
                "title": snapshot.title,
                "aria_tree": snapshot.aria_tree,
                "interactive_elements": snapshot.interactive_elements,
                "takeover_triggered": False,
            }

        # 5. File System Operations
        elif action.action_type == ActionType.FS_READ:
            sandbox = self.get_sandbox(action.bot_id, action.session_id)
            content = sandbox.read_workspace_file(action.target)
            return {"path": action.target, "content": content}

        elif action.action_type == ActionType.FS_WRITE:
            sandbox = self.get_sandbox(action.bot_id, action.session_id)
            content = action.payload.get("content", "")
            success = sandbox.write_workspace_file(action.target, content)
            return {"path": action.target, "success": success}

        else:
            raise ValueError(f"Unsupported action type: {action.action_type}")

    def _summarize_result(self, result: dict[str, Any]) -> str:
        """Create a compact summary string for the audit log."""
        if "exit_code" in result:
            return f"Exit Code: {result['exit_code']}, Stdout: {len(result.get('stdout', ''))} bytes"
        if "aria_tree" in result:
            return f"URL: {result.get('url')}, Title: '{result.get('title')}', Elements: {len(result.get('interactive_elements', []))}"
        if "action" in result and result["action"] == "take_the_wheel":
            return f"Takeover Engaged: {result.get('reason')}"
        if "action" in result and result["action"] == "end_computer_session":
            return f"Session Terminated: {result.get('bot_id')}:{result.get('session_id')}"
        if "success" in result:
            return f"Success: {result['success']}"
        return f"Completed with keys: {list(result.keys())}"

    def dispatch_action(self, action: ComputerAction) -> str:
        """Synchronous wrapper for dispatch_action_async."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If called from within an active event loop without await
            return self._sync_loop_manager.run_coroutine(self.dispatch_action_async(action))
        else:
            return asyncio.run(self.dispatch_action_async(action))

    def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
        bot_id: str = "ultron_openbot",
    ) -> str:
        """
        Synchronous tool dispatch entrypoint. Translates tool invocation to ComputerAction
        and returns clean JSON string.
        """
        action = self.build_action(
            tool_name=tool_name,
            arguments=arguments,
            session_id=session_id,
            bot_id=bot_id,
        )
        return self.dispatch_action(action)

    async def dispatch_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
        bot_id: str = "ultron_openbot",
    ) -> str:
        """
        Asynchronous tool dispatch entrypoint.
        """
        action = self.build_action(
            tool_name=tool_name,
            arguments=arguments,
            session_id=session_id,
            bot_id=bot_id,
        )
        return await self.dispatch_action_async(action)

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """
        Compatibility adapter conforming to Ultron's standard ToolExecutor interface:
            execute(tool_name, tool_input) -> {"success": bool, "output": str, "error": str | None, "duration_ms": int}
        """
        raw_json = self.dispatch(tool_name, tool_input)
        try:
            parsed = json.loads(raw_json)
            status = parsed.get("status")
            return {
                "success": status == "COMPLETED",
                "output": raw_json,
                "error": parsed.get("error"),
                "duration_ms": parsed.get("duration_ms", 0),
            }
        except Exception:
            return {
                "success": False,
                "output": raw_json,
                "error": "Failed to parse dispatch output JSON.",
                "duration_ms": 0,
            }

    def end_session(self, bot_id: str = "ultron_openbot", session_id: str = "default") -> None:
        """Explicitly end a computer session and release all associated resources."""
        self.session_registry.end_session(bot_id=bot_id, session_id=session_id)

    async def end_session_async(self, bot_id: str = "ultron_openbot", session_id: str = "default") -> None:
        """Explicitly end a computer session and release all associated resources asynchronously."""
        await self.session_registry.end_session_async(bot_id=bot_id, session_id=session_id)

    def sweep_expired_sessions(self) -> list[str]:
        """Evict all idle sessions that have exceeded TTL."""
        return self.session_registry.sweep_expired()

    async def sweep_expired_sessions_async(self) -> list[str]:
        """Evict all idle sessions that have exceeded TTL asynchronously."""
        return await self.session_registry.sweep_expired_async()

    async def cleanup_async(self) -> None:
        """Close all active browser instances and clean up sandboxes asynchronously."""
        if self._custom_browser_controller is not None:
            try:
                await self._custom_browser_controller.close()
            except Exception:
                pass
            self._custom_browser_controller = None

        await self.session_registry.clear_async()

    def cleanup(self) -> None:
        """Synchronously clean up all active browser instances and sandboxes."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            self._sync_loop_manager.run_coroutine(self.cleanup_async())
        else:
            asyncio.run(self.cleanup_async())

        self._sync_loop_manager.stop()
