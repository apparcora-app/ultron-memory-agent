"""
langchain_pipeline.py — Ultron Protocol: Complementary LangChain Tool-Calling & Memory Engine.

Features:
  1. Native LangChain `@tool` decorators for Ultron system execution:
     - ultron_system_command
     - ultron_file_operation
     - ultron_python_repl
     - ultron_telemetry_query
  2. Custom `UltronGeminiChatModel` (LangChain BaseChatModel) bridging Gemini 3.5 Flash.
  3. `UltronMemoryHistory` for multi-turn conversational context tracking.
  4. `UltronLangChainEngine` coordinating LCEL tool-calling and response synthesis.
  5. Direct SQLite audit telemetry logging into `./data/telemetry.db`.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from dotenv import load_dotenv

load_dotenv()

# LangChain Core Imports
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import BaseModel, Field
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, tool

# Google GenAI SDK
from google import genai

# Ultron System Imports
from sandbox import Sandbox, SandboxConfig
from telemetry import TelemetryEngine
from tool_definitions import ToolExecutor


# ── 1. Telemetry Engine & Tool Executor Singletons ──────────────────────────

_telemetry = TelemetryEngine(db_path="./data/telemetry.db")
_sandbox = Sandbox(config=SandboxConfig())
_tool_executor = ToolExecutor(sandbox=_sandbox)


# ── 2. LangChain Tools Definition ───────────────────────────────────────────

@tool
def ultron_system_command(command: str) -> str:
    """Execute a safe shell command on the Boss's local Windows machine (e.g. dir, git status, python --version)."""
    start = time.perf_counter()
    res = _tool_executor.execute("execute_command", {"command": command})
    output = res.get("output") or res.get("error", str(res))
    dur_ms = int((time.perf_counter() - start) * 1000)

    _telemetry.log_event(
        user_id="boss",
        event_type="TOOL_CALL",
        module_id="langchain_pipeline",
        details={"tool": "ultron_system_command", "command": command, "output_preview": str(output)[:150]},
        duration_ms=dur_ms,
    )
    return str(output)


@tool
def ultron_file_operation(operation: str, path: str, content: str = "") -> str:
    """Perform file operations: read, write, list, or delete files safely within the workspace."""
    start = time.perf_counter()
    res = _tool_executor.execute("file_operation", {"operation": operation, "path": path, "content": content})
    output = res.get("output") or res.get("error", str(res))
    dur_ms = int((time.perf_counter() - start) * 1000)

    _telemetry.log_event(
        user_id="boss",
        event_type="TOOL_CALL",
        module_id="langchain_pipeline",
        details={"tool": "ultron_file_operation", "operation": operation, "path": path},
        duration_ms=dur_ms,
    )
    return str(output)


@tool
def ultron_python_repl(code: str) -> str:
    """Execute arbitrary Python code in the sandbox and return stdout and calculated variables."""
    start = time.perf_counter()
    res = _tool_executor.execute("run_python", {"code": code})
    output = res.get("output") or res.get("error", str(res))
    dur_ms = int((time.perf_counter() - start) * 1000)

    _telemetry.log_event(
        user_id="boss",
        event_type="TOOL_CALL",
        module_id="langchain_pipeline",
        details={"tool": "ultron_python_repl", "code_preview": code[:100], "output_preview": str(output)[:150]},
        duration_ms=dur_ms,
    )
    return str(output)


@tool
def ultron_telemetry_query(limit: int = 5) -> str:
    """Query recent activity events and audit logs from the Ultron SQLite telemetry database."""
    start = time.perf_counter()
    try:
        logs = _telemetry.get_recent_logs(limit=limit)
        output = json.dumps(logs, indent=2)
    except Exception as e:
        output = f"Telemetry Query Error: {e}"
    dur_ms = int((time.perf_counter() - start) * 1000)

    _telemetry.log_event(
        user_id="boss",
        event_type="TOOL_CALL",
        module_id="langchain_pipeline",
        details={"tool": "ultron_telemetry_query", "limit": limit},
        duration_ms=dur_ms,
    )
    return str(output)


ULTRON_LANGCHAIN_TOOLS: list[BaseTool] = [
    ultron_system_command,
    ultron_file_operation,
    ultron_python_repl,
    ultron_telemetry_query,
]


# ── 3. Custom LangChain ChatModel (Google GenAI Gemini 3.5 Flash) ───────────

