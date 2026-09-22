"""
tool_definitions.py — Ultron Protocol: Autonomous Tool Execution Engine.

Defines the 4 core tools that Ultron can use to take over the system:
  1. execute_command  — Run PowerShell/CMD commands on the local machine
  2. file_operation   — Read, write, list, or delete files/directories
  3. run_python       — Write and execute Python scripts
  4. web_search       — Search the web using DuckDuckGo

Each tool has:
  - An Anthropic tool schema (JSON) for Claude's tool_use API
  - A Python execution handler that runs the operation locally
  - Safety validation via the Sandbox layer
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

from sandbox import Sandbox, SandboxConfig, SandboxViolation
from guardrails.ast_sandbox import ASTSecurityViolation
from guardrails.limits import ExecutionLimitExceeded, dispatch_with_timeout, DEFAULT_TOOL_TIMEOUT_SEC
from concurrency import atomic_write, atomic_write_json
from governance import default_process_tracker
from contracts import (
    ContractValidationError,
    TOOL_INPUT_CONTRACTS,
    TOOL_OUTPUT_CONTRACTS,
    validate_contract,
)


# ── Anthropic Tool Schemas ────────────────────────────────────────────────────

ULTRON_TOOLS: list[dict[str, Any]] = [
    {
        "name": "core_memory_update",
        "description": "Replace the entire content of a core memory block (boss_profile, active_task, session_scratchpad). Use for massive changes or resetting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "block_name": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["block_name", "content"]
        }
    },
    {
        "name": "core_memory_append",
        "description": "Append a new line to an existing core memory block. Use to add a quick note to session_scratchpad.",
        "input_schema": {
            "type": "object",
            "properties": {
                "block_name": {"type": "string"},
                "text": {"type": "string"}
            },
            "required": ["block_name", "text"]
        }
    },
    {
        "name": "core_memory_replace",
        "description": "Surgically replace a specific substring inside a core memory block. Use to update a small fact in boss_profile or active_task without overwriting everything.",
        "input_schema": {
            "type": "object",
            "properties": {
                "block_name": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"}
            },
            "required": ["block_name", "old_text", "new_text"]
        }
    },
    {
        "name": "store_file_memory",
        "description": "Store key findings (sheet names, columns, summary stats, named entities) from a file analysis into long-term memory for future retrieval. Use this immediately after successfully analyzing a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The exact name of the file being stored (e.g. 'Tuition Fee Reconciliation.xlsx')."
                },
                "findings": {
                    "type": "string",
                    "description": "The detailed schema, key entities, and statistics found in the file."
                }
            },
            "required": ["filename", "findings"]
        }
    },
    {
        "name": "search_file_memory",
        "description": "Search long-term memory for previously stored findings about a specific file. Use this BEFORE writing any new analysis script for a file to avoid starting from scratch. When you are asked to 'analyze again', use this tool FIRST.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The exact name of the file to search for."
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "execute_command",
        "description": (
            "Execute a shell command on the Boss's local Windows machine. "
            "Use this for directory listings, file operations, git commands, "
            "running scripts, installing packages with pip, and general system tasks. "
            "Commands run in PowerShell on Windows. "
            "IMPORTANT: Only allowed commands are permitted (python, pip, dir, git, mkdir, etc). "
            "Dangerous system commands are blocked by the safety sandbox."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute. Example: 'dir' or 'python script.py'",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Optional working directory for the command. Defaults to the project root.",
                    "default": ".",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "file_operation",
        "description": (
            "Perform file system operations: read, write, list, or delete files and directories. "
            "Use this to create new files, read existing file contents, list directory contents, "
            "or delete files. All paths must be within the allowed workspace boundaries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete"],
                    "description": "The file operation to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "The file or directory path. Example: 'reports/summary.txt' or 'data/file.csv'",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (only for 'write' operation).",
                },
            },
            "required": ["operation", "path"],
        },
    },
    {
        "name": "run_python",
        "description": (
            "Write and execute a Python script on the Boss's machine. "
            "Use this for data processing, calculations, file manipulation, "
            "creating Excel spreadsheets with pandas/openpyxl, web scraping, "
            "data analysis, automation scripts, and any computational task. "
            "The script will be saved to a temp file and executed with the system Python interpreter. "
            "All output (stdout + stderr) is captured and returned. "
            "You can import any installed packages (pandas, openpyxl, requests, etc)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The complete Python script code to execute.",
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what this script does (for the action log).",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web using DuckDuckGo and return relevant results. "
            "Use this to find real-time information, research topics, look up documentation, "
            "find contact information, get pricing data, or gather any web-based intelligence. "
            "Returns titles, URLs, and snippets of the top results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 10).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_web_page",
        "description": (
            "Fetch and extract clean readable text from any web page or URL, bypassing Cloudflare/WAF bot-protection "
            "using browser TLS fingerprint impersonation. Use this to read full articles, documentation, IRS publications, "
            "FASB accounting standards, regulatory guidance, or API documentation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full HTTP/HTTPS URL of the web page to fetch and parse.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "open_browser",
        "description": (
            "Open Google Chrome, Microsoft Edge, or the default browser on Boss's desktop to a specific URL and profile. "
            "Supports targeting specific Chrome profiles on Boss's machine: "
            "'primary' (hanzla.rehman@primarybooksntax.com / Profile 7), "
            "'reach' (reach.hanzla@gmail.com / Profile 1), "
            "'personal' or 'default' (hanzlahmalik123@gmail.com / Default), "
            "'arcora' (app.arcora@gmail.com / Profile 10), "
            "'loyal_agency' (Profile 3). "
            "Use this whenever Boss asks to open websites, Gmail, portals, web dashboards, or Chrome profiles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to open (e.g. 'https://mail.google.com' or 'https://primarybooksntax.com').",
                },
                "profile": {
                    "type": "string",
                    "description": "Chrome profile to use: 'primary', 'reach', 'default', 'arcora', 'loyal_agency', or profile directory name.",
                    "default": "primary",
                },
                "browser": {
                    "type": "string",
                    "enum": ["chrome", "edge", "default"],
                    "description": "Browser to launch (defaults to chrome).",
                    "default": "chrome",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "open_application",
        "description": (
            "Launch ANY desktop application or shortcut on Boss's Windows machine. "
            "Automatically resolves shortcuts on Boss's Desktop (e.g. 'QuickBooks', 'QuickBooks Online', 'Arcora', 'CapCut', 'Zoom', 'Far Cry', 'Stremio', 'Antigravity') "
            "and Start Menu/system applications (e.g. 'code', 'explorer', 'notepad', 'calc', 'chrome', 'msedge')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "The name of the desktop application or shortcut to launch (e.g. 'QuickBooks', 'Arcora', 'CapCut', 'Zoom', 'code', 'explorer').",
                },
                "arguments": {
                    "type": "string",
                    "description": "Optional command line arguments or file/folder path (e.g. folder path to open in Explorer).",
                    "default": "",
                },
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "desktop_create_and_show_note",
        "description": (
            "Atomic Compound Tool: Writes text/notes to a file and pops it up in Notepad in the active foreground in a single deterministic operation. "
            "Use this whenever Boss asks to write a note, draft text on Notepad/screen, create a text file and show it, or display a greeting/message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The exact text or note content to write and display.",
                },
                "filename": {
                    "type": "string",
                    "description": "Optional filename or path (e.g. 'linkedin_intro.txt', 'greeting.txt', 'notes.txt'). Defaults to 'ultron_note.txt' in workspace.",
                    "default": "ultron_note.txt",
                },
                "open_in_foreground": {
                    "type": "boolean",
                    "description": "Whether to launch Notepad with the file and bring it to the foreground on Boss's screen. Default True.",
                    "default": True,
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "control_desktop_gui",
        "description": (
            "Control and interact with native Windows desktop applications and GUI elements. "
            "Use this to focus an application window, send keystrokes/hotkeys, close an application/window, "
            "click buttons/tabs by name or screen coordinates, and capture desktop screenshots for visual verification.\n\n"
            "MANDATORY DESKTOP AUTOMATION RULES:\n"
            "1. Post-Action Verification: After EVERY send_keys, click_element, or open_application call, you MUST perform a verification step. Take a screenshot (action='capture_screen'), describe what's visible, and confirm the expected result appeared. If verification fails, retry the specific step once. Do NOT proceed to the next step on an unverified state.\n"
            "2. Coordinate Brittleness: ALWAYS replace click_coordinates(x, y) with click_element(element_name) using the accessibility tree wherever the target element has a name. Coordinates are an absolute last resort.\n"
            "3. State Tracking: You MUST include the 'step_state' dictionary argument in every call to track progress. If verification shows the wrong state, explicitly report failure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["focus_window", "send_keys", "close_window", "click_element", "click_coordinates", "capture_screen", "list_open_windows"],
                    "description": "The GUI automation action to perform.",
                },
                "window_title": {
                    "type": "string",
                    "description": "Target application or window title to focus or interact with (e.g. 'QuickBooks', 'Excel', 'Chrome', 'Notepad').",
                    "default": "",
                },
                "keys": {
                    "type": "string",
                    "description": "Text or keystrokes to send (e.g. '^f' for Ctrl+F, '{ENTER}', '{TAB}', 'Hope for Haven').",
                    "default": "",
                },
                "element_name": {
                    "type": "string",
                    "description": "Visible text or label of the button/tab/menu to find and click (e.g. 'Bank transactions', 'Submit', 'File').",
                    "default": "",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate on screen for direct clicks.",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate on screen for direct clicks.",
                },
                "step_state": {
                    "type": "object",
                    "description": "Mandatory state tracking dictionary for multi-step flows.",
                    "properties": {
                        "current_step": {"type": "integer", "description": "Which step we are currently executing (e.g. 1, 2, 3)"},
                        "last_verified_state": {"type": "string", "description": "What was the last state successfully verified via screenshot"},
                        "expected_next_state": {"type": "string", "description": "What state we expect to see after this action executes"},
                    },
                    "required": ["current_step", "last_verified_state", "expected_next_state"],
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "search_emails",
        "description": (
            "Search Boss's email inbox using IMAP. "
            "Filter by sender (e.g. 'sarah'), subject (e.g. 'confirmation of invoices'), "
            "keywords, or unread status across profiles ('primary', 'reach', 'personal'). "
            "Returns matching message IDs, senders, subjects, dates, and snippets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword to search across email text or bodies (e.g. 'invoice', 'contract').",
                    "default": "",
                },
                "sender": {
                    "type": "string",
                    "description": "Filter by sender email or name (e.g. 'sarah' or 'client@domain.com').",
                    "default": "",
                },
                "subject": {
                    "type": "string",
                    "description": "Filter by subject keyword (e.g. 'confirmation of invoices').",
                    "default": "",
                },
                "unread_only": {
                    "type": "boolean",
                    "description": "Whether to only return unread emails.",
                    "default": False,
                },
                "profile": {
                    "type": "string",
                    "description": "Email profile: 'primary', 'reach', 'personal'. Defaults to 'primary'.",
                    "default": "primary",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of messages to return (default 10).",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "read_email_thread",
        "description": (
            "Read the full decoded content of an email message or thread by its message ID. "
            "Returns the sender, recipient, subject, date, full plain text body, HTML snippet, and attachment list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The message ID returned from search_emails.",
                },
                "profile": {
                    "type": "string",
                    "description": "Email profile: 'primary', 'reach', 'personal'. Defaults to 'primary'.",
                    "default": "primary",
                },
                "folder": {
                    "type": "string",
                    "description": "Mailbox folder (defaults to 'INBOX').",
                    "default": "INBOX",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "draft_email",
        "description": (
            "Create and save a formatted email draft locally as .eml and JSON. "
            "Allows Boss to review the message before sending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "body": {
                    "type": "string",
                    "description": "Email body text.",
                },
                "cc": {
                    "type": "string",
                    "description": "Optional CC recipient(s).",
                    "default": "",
                },
                "profile": {
                    "type": "string",
                    "description": "Sender profile: 'primary', 'reach', 'personal'. Defaults to 'primary'.",
                    "default": "primary",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "send_email",
        "description": (
            "Send an outbound email directly via SMTP SSL on behalf of Boss. "
            "Supports attachments, CC/BCC, and HTML/plain text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address (or comma-separated addresses).",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "body": {
                    "type": "string",
                    "description": "Email body text.",
                },
                "cc": {
                    "type": "string",
                    "description": "Optional CC recipient(s).",
                    "default": "",
                },
                "bcc": {
                    "type": "string",
                    "description": "Optional BCC recipient(s).",
                    "default": "",
                },
                "profile": {
                    "type": "string",
                    "description": "Sender profile: 'primary', 'reach', 'personal'. Defaults to 'primary'.",
                    "default": "primary",
                },
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of file paths to attach.",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "sleep_seconds",
        "description": "Pause execution for a specific number of seconds. Use this to wait for long-running Apify tasks, web pages to load, or background processes to finish before polling again.",
        "input_schema": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "description": "Number of seconds to sleep (e.g. 5, 10, 30)."
                }
            },
            "required": ["seconds"]
        }
    }
]



# ── Tool Execution Handlers ───────────────────────────────────────────────────

class ToolExecutor:
    """Executes tool calls with safety validation and output capture."""

    def __init__(self, sandbox: Sandbox | None = None, email_engine: Any = None) -> None:
        self.sandbox = sandbox or Sandbox()
        self._project_root = os.path.abspath("./")
        if email_engine is None:
            try:
                from email_engine import EmailEngine
                email_engine = EmailEngine()
            except Exception:
                email_engine = None
        self._email_engine = email_engine

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool call and return structured results.

        Returns:
            {
                "success": bool,
                "output": str,         # stdout or result text
                "error": str | None,   # error message if failed
                "duration_ms": int,    # execution time in milliseconds
            }
        """
        # ── Ingress Contract Validation (Fail-Fast) ───────────────────────────
        if tool_name in TOOL_INPUT_CONTRACTS:
            validated = validate_contract(TOOL_INPUT_CONTRACTS[tool_name], tool_input)
            tool_input = validated.model_dump()

        import collections
        import json
        import hashlib
        import time

        if not hasattr(self, "_cache"):
            self._cache = collections.OrderedDict()
            self._cache_ttl = 900
            self._cache_max_size = 200

        is_cacheable = False
        cacheable_tools = {"web_search", "brave_web_search", "fetch_web_page"}
        if tool_name in cacheable_tools:
            is_cacheable = True
        elif tool_name == "file_operation" and tool_input.get("operation", "").lower() == "read":
            is_cacheable = True

        cache_key = None
        if is_cacheable:
            input_str = json.dumps(tool_input, sort_keys=True)
            cache_key = f"{tool_name}:{hashlib.md5(input_str.encode('utf-8')).hexdigest()}"

            if cache_key in self._cache:
                entry = self._cache[cache_key]
                if time.time() - entry["timestamp"] < self._cache_ttl:
                    print(f"  [CACHE HIT] {tool_name} returned instantly.")
                    self._cache.move_to_end(cache_key)
                    res = entry["result"].copy()
                    res["duration_ms"] = 0
                    return res
                else:
                    del self._cache[cache_key]

        start = time.time()
        try:
            handler = getattr(self, f"_handle_{tool_name}", None)
            if handler is None:
                return {
                    "success": False,
                    "output": "",
                    "error": f"Unknown tool: {tool_name}",
                    "duration_ms": 0,
                }
            
            if is_cacheable:
                print(f"  [CACHE MISS] {tool_name} executing...")

            result = handler(tool_input)
            duration_ms = int((time.time() - start) * 1000)
            result["duration_ms"] = duration_ms

            if is_cacheable and result.get("success"):
                if len(self._cache) >= self._cache_max_size:
                    self._cache.popitem(last=False)
                self._cache[cache_key] = {
                    "timestamp": time.time(),
                    "result": result.copy()
                }

            if tool_name in TOOL_OUTPUT_CONTRACTS:
                validated_out = validate_contract(TOOL_OUTPUT_CONTRACTS[tool_name], result)
                result = validated_out.model_dump()

            return result

        except (SandboxViolation, ASTSecurityViolation) as e:
            duration_ms = int((time.time() - start) * 1000)
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return {
                "success": False,
                "output": "",
                "error": f"Execution error: {type(e).__name__}: {e}",
                "duration_ms": duration_ms,
            }

    async def execute_async(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        timeout_sec: float = DEFAULT_TOOL_TIMEOUT_SEC,
    ) -> dict[str, Any]:
        """
        Non-blocking async tool execution wrapped in timeout middleware (asyncio.wait_for).
        """
        import asyncio
        if timeout_sec == DEFAULT_TOOL_TIMEOUT_SEC:
            if tool_name == "run_python":
                timeout_sec = float(getattr(self.sandbox.config, "python_timeout", 120.0))
            elif tool_name == "execute_command":
                timeout_sec = float(getattr(self.sandbox.config, "command_timeout", 60.0))

        if tool_name in TOOL_INPUT_CONTRACTS:
            validated = validate_contract(TOOL_INPUT_CONTRACTS[tool_name], tool_input)
            tool_input = validated.model_dump()

        async def _run_tool():
            try:
                if tool_name == "sleep_seconds":
                    return await self._handle_sleep_seconds_async(tool_input)
                if tool_name == "execute_command":
                    return await self._handle_execute_command_async(tool_input, timeout_sec=timeout_sec)
                if tool_name == "run_python":
                    return await self._handle_run_python_async(tool_input, timeout_sec=timeout_sec)
                return await asyncio.to_thread(self.execute, tool_name, tool_input)
            except (SandboxViolation, ASTSecurityViolation) as e:
                return {
                    "success": False,
                    "output": "",
                    "error": str(e),
                    "duration_ms": 0,
                }
            except Exception as e:
                return {
                    "success": False,
                    "output": "",
                    "error": f"Tool execution error: {type(e).__name__}: {e}",
                    "duration_ms": 0,
                }

        res = await dispatch_with_timeout(_run_tool(), timeout_sec=timeout_sec, tool_name=tool_name)

        if tool_name in TOOL_OUTPUT_CONTRACTS:
            res = validate_contract(TOOL_OUTPUT_CONTRACTS[tool_name], res).model_dump()
        return res

    async def _handle_sleep_seconds_async(self, args: dict[str, Any]) -> dict[str, Any]:
        """True async sleep — zero LLM token burns, zero CPU spin during the wait."""
        import asyncio
        seconds = float(args.get("seconds", 0))
        print(f"  [ASYNC MESH] Suspending agent for {seconds}s — 0 token burn during wait...")
        await asyncio.sleep(seconds)
        return {
            "success": True,
            "output": f"Async suspension complete: {seconds}s elapsed. 0 LLM tokens consumed during wait.",
            "error": None,
            "duration_ms": int(seconds * 1000),
        }

    # ── Core Memory Tools ─────────────────────────────────────────────────────

    def _get_core_memory(self):
        try:
            from core_memory import CoreMemory
            return CoreMemory(user_id="boss")
        except ImportError:
            return None

    def _handle_core_memory_update(self, inp: dict[str, Any]) -> dict[str, Any]:
        cm = self._get_core_memory()
        if not cm:
            return {"success": False, "output": "", "error": "core_memory module not available"}
        block_name = inp.get("block_name", "")
        content = inp.get("content", "")
        if cm.update_block(block_name, content):
            return {"success": True, "output": f"Updated block '{block_name}' successfully.", "error": None}
        return {"success": False, "output": "", "error": f"Block '{block_name}' not found."}

    def _handle_core_memory_append(self, inp: dict[str, Any]) -> dict[str, Any]:
        cm = self._get_core_memory()
        if not cm:
            return {"success": False, "output": "", "error": "core_memory module not available"}
        block_name = inp.get("block_name", "")
        text = inp.get("text", "")
        if cm.append_to_block(block_name, text):
            return {"success": True, "output": f"Appended to block '{block_name}' successfully.", "error": None}
        return {"success": False, "output": "", "error": f"Block '{block_name}' not found."}

    def _handle_core_memory_replace(self, inp: dict[str, Any]) -> dict[str, Any]:
        cm = self._get_core_memory()
        if not cm:
            return {"success": False, "output": "", "error": "core_memory module not available"}
        block_name = inp.get("block_name", "")
        old_text = inp.get("old_text", "")
        new_text = inp.get("new_text", "")
        if cm.replace_in_block(block_name, old_text, new_text):
            return {"success": True, "output": f"Replaced text in block '{block_name}' successfully.", "error": None}
        return {"success": False, "output": "", "error": f"Block '{block_name}' not found or old_text not in block."}

    # ── File Memory Tools ─────────────────────────────────────────────────────

    def _handle_store_file_memory(self, inp: dict[str, Any]) -> dict[str, Any]:
        filename = inp.get("filename", "").strip()
        findings = inp.get("findings", "").strip()
        if not filename or not findings:
            return {"success": False, "output": "", "error": "filename and findings are required"}
        
        try:
            import os, json
            file_mem_path = os.path.join("data", "file_memory.json")
            os.makedirs("data", exist_ok=True)
            
            mem_data = {}
            if os.path.exists(file_mem_path):
                with open(file_mem_path, "r", encoding="utf-8") as f:
                    mem_data = json.load(f)
                    
            mem_data[filename] = findings
            atomic_write_json(file_mem_path, mem_data, indent=4)
            return {"success": True, "output": f"Successfully stored findings for {filename} into local file memory.", "error": None}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _handle_search_file_memory(self, inp: dict[str, Any]) -> dict[str, Any]:
        filename = inp.get("filename", "").strip()
        if not filename:
            return {"success": False, "output": "", "error": "filename is required"}
        
        try:
            import os, json
            file_mem_path = os.path.join("data", "file_memory.json")
            
            if not os.path.exists(file_mem_path):
                return {"success": True, "output": f"No previous findings found in memory for {filename}. You must scan it from scratch.", "error": None}
                
            with open(file_mem_path, "r", encoding="utf-8") as f:
                mem_data = json.load(f)
                
            if filename in mem_data:
                output_str = f"--- MEMORY RESULTS FOR {filename} ---\n{mem_data[filename]}\n"
                return {"success": True, "output": output_str, "error": None}
            
            # Fuzzy match
            for k, v in mem_data.items():
                if filename.lower() in k.lower():
                    output_str = f"--- MEMORY RESULTS FOR {k} ---\n{v}\n"
                    return {"success": True, "output": output_str, "error": None}

            return {"success": True, "output": f"No previous findings found in memory for {filename}. You must scan it from scratch.", "error": None}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
            
    # ── execute_command ───────────────────────────────────────────────────────

    def _handle_execute_command(self, inp: dict[str, Any]) -> dict[str, Any]:
        command = inp.get("command", "").strip()
        working_dir = inp.get("working_directory", self._project_root)

        # Validate command
        self.sandbox.validate_command(command)

        # Validate working directory
        if working_dir and working_dir != ".":
            working_dir = self.sandbox.validate_file_path(working_dir, "read")
        else:
            working_dir = self._project_root

        # Execute with process tree killing for Windows
        try:
            import platform
            import subprocess
            is_win = platform.system() == "Windows"
            
            p = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=working_dir,
            )
            default_process_tracker.register(p)
            
            try:
                stdout_data, stderr_data = p.communicate(timeout=self.sandbox.config.command_timeout)
            except subprocess.TimeoutExpired:
                default_process_tracker.terminate(p.pid, timeout_sec=2.0)
                # Flush pipes to prevent hanging
                stdout_data, stderr_data = p.communicate()
                return {
                    "success": False,
                    "output": (stdout_data or "") + (stderr_data or ""),
                    "error": f"Command timed out after {self.sandbox.config.command_timeout}s. Process tree forcefully terminated.",
                }
            finally:
                default_process_tracker.unregister(p.pid)

            output = ""
            if stdout_data:
                output += stdout_data
            if stderr_data:
                if output:
                    output += "\n--- STDERR ---\n"
                output += stderr_data

            output = self.sandbox.truncate_output(output or "(no output)")

            return {
                "success": p.returncode == 0,
                "output": output,
                "error": None if p.returncode == 0 else f"Exit code: {p.returncode}",
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Execution failed: {str(e)}",
            }

    # ── file_operation ────────────────────────────────────────────────────────

    def _handle_file_operation(self, inp: dict[str, Any]) -> dict[str, Any]:
        operation = inp.get("operation", "").strip().lower()
        path = inp.get("path", "").strip()
        content = inp.get("content", "")

        # Validate path
        normalized = self.sandbox.validate_file_path(path, operation)

        if operation == "read":
            return self._file_read(normalized)
        elif operation == "write":
            return self._file_write(normalized, content or "")
        elif operation == "list":
            return self._file_list(normalized)
        elif operation == "delete":
            return self._file_delete(normalized)
        else:
            return {"success": False, "output": "", "error": f"Unknown operation: {operation}"}

    def _file_read(self, path: str) -> dict[str, Any]:
        if not os.path.exists(path):
            return {"success": False, "output": "", "error": f"File not found: {path}"}
        if os.path.isdir(path):
            return {"success": False, "output": "", "error": f"Path is a directory, use 'list' operation: {path}"}

        try:
            lower = path.lower()
            if lower.endswith((".docx", ".pdf", ".xlsx", ".xls", ".pptx", ".csv")):
                from file_processor import FileProcessor
                with open(path, "rb") as f:
                    content_bytes = f.read()
                pf = FileProcessor.process_file(os.path.basename(path), content_bytes)
                return {"success": True, "output": self.sandbox.truncate_output(pf.text_content), "error": None}

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            content = self.sandbox.truncate_output(content)
            return {"success": True, "output": content, "error": None}
        except Exception as e:
            return {"success": False, "output": "", "error": f"Read error: {e}"}


    def _file_write(self, path: str, content: str) -> dict[str, Any]:
        try:
            atomic_write(path, content)
            size = os.path.getsize(path)
            return {
                "success": True,
                "output": f"✅ File written successfully: {path} ({size:,} bytes)",
                "error": None,
            }
        except Exception as e:
            return {"success": False, "output": "", "error": f"Write error: {e}"}

    def _file_list(self, path: str) -> dict[str, Any]:
        if not os.path.exists(path):
            return {"success": False, "output": "", "error": f"Path not found: {path}"}

        try:
            if os.path.isfile(path):
                size = os.path.getsize(path)
                return {
                    "success": True,
                    "output": f"FILE: {path} ({size:,} bytes)",
                    "error": None,
                }

            entries = []
            for entry in sorted(os.listdir(path)):
                full = os.path.join(path, entry)
                if os.path.isdir(full):
                    count = len(os.listdir(full)) if os.access(full, os.R_OK) else "?"
                    entries.append(f"📁 {entry}/ ({count} items)")
                else:
                    size = os.path.getsize(full)
                    entries.append(f"📄 {entry} ({size:,} bytes)")

            output = f"Directory: {path}\n{'─' * 50}\n" + "\n".join(entries)
            if not entries:
                output += "(empty directory)"
            output = self.sandbox.truncate_output(output)
            return {"success": True, "output": output, "error": None}
        except PermissionError:
            return {"success": False, "output": "", "error": f"Permission denied: {path}"}
        except Exception as e:
            return {"success": False, "output": "", "error": f"List error: {e}"}

    def _file_delete(self, path: str) -> dict[str, Any]:
        if not os.path.exists(path):
            return {"success": False, "output": "", "error": f"Path not found: {path}"}
        try:
            if os.path.isfile(path):
                os.remove(path)
                return {"success": True, "output": f"✅ Deleted file: {path}", "error": None}
            else:
                return {"success": False, "output": "", "error": "Use execute_command with 'rmdir' for directory deletion."}
        except Exception as e:
            return {"success": False, "output": "", "error": f"Delete error: {e}"}

    # ── run_python ────────────────────────────────────────────────────────────

    def _handle_run_python(self, inp: dict[str, Any]) -> dict[str, Any]:
        code = inp.get("code", "").strip()
        description = inp.get("description", "Python script")

        # Validate code
        self.sandbox.validate_python_code(code)

        # Write to temp file with UTF-8 setup and execute
        try:
            bootstrap = (
                "import sys\n"
                "try:\n"
                "    sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
                "    sys.stderr.reconfigure(encoding='utf-8', errors='replace')\n"
                "except Exception:\n"
                "    pass\n\n"
            )
            full_code = bootstrap + code

            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                prefix="ultron_script_",
                dir=tempfile.gettempdir(),
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(full_code)
                script_path = f.name

            try:
                import sys as _sys
                env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
                result = subprocess.run(
                    [_sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.sandbox.config.python_timeout,
                    cwd=self._project_root,
                    env=env,
                )



                output = ""
                if result.stdout:
                    output += result.stdout
                if result.stderr:
                    if output:
                        output += "\n--- STDERR ---\n"
                    output += result.stderr

                output = self.sandbox.truncate_output(output or "(no output)")

                return {
                    "success": result.returncode == 0,
                    "output": output,
                    "error": None if result.returncode == 0 else f"Script exited with code {result.returncode}",
                }
            finally:
                # Clean up temp script
                try:
                    os.unlink(script_path)
                except OSError:
                    pass

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"Python script timed out after {self.sandbox.config.python_timeout}s",
            }

    # ── web_search ────────────────────────────────────────────────────────────

    def _handle_web_search(self, inp: dict[str, Any]) -> dict[str, Any]:
        query = inp.get("query", "").strip()
        num_results = min(inp.get("num_results", 5), 10)

        if not query:
            return {"success": False, "output": "", "error": "Empty search query."}

        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append(r)

            if not results:
                return {"success": True, "output": f"No web search results found for: \"{query}\".", "error": None}

            output_parts = [f"🔍 Web Search: \"{query}\"\n{'═' * 50}"]
            for i, r in enumerate(results, 1):
                output_parts.append(
                    f"\n{i}. {r.get('title', 'No title')}\n"
                    f"   URL: {r.get('href', r.get('link', 'N/A'))}\n"
                    f"   {r.get('body', r.get('snippet', 'No snippet'))}"
                )

            output = "\n".join(output_parts)
            return {"success": True, "output": self.sandbox.truncate_output(output), "error": None}

        except ImportError:
            return {
                "success": False,
                "output": "",
                "error": "ddgs/duckduckgo-search package not installed. Run: pip install ddgs",
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Search error: {type(e).__name__}: {e}",
            }

    # ── fetch_web_page ────────────────────────────────────────────────────────

    def _handle_fetch_web_page(self, inp: dict[str, Any]) -> dict[str, Any]:
        url = inp.get("url", "").strip()
        if not url:
            return {"success": False, "output": "", "error": "Missing URL parameter."}

        try:
            html_text = ""
            status_code = 200
            # 1. High-fidelity browser TLS impersonation via curl_cffi to bypass Cloudflare/Akamai WAF
            try:
                from curl_cffi import requests as cffi_requests
                resp = cffi_requests.get(url, impersonate="chrome120", timeout=15)
                status_code = resp.status_code
                if resp.status_code == 200:
                    html_text = resp.text
            except Exception:
                # 2. Fallback to urllib with standard browser headers
                import urllib.request
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    html_text = r.read().decode("utf-8", errors="replace")
                    status_code = r.status

            if not html_text:
                return {"success": False, "output": "", "error": f"Failed to fetch content from {url} (HTTP {status_code})"}

            clean_text = self._html_to_clean_text(html_text)
            truncated = self.sandbox.truncate_output(clean_text)
            return {
                "success": True,
                "output": f"📄 URL: {url} (HTTP {status_code})\n{'─' * 50}\n{truncated}",
                "error": None,
            }
        except Exception as e:
            return {"success": False, "output": "", "error": f"Web fetch error for {url}: {e}"}

    def _html_to_clean_text(self, html: str) -> str:
        import html as html_module
        import re as _re
        cleaned = _re.sub(r"<(script|style|svg|noscript|iframe)[^>]*>[\s\S]*?</\1>", " ", html, flags=_re.IGNORECASE)
        cleaned = _re.sub(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', cleaned, flags=_re.IGNORECASE)
        cleaned = _re.sub(r'<(h[1-6]|p|div|li|tr)[^>]*>', '\n', cleaned, flags=_re.IGNORECASE)
        cleaned = _re.sub(r'<[^>]+>', ' ', cleaned)
        cleaned = html_module.unescape(cleaned)
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        return '\n'.join(lines)

    # ── open_browser ──────────────────────────────────────────────────────────

    def _handle_open_browser(self, inp: dict[str, Any]) -> dict[str, Any]:
        url = inp.get("url", "").strip()
        profile_req = inp.get("profile", "primary").strip().lower()
        browser = inp.get("browser", "chrome").strip().lower()

        if not url:
            return {"success": False, "output": "", "error": "No URL specified."}

        # Map friendly profile names to Chrome profile directories
        profile_map = {
            "primary": "Profile 7",
            "primarybooks": "Profile 7",
            "primarybooksntax": "Profile 7",
            "profile 7": "Profile 7",
            "7": "Profile 7",
            "reach": "Profile 1",
            "reach.hanzla": "Profile 1",
            "profile 1": "Profile 1",
            "1": "Profile 1",
            "arcora": "Profile 10",
            "project arcora": "Profile 10",
            "profile 10": "Profile 10",
            "10": "Profile 10",
            "loyal": "Profile 3",
            "loyal tax": "Profile 3",
            "profile 3": "Profile 3",
            "3": "Profile 3",
            "personal": "Default",
            "default": "Default",
            "hanzlahmalik": "Default",
        }

        resolved_profile = profile_map.get(profile_req, profile_req)

        try:
            if browser == "chrome":
                cmd = f'start chrome --profile-directory="{resolved_profile}" "{url}"'
                subprocess.Popen(cmd, shell=True)
                return {
                    "success": True,
                    "output": f"Launched Google Chrome with Profile '{resolved_profile}' to URL: {url}",
                    "error": None,
                }
            elif browser == "edge":
                cmd = f'start msedge "{url}"'
                subprocess.Popen(cmd, shell=True)
                return {
                    "success": True,
                    "output": f"Launched Microsoft Edge to URL: {url}",
                    "error": None,
                }
            else:
                import webbrowser
                webbrowser.open(url)
                return {
                    "success": True,
                    "output": f"Opened URL in default browser: {url}",
                    "error": None,
                }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Failed to launch browser: {e}",
            }

    # ── open_application ──────────────────────────────────────────────────────

    def _handle_open_application(self, inp: dict[str, Any]) -> dict[str, Any]:
        app_name = inp.get("app_name", "").strip()
        args = inp.get("arguments", "").strip()

        if not app_name:
            return {"success": False, "output": "", "error": "Application name is required."}

        target_path = self._resolve_desktop_app(app_name)
        try:
            if target_path and os.path.exists(target_path):
                # Launch shortcut or exe using Windows shell
                if args:
                    subprocess.Popen(f'start "" "{target_path}" {args}', shell=True)
                else:
                    os.startfile(target_path)
                return {
                    "success": True,
                    "output": f"Successfully launched '{app_name}' from: {target_path}\n[MANDATORY VERIFICATION] You must now use control_desktop_gui with action='capture_screen' to verify the expected result appeared before proceeding.",
                    "error": None,
                }

            # If not a desktop shortcut, check system commands & standard apps
            app_lower = app_name.lower()
            if app_lower == "explorer":
                path = args or self._cfg.workspace_root or "."
                cmd = f'explorer "{path}"'
            elif app_lower == "code":
                path = args or "."
                cmd = f'code "{path}"'
            elif app_lower == "notepad":
                path = args or ""
                cmd = f'notepad "{path}"' if path else "notepad"
            elif app_lower in ["calc", "calculator"]:
                cmd = "calc"
            elif app_lower in ["cmd", "powershell", "msedge", "chrome"]:
                cmd = f'start {app_lower} {args}'.strip()
            else:
                cmd = f'start "" "{app_name}" {args}'.strip()

            subprocess.Popen(cmd, shell=True)
            return {
                "success": True,
                "output": f"Initiated application '{app_name}' via Windows system command: {cmd}\n[MANDATORY VERIFICATION] You must now use control_desktop_gui with action='capture_screen' to verify the expected result appeared before proceeding.",
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Failed to launch application '{app_name}': {e}",
            }

    def _resolve_desktop_app(self, name: str) -> str | None:
        query = name.strip().lower()
        search_dirs = [
            os.path.expanduser("~/OneDrive/Desktop"),
            os.path.expanduser("~/Desktop"),
            r"C:\Users\Public\Desktop",
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs")
        ]

        # 1. Check direct match in desktop directories first
        for d in search_dirs[:3]:
            if not os.path.exists(d):
                continue
            for f in os.listdir(d):
                stem, ext = os.path.splitext(f)
                if ext.lower() in [".lnk", ".exe", ".url"]:
                    if query == stem.lower() or query in stem.lower() or stem.lower() in query:
                        return os.path.join(d, f)

        # 2. Check Start Menu and subdirectories (Fast because Start Menu is shallow)
        for d in search_dirs[3:5]:
            if not os.path.exists(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    stem, ext = os.path.splitext(f)
                    if ext.lower() in [".lnk", ".exe"]:
                        if query == stem.lower() or query in stem.lower() or stem.lower() in query:
                            return os.path.join(root, f)

        # 3. Check common absolute paths explicitly instead of walking all of Program Files
        common_exes = [
            rf"C:\Program Files\{query}\{query}.exe",
            rf"C:\Program Files (x86)\{query}\{query}.exe",
            os.path.expandvars(rf"%LOCALAPPDATA%\Programs\{query}\{query}.exe")
        ]
        for path in common_exes:
            if os.path.exists(path):
                return path

        return None

    # ── desktop_create_and_show_note (Atomic Compound Tool) ───────────────────

    def _handle_desktop_create_and_show_note(self, inp: dict[str, Any]) -> dict[str, Any]:
        content = inp.get("content", "")
        if not content:
            return {"success": False, "output": "", "error": "content parameter is required."}

        filename = inp.get("filename", "ultron_note.txt").strip()
        open_in_foreground = inp.get("open_in_foreground", True)

        # 1. Resolve safe target path
        if not os.path.isabs(filename):
            default_dir = self._cfg.workspace_root if os.path.exists(self._cfg.workspace_root) else self._project_root
            target_path = os.path.join(default_dir, filename)
        else:
            target_path = filename

        target_path = os.path.abspath(target_path)

        # 2. Write file atomically with UTF-8
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            size = os.path.getsize(target_path)
        except Exception as e:
            return {"success": False, "output": "", "error": f"Failed to write note to disk: {e}"}

        # 3. Launch Notepad with target file and bring to foreground
        launch_msg = "Note written to disk."
        if open_in_foreground:
            norm_path = target_path.replace("\\", "/")
            ps_script = f'''
            $filePath = "{norm_path}"
            # Launch Notepad directly loading the file
            $proc = Start-Process notepad.exe -ArgumentList "`"$filePath`"" -PassThru
            Start-Sleep -Milliseconds 600

            $wshell = New-Object -ComObject wscript.shell;
            $activated = $wshell.AppActivate($proc.Id);
            if (-not $activated) {{
                $fileName = [System.IO.Path]::GetFileName($filePath)
                $activated = $wshell.AppActivate($fileName)
            }}
            if (-not $activated) {{
                $activated = $wshell.AppActivate("Notepad")
            }}
            Write-Output "STATUS:OPENED"
            '''
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
            launch_msg = "Note written to disk and popped up in Notepad on your active screen."

        return {
            "success": True,
            "output": f"[SUCCESS] {launch_msg}\n- Path: {target_path}\n- Size: {size:,} bytes",
            "path": target_path,
            "bytes_written": size,
            "error": None,
        }

    # ── control_desktop_gui ───────────────────────────────────────────────────

    def _handle_control_desktop_gui(self, inp: dict[str, Any]) -> dict[str, Any]:
        window_title = inp.get("window_title", "").strip()
        verifier = None
        pre_state = {}
        try:
            from desktop_action_verifier import DesktopActionVerifier
            verifier = DesktopActionVerifier()
            if window_title:
                pre_state = verifier.capture_window_state(window_title)
        except Exception as e:
            pass
            
        result = self._handle_control_desktop_gui_raw(inp)
        
        if verifier and window_title and result.get("success"):
            import time
            time.sleep(verifier.SETTLE_DELAY)
            try:
                post_state = verifier.capture_window_state(window_title)
                state_changed = verifier._states_differ(pre_state, post_state)
                if state_changed:
                    result["output"] += "\n[UFO VERIFIER: UI state changed successfully.]"
                else:
                    result["output"] += "\n[UFO VERIFIER WARNING: UI state did NOT change. Action may have failed silently.]"
            except Exception:
                pass

        return result

    def _handle_control_desktop_gui_raw(self, inp: dict[str, Any]) -> dict[str, Any]:
        action = inp.get("action", "").strip().lower()
        window_title = inp.get("window_title", "").strip()
        keys = inp.get("keys", "").strip()
        element_name = inp.get("element_name", "").strip()
        x = inp.get("x")
        y = inp.get("y")
        step_state = inp.get("step_state", {})

        if not action:
            return {"success": False, "output": "", "error": "GUI action is required."}

        state_prefix = ""
        if step_state:
            curr = step_state.get('current_step', '?')
            last = step_state.get('last_verified_state', '?')
            nxt = step_state.get('expected_next_state', '?')
            state_prefix = f"[STATE TRACKING] Step: {curr} | Last: {last} | Expected Next: {nxt}\n"

        try:
            # 1. Action: Focus Window
            if action == "focus_window":
                if not window_title:
                    return {"success": False, "output": "", "error": "window_title is required for focus_window."}
                ps_script = f'''
                $wshell = New-Object -ComObject wscript.shell;
                $res = $wshell.AppActivate("{window_title}");
                if ($res) {{ Write-Output "FOCUSED: {window_title}" }} else {{ Write-Output "NOT_FOUND" }}
                '''
                res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
                out = res.stdout.strip()
                if "FOCUSED" in out:
                    return {"success": True, "output": f"Window matching '{window_title}' brought to foreground.", "error": None}
                return {"success": False, "output": "", "error": f"No active window found matching '{window_title}'."}

            # 2. Action: Send Keys / Hotkeys
            elif action == "send_keys":
                if not keys:
                    return {"success": False, "output": "", "error": "keys parameter is required for send_keys."}

                if not window_title:
                    return {
                        "success": False,
                        "output": "",
                        "error": "window_title is required for send_keys to prevent sending keystrokes to an unintended window.",
                    }

                # Step 1: Structural Focus & Step 2: Active Window Guard via Win32 / PowerShell
                safe_title_esc = window_title.replace('"', '`"').replace("'", "''")
                import tempfile
                tmp_text_file = os.path.join(tempfile.gettempdir(), f"ultron_sendkeys_{int(time.time()*1000)}.txt")
                with open(tmp_text_file, "w", encoding="utf-8") as f:
                    f.write(keys)
                norm_tmp = tmp_text_file.replace("\\", "/")

                safe_title_esc = window_title.replace('"', '`"').replace("'", "''")

                ps_script = f'''
                $txtPath = "{norm_tmp}"
                $content = if (Test-Path $txtPath) {{ Get-Content $txtPath -Raw -Encoding UTF8 }} else {{ "" }}
                
                $wshell = New-Object -ComObject wscript.shell;
                
                # Try multiple activation heuristics for Windows 10/11
                $activated = $wshell.AppActivate("{safe_title_esc}");
                if (-not $activated) {{
                    $activated = $wshell.AppActivate("Untitled - {safe_title_esc}");
                }}
                if (-not $activated) {{
                    $proc = Get-Process | Where-Object {{ $_.ProcessName -like "*{safe_title_esc}*" -or $_.MainWindowTitle -like "*{safe_title_esc}*" }} | Select-Object -First 1
                    if ($proc) {{
                        $activated = $wshell.AppActivate($proc.Id);
                    }}
                }}

                if (-not $activated) {{
                    Write-Output "STATUS:NOT_FOUND";
                }} else {{
                    Start-Sleep -Milliseconds 400;
                    Add-Type @"
                    using System;
                    using System.Runtime.InteropServices;
                    using System.Text;
                    public class ActiveWindowGuard {{
                        [DllImport("user32.dll")]
                        public static extern IntPtr GetForegroundWindow();
                        [DllImport("user32.dll")]
                        public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
                        public static string GetActiveTitle() {{
                            IntPtr hwnd = GetForegroundWindow();
                            if (hwnd == IntPtr.Zero) return "";
                            StringBuilder sb = new StringBuilder(512);
                            GetWindowText(hwnd, sb, 512);
                            return sb.ToString();
                        }}
                    }}
"@
                    # Force SetForegroundWindow via Win32 API to guarantee active focus before typing
                    Add-Type @"
                    using System;
                    using System.Runtime.InteropServices;
                    public class WindowActivator {{
                        [DllImport("user32.dll")]
                        public static extern bool SetForegroundWindow(IntPtr hWnd);
                        [DllImport("user32.dll")]
                        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    }}
"@
                    $hwnd = [IntPtr]::Zero;
                    $procs = Get-Process | Where-Object {{ $_.ProcessName -like "*{safe_title_esc}*" -or $_.MainWindowTitle -like "*{safe_title_esc}*" }}
                    foreach ($p in $procs) {{
                        if ($p.MainWindowHandle -ne [IntPtr]::Zero) {{
                            $hwnd = $p.MainWindowHandle;
                            break;
                        }}
                    }}
                    if ($hwnd -ne [IntPtr]::Zero) {{
                        [WindowActivator]::ShowWindow($hwnd, 9);
                        [WindowActivator]::SetForegroundWindow($hwnd);
                        Start-Sleep -Milliseconds 300;
                    }}

                    $actualTitle = [ActiveWindowGuard]::GetActiveTitle();
                    # Proceed if forced focus succeeded or title matches
                    if ($hwnd -ne [IntPtr]::Zero -or $actualTitle.Length -eq 0 -or $actualTitle.ToLower().Contains("{safe_title_esc.lower()}")) {{
                        # Type content line-by-line
                        $lines = $content -split "`r?`n"
                        foreach ($line in $lines) {{
                            if ($line.Length -gt 0) {{
                                $escaped = ""
                                for ($i = 0; $i -lt $line.Length; $i++) {{
                                    $char = $line[$i]
                                    if ($char -in '+', '^', '%', '~', '(', ')', '{{', '}}') {{
                                        $escaped += "{{" + $char + "}}"
                                    }} else {{
                                        $escaped += $char
                                    }}
                                }}
                                $wshell.SendKeys($escaped)
                            }}
                            $wshell.SendKeys("{{ENTER}}")
                            Start-Sleep -Milliseconds 30
                        }}
                        $reportTitle = if ($actualTitle.Length -gt 0) {{ $actualTitle }} else {{ "{safe_title_esc}" }}
                        Write-Output "STATUS:SUCCESS|TITLE:$reportTitle";
                    }} else {{
                        Write-Output "STATUS:MISMATCH|TITLE:$actualTitle";
                    }}
                }}
                '''
                res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
                out = res.stdout.strip()

                try:
                    if os.path.exists(tmp_text_file):
                        os.remove(tmp_text_file)
                except Exception:
                    pass

                if "STATUS:NOT_FOUND" in out:
                    return {
                        "success": False,
                        "output": "",
                        "error": f"Target window '{window_title}' not found — keystroke aborted for safety.",
                    }
                elif "STATUS:MISMATCH" in out:
                    actual = out.split("TITLE:")[-1].strip() if "TITLE:" in out else "Unknown"
                    return {
                        "success": False,
                        "output": "",
                        "error": f"Active window mismatch — keystroke aborted for safety. Expected window matching '{window_title}', but active window was '{actual}'.",
                    }
                elif "STATUS:SUCCESS" in out:
                    actual = out.split("TITLE:")[-1].strip() if "TITLE:" in out else window_title
                    return {
                        "success": True,
                        "output": state_prefix + f"Sent keystrokes to verified active window '{actual}'.\n[MANDATORY VERIFICATION] You must now run action='capture_screen' to verify the expected result appeared before proceeding.",
                        "error": None,
                    }
                else:
                    return {
                        "success": False,
                        "output": "",
                        "error": f"Active window verification failed: {out or res.stderr.strip() or 'Unknown error'}",
                    }

            # 3. Action: Close Window / Terminate Desktop Application
            elif action == "close_window":
                if not window_title:
                    return {"success": False, "output": "", "error": "window_title is required for close_window."}

                safe_title = window_title.replace('"', '`"').replace("'", "''")
                ps_script = f'''
                $closed = $false;
                # Strategy A: Graceful close via Process MainWindowHandle / CloseMainWindow
                $procs = Get-Process | Where-Object {{ $_.ProcessName -like "*{safe_title}*" -or $_.MainWindowTitle -like "*{safe_title}*" }}
                foreach ($p in $procs) {{
                    try {{
                        if ($p.MainWindowHandle -ne [IntPtr]::Zero) {{
                            $p.CloseMainWindow() | Out-Null
                            $closed = $true
                        }}
                    }} catch {{}}
                }}

                # Strategy B: If still running after 400ms, Stop-Process under user session
                Start-Sleep -Milliseconds 400
                $remaining = Get-Process | Where-Object {{ $_.ProcessName -like "*{safe_title}*" -or $_.MainWindowTitle -like "*{safe_title}*" }}
                foreach ($p in $remaining) {{
                    try {{
                        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
                        $closed = $true
                    }} catch {{}}
                }}

                if ($closed) {{
                    Write-Output "STATUS:CLOSED"
                }} else {{
                    Write-Output "STATUS:NOT_FOUND"
                }}
                '''
                res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
                out = res.stdout.strip()
                if "STATUS:CLOSED" in out:
                    return {"success": True, "output": f"Successfully closed application/window matching '{window_title}'.", "error": None}
                else:
                    return {"success": False, "output": "", "error": f"No running window or process matching '{window_title}' was found."}

            # 4. Action: Click Element (via UIAutomation)
            elif action == "click_element":
                if not element_name:
                    return {"success": False, "output": "", "error": "element_name is required for click_element."}
                
                try:
                    import uiautomation as auto
                    search_root = auto.GetRootControl()
                    if window_title:
                        win = auto.WindowControl(searchDepth=1, SubName=window_title)
                        if win.Exists(maxSearchSeconds=2):
                            search_root = win
                            win.SetActive()
                    
                    target = search_root.Control(searchDepth=6, Name=element_name)
                    if target.Exists(maxSearchSeconds=3):
                        target.Click()
                        return {"success": True, "output": state_prefix + f"Clicked UI element '{element_name}' in {window_title or 'active window'}.\n[MANDATORY VERIFICATION] You must now run action='capture_screen' to verify the expected result appeared before proceeding.", "error": None}
                    else:
                        return {"success": False, "output": "", "error": f"Could not find UI control with name '{element_name}'."}
                except Exception as uia_err:
                    return {"success": False, "output": "", "error": f"UIAutomation click failed: {uia_err}"}

            # 4. Action: Click Screen Coordinates
            elif action == "click_coordinates":
                if x is None or y is None:
                    return {"success": False, "output": "", "error": "x and y coordinates are required for click_coordinates."}
                import pyautogui
                pyautogui.FAILSAFE = True
                pyautogui.click(int(x), int(y))
                return {"success": True, "output": state_prefix + f"Clicked screen coordinates ({x}, {y}).\n[MANDATORY VERIFICATION] You must now run action='capture_screen' to verify the expected result appeared before proceeding.", "error": None}

            # 5. Action: Capture Screen
            elif action == "capture_screen":
                os.makedirs("data/screenshots", exist_ok=True)
                filename = f"data/screenshots/desktop_shot_{int(time.time())}.png"
                import pyautogui
                shot = pyautogui.screenshot()
                shot.save(filename)
                return {
                    "success": True,
                    "output": f"Captured desktop screenshot ({shot.size[0]}x{shot.size[1]}): {filename}",
                    "error": None,
                }

            # 6. Action: List Open Windows
            elif action == "list_open_windows":
                ps_script = '''
                Get-Process | Where-Object { $_.MainWindowTitle -ne "" } | Select-Object Id, ProcessName, MainWindowTitle | ConvertTo-Json
                '''
                res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
                import json as _json
                try:
                    data = _json.loads(res.stdout.strip())
                    if isinstance(data, dict):
                        data = [data]
                    lines = [f"• [{item.get('ProcessName')}] (PID: {item.get('Id')}): {item.get('MainWindowTitle')}" for item in data if item.get('MainWindowTitle')]
                    return {"success": True, "output": "Active Desktop Windows:\n" + "\n".join(lines), "error": None}
                except Exception:
                    return {"success": True, "output": res.stdout.strip() or "No top-level window titles found.", "error": None}

            else:
                return {"success": False, "output": "", "error": f"Unknown GUI action: '{action}'."}

        except Exception as e:
            return {"success": False, "output": "", "error": f"GUI automation error: {e}"}

    # ── search_emails ─────────────────────────────────────────────────────────

    def _handle_search_emails(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._email_engine:
            return {"success": False, "output": "", "error": "EmailEngine is not available."}

        res = self._email_engine.search_inbox(
            query=inp.get("query", ""),
            sender=inp.get("sender", ""),
            subject=inp.get("subject", ""),
            unread_only=inp.get("unread_only", False),
            folder=inp.get("folder", "INBOX"),
            profile=inp.get("profile", "primary"),
            limit=inp.get("limit", 10),
        )

        if not res.get("success"):
            return {
                "success": False,
                "output": "",
                "error": res.get("error", "Email search failed."),
            }

        matches = res.get("matches", [])
        if not matches:
            return {
                "success": True,
                "output": f"No emails found in {res.get('folder', 'INBOX')} matching your search criteria for account {res.get('account')}.",
                "error": None,
            }

        lines = [f"Found {len(matches)} email(s) for account {res.get('account')} ({res.get('folder')}):"]
        for m in matches:
            lines.append(f"• ID: {m['id']} | From: {m['from']} | Date: {m['date']} | Subject: {m['subject']}")

        return {
            "success": True,
            "output": "\n".join(lines),
            "error": None,
        }

    # ── read_email_thread ─────────────────────────────────────────────────────

    def _handle_read_email_thread(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._email_engine:
            return {"success": False, "output": "", "error": "EmailEngine is not available."}

        msg_id = str(inp.get("message_id", "")).strip()
        if not msg_id:
            return {"success": False, "output": "", "error": "message_id is required."}

        res = self._email_engine.read_email_thread(
            message_id=msg_id,
            folder=inp.get("folder", "INBOX"),
            profile=inp.get("profile", "primary"),
        )

        if not res.get("success"):
            return {
                "success": False,
                "output": "",
                "error": res.get("error", "Failed to read email thread."),
            }

        output_text = (
            f"Subject: {res.get('subject')}\n"
            f"From: {res.get('from')}\n"
            f"To: {res.get('to')}\n"
            f"Date: {res.get('date')}\n"
            f"Attachments: {', '.join(res.get('attachments', [])) or 'None'}\n\n"
            f"--- Email Body ---\n"
            f"{res.get('body_plain') or res.get('snippet')}"
        )

        return {
            "success": True,
            "output": output_text,
            "error": None,
        }

    # ── draft_email ───────────────────────────────────────────────────────────

    def _handle_draft_email(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._email_engine:
            return {"success": False, "output": "", "error": "EmailEngine is not available."}

        to = inp.get("to", "").strip()
        subject = inp.get("subject", "").strip()
        body = inp.get("body", "").strip()

        if not to or not subject or not body:
            return {"success": False, "output": "", "error": "'to', 'subject', and 'body' are required to draft an email."}

        res = self._email_engine.draft_email(
            to=to,
            subject=subject,
            body=body,
            cc=inp.get("cc", ""),
            bcc=inp.get("bcc", ""),
            profile=inp.get("profile", "primary"),
        )

        if not res.get("success"):
            return {"success": False, "output": "", "error": res.get("error", "Draft creation failed.")}

        output_text = (
            f"✅ Draft created successfully ({res['draft_id']})\n"
            f"From: {res.get('from')}\n"
            f"To: {res.get('to')}\n"
            f"Subject: {res.get('subject')}\n"
            f"Saved to: {res.get('eml_path')}\n\n"
            f"Preview:\n{res.get('preview')}"
        )

        return {
            "success": True,
            "output": output_text,
            "error": None,
        }

    # ── send_email ────────────────────────────────────────────────────────────

    def _handle_send_email(self, inp: dict[str, Any]) -> dict[str, Any]:
        if not self._email_engine:
            return {"success": False, "output": "", "error": "EmailEngine is not available."}

        to = inp.get("to", "").strip()
        subject = inp.get("subject", "").strip()
        body = inp.get("body", "").strip()

        if not to or not subject or not body:
            return {"success": False, "output": "", "error": "'to', 'subject', and 'body' are required to send an email."}

        res = self._email_engine.send_email(
            to=to,
            subject=subject,
            body=body,
            cc=inp.get("cc", ""),
            bcc=inp.get("bcc", ""),
            profile=inp.get("profile", "primary"),
            attachments=inp.get("attachments"),
        )

        if not res.get("success"):
            return {
                "success": False,
                "output": "",
                "error": res.get("error", "Email dispatch failed."),
            }

        output_text = (
            f"🚀 Outbound Email Sent!\n"
            f"From: {res.get('from')}\n"
            f"To: {res.get('to')}\n"
            f"Subject: {res.get('subject')}\n"
            f"Status: {res.get('status')} | Message-ID: {res.get('message_id')}"
        )

        return {
            "success": True,
            "output": output_text,
            "error": None,
        }




    def _handle_sleep_seconds(self, args: dict[str, Any]) -> dict[str, Any]:
        seconds = args.get('seconds', 0)
        time.sleep(seconds)
        return {
            'success': True,
            'output': f'Successfully slept for {seconds} seconds.',
            'error': None
        }

    async def _handle_execute_command_async(self, inp: dict[str, Any], timeout_sec: float = DEFAULT_TOOL_TIMEOUT_SEC) -> dict[str, Any]:
        import asyncio
        import platform
        import subprocess
        
        command = inp.get("command", "").strip()
        working_dir = inp.get("working_directory", self._project_root)

        self.sandbox.validate_command(command)

        if working_dir and working_dir != ".":
            working_dir = self.sandbox.validate_file_path(working_dir, "read")
        else:
            working_dir = self._project_root

        is_win = platform.system() == "Windows"
        internal_timeout = min(float(self.sandbox.config.command_timeout), max(0.5, timeout_sec - 0.5) if timeout_sec > 1.0 else timeout_sec)
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )
            
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=internal_timeout
                )
                stdout_data = stdout_bytes.decode('utf-8', errors='replace')
                stderr_data = stderr_bytes.decode('utf-8', errors='replace')
            except asyncio.TimeoutError:
                if is_win:
                    subprocess.run(f"taskkill /F /T /PID {process.pid}", shell=True, capture_output=True)
                else:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                
                return {
                    "success": False,
                    "output": "",
                    "error": f"Command timed out after {internal_timeout:.1f}s. Process forcefully terminated.",
                }

            output = ""
            if stdout_data:
                output += stdout_data
            if stderr_data:
                if output:
                    output += "\n--- STDERR ---\n"
                output += stderr_data

            output = self.sandbox.truncate_output(output or "(no output)")

            return {
                "success": process.returncode == 0,
                "output": output,
                "error": None if process.returncode == 0 else f"Exit code: {process.returncode}",
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    async def _handle_run_python_async(self, inp: dict[str, Any], timeout_sec: float = DEFAULT_TOOL_TIMEOUT_SEC) -> dict[str, Any]:
        import asyncio
        import tempfile
        import os
        import platform
        import subprocess
        
        code = inp.get("code", "").strip()
        
        try:
            self.sandbox.validate_python_code(code)
        except (SandboxViolation, ASTSecurityViolation) as e:
            return {
                "success": False,
                "output": "",
                "error": f"{e}\n💡 HINT: 'run_python' restricts direct OS/system access ('os', 'sys', 'subprocess'). To list, read, or write files, use the 'file_operation' tool. To run system/shell commands, use 'execute_command'.",
                "duration_ms": 0,
            }

        bootstrap = (
            "import sys\n"
            "try:\n"
            "    sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
            "    sys.stderr.reconfigure(encoding='utf-8', errors='replace')\n"
            "except Exception:\n"
            "    pass\n\n"
        )
        full_code = bootstrap + code

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as temp_script:
                temp_script.write(full_code)
                temp_script_path = temp_script.name

            is_win = platform.system() == "Windows"
            internal_timeout = min(float(self.sandbox.config.python_timeout), max(0.5, timeout_sec - 0.5) if timeout_sec > 1.0 else timeout_sec)
            process = await asyncio.create_subprocess_shell(
                f"python \"{temp_script_path}\"",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._project_root,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=internal_timeout
                )
                stdout_data = stdout_bytes.decode('utf-8', errors='replace')
                stderr_data = stderr_bytes.decode('utf-8', errors='replace')
            except asyncio.TimeoutError:
                if is_win:
                    subprocess.run(f"taskkill /F /T /PID {process.pid}", shell=True, capture_output=True)
                else:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                
                os.unlink(temp_script_path)
                return {
                    "success": False,
                    "output": "",
                    "error": f"Python script timed out after {internal_timeout:.1f}s.",
                }
                
            os.unlink(temp_script_path)

            output = ""
            if stdout_data:
                output += stdout_data
            if stderr_data:
                if output:
                    output += "\n--- STDERR ---\n"
                output += stderr_data

            output = self.sandbox.truncate_output(output or "(no output)")

            return {
                "success": process.returncode == 0,
                "output": output,
                "error": None if process.returncode == 0 else f"Exit code: {process.returncode}",
            }

        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