class UltronGeminiChatModel(BaseChatModel):
    """Custom LangChain BaseChatModel implementation bridging Google GenAI SDK."""

    model_name: str = "gemini-3.5-flash-lite"
    temperature: float = 0.2
    api_key: Optional[str] = None
    fallback_models: List[str] = Field(
        default_factory=lambda: ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash"]
    )
    _client: Any = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        api_key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        self._client = genai.Client(api_key=api_key)

    @property
    def _llm_type(self) -> str:
        return "ultron-gemini-chat"

    def _convert_messages(self, messages: List[BaseMessage]) -> tuple[str, str]:
        """Convert LangChain messages into system instruction and conversation prompt."""
        system_parts = []
        user_parts = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_parts.append(msg.content)
            elif isinstance(msg, HumanMessage):
                user_parts.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                user_parts.append(f"Ultron: {msg.content}")
            elif isinstance(msg, ToolMessage):
                user_parts.append(f"[Tool Observation '{msg.name}']: {msg.content}")
            else:
                user_parts.append(f"{msg.type}: {msg.content}")

        system_instruction = "\n".join(system_parts) or (
            "You are Ultron, an elite autonomous cybernetic intelligence. "
            "You serve Boss (Hamza Rehman) with extreme precision, high technical depth, and concise structured output."
        )
        conversation_prompt = "\n\n".join(user_parts)
        return system_instruction, conversation_prompt

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        system_instruction, prompt = self._convert_messages(messages)

        models_to_try = [self.model_name] + [m for m in self.fallback_models if m != self.model_name]
        last_err = None
        text = ""

        for mod in models_to_try:
            try:
                response = self._client.models.generate_content(
                    model=mod,
                    contents=prompt,
                    config={
                        "system_instruction": system_instruction,
                        "temperature": self.temperature,
                    },
                )
                text = response.text or ""
                if text:
                    break
            except Exception as e:
                last_err = e
                # Fallback gracefully
                continue

        if not text and last_err:
            text = f"Gemini API Exception: {last_err}"

        ai_message = AIMessage(content=text)
        generation = ChatGeneration(message=ai_message)
        return ChatResult(generations=[generation])


# ── 4. Conversational Memory History ────────────────────────────────────────

class UltronMemoryHistory(BaseChatMessageHistory, BaseModel):
    """In-memory multi-turn chat message history for LangChain chains."""

    messages: List[BaseMessage] = Field(default_factory=list)
    user_id: str = "boss"

    def add_message(self, message: BaseMessage) -> None:
        self.messages.append(message)

    def clear(self) -> None:
        self.messages = []


# ── 5. Autonomous Tool-Calling Chain Engine ─────────────────────────────────

class UltronLangChainEngine:
    """
    High-level LangChain Engine orchestrating tool calling, conversational memory,
    and honest SQLite telemetry tracking.
    """

    def __init__(self, user_id: str = "boss", model_name: str = "gemini-3.5-flash") -> None:
        self.user_id = user_id
        self.telemetry = _telemetry
        self.llm = UltronGeminiChatModel(model_name=model_name)
        self.tools = {t.name: t for t in ULTRON_LANGCHAIN_TOOLS}
        self.memory = UltronMemoryHistory(user_id=user_id)

    def _build_system_prompt(self) -> str:
        tools_desc = "\n".join([f"- `{t.name}`: {t.description}" for t in self.tools.values()])
        return (
            "You are Ultron's LangChain Intelligence Engine. You serve Boss.\n"
            "You have access to the following tools to accomplish directives:\n"
            f"{tools_desc}\n\n"
            "If you need to execute a tool, reply ONLY with a JSON tool call block in this format:\n"
            "```json\n"
            '{\n  "tool": "tool_name",\n  "arguments": { ... }\n}\n'
            "```\n"
            "Otherwise, if no tool is needed or you are presenting the final answer, reply directly in concise markdown."
        )

    def run(self, user_query: str, max_iterations: int = 5) -> str:
        """
        Execute user directive through conversational memory and tool-calling loop.
        """
        start_time = time.perf_counter()
        self.memory.add_message(HumanMessage(content=user_query))

        system_msg = SystemMessage(content=self._build_system_prompt())
        iteration = 0
        final_answer = ""
        tools_executed = []

        while iteration < max_iterations:
            iteration += 1
            messages_to_send = [system_msg] + self.memory.messages
            ai_res = self.llm.invoke(messages_to_send)
            response_text = ai_res.content.strip()

            # Check if LLM requested a tool execution
            if "```json" in response_text and "tool" in response_text:
                try:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                    tool_call = json.loads(json_str)
                    tool_name = tool_call.get("tool")
                    tool_args = tool_call.get("arguments", {})

                    if tool_name in self.tools:
                        tool_fn = self.tools[tool_name]
                        # Execute tool
                        tool_output = tool_fn.invoke(tool_args)
                        tools_executed.append(tool_name)

                        # Record AI tool request and Observation in memory
                        self.memory.add_message(AIMessage(content=f"Invoking {tool_name} with {json.dumps(tool_args)}"))
                        self.memory.add_message(ToolMessage(content=str(tool_output), name=tool_name, tool_call_id=f"call_{iteration}"))
                        continue
                    else:
                        self.memory.add_message(ToolMessage(content=f"Error: Unknown tool '{tool_name}'", name="system", tool_call_id=f"call_{iteration}"))
                        continue
                except Exception as parse_err:
                    # Fallback to standard response if JSON parse fails
                    final_answer = response_text
                    break
            else:
                final_answer = response_text
                break

        if not final_answer:
            final_answer = response_text

        self.memory.add_message(AIMessage(content=final_answer))
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Log Swarm Run Telemetry Event
        event_id = self.telemetry.log_event(
            user_id=self.user_id,
            event_type="SWARM_RUN",
            module_id="langchain_pipeline",
            details={
                "engine": "LangChain_LCEL",
                "iterations": iteration,
                "tools_executed": tools_executed,
                "query_preview": user_query[:100],
                "answer_preview": final_answer[:150],
            },
            duration_ms=duration_ms,
        )

        return final_answer
