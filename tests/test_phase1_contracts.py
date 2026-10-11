"""
tests/test_phase1_contracts.py — Phase 1 Test Suite: Contract Enforcement & Strict Boundary Typing.

Covers:
  a) Happy-path validation for all schemas (19 tools, agent I/O, LangGraph state, API payloads).
  b) Rejection of payloads containing forbidden/extra keys (extra="forbid").
  c) Rejection of invalid types without automatic coercion (strict=True).
  d) Handling of missing required fields with clear, structured error reporting.
  e) Integration-level boundary validation for ToolExecutor, MemoryAgent, and LangGraph pipeline.
"""

import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from contracts import (
    ContractValidationError,
    StrictBaseModel,
    validate_contract,
    TOOL_INPUT_CONTRACTS,
    TOOL_OUTPUT_CONTRACTS,
    ToolExecutionOutput,
    CoreMemoryUpdateInput,
    CoreMemoryAppendInput,
    CoreMemoryReplaceInput,
    StoreFileMemoryInput,
    SearchFileMemoryInput,
    ExecuteCommandInput,
    FileOperationInput,
    RunPythonInput,
    WebSearchInput,
    FetchWebPageInput,
    OpenBrowserInput,
    OpenApplicationInput,
    DesktopCreateAndShowNoteInput,
    StepStateContract,
    ControlDesktopGuiInput,
    SearchEmailsInput,
    ReadEmailThreadInput,
    DraftEmailInput,
    SendEmailInput,
    SleepSecondsInput,
    AgentChatInput,
    AgentChatOutput,
    SwarmHandoffStateContract,
    ChatRequestPayload,
    SessionCreatePayload,
    SessionRenamePayload,
    KillswitchTriggerPayload,
    KillswitchUnlockPayload,
)
from tool_definitions import ToolExecutor
from langgraph_pipeline import LangGraphTwoStepSwarm


# ── Fixtures & Valid Payloads ──────────────────────────────────────────────────

VALID_TOOL_PAYLOADS = {
    "core_memory_update": {"block_name": "boss_profile", "content": "Updated profile content"},
    "core_memory_append": {"block_name": "session_scratchpad", "text": "New note line"},
    "core_memory_replace": {"block_name": "active_task", "old_text": "task1", "new_text": "task2"},
    "store_file_memory": {"filename": "audit.xlsx", "findings": "Found 3 discrepancies"},
    "search_file_memory": {"filename": "audit.xlsx"},
    "execute_command": {"command": "dir", "working_directory": "."},
    "file_operation": {"operation": "read", "path": "test.txt", "content": None},
    "run_python": {"code": "print('hello')", "description": "test script"},
    "web_search": {"query": "python pydantic v2", "num_results": 3},
    "fetch_web_page": {"url": "https://example.com"},
    "open_browser": {"url": "https://example.com", "profile": "default", "browser": "chrome"},
    "open_application": {"app_name": "notepad", "arguments": ""},
    "desktop_create_and_show_note": {"content": "Test note", "filename": "note.txt", "open_in_foreground": True},
    "control_desktop_gui": {
        "action": "click_element",
        "element_name": "Submit",
        "window_title": "App",
        "keys": "",
        "x": 100,
        "y": 200,
        "step_state": {
            "current_step": 1,
            "last_verified_state": "Home",
            "expected_next_state": "Submitted",
        },
    },
    "search_emails": {"query": "invoice", "sender": "client", "limit": 5, "profile": "default", "unread_only": False},
    "read_email_thread": {"message_id": "msg_123", "profile": "default", "folder": "INBOX"},
    "draft_email": {"to": "client@example.com", "subject": "Review", "body": "Please review", "cc": "", "bcc": "", "profile": "default"},
    "send_email": {"to": "client@example.com", "subject": "Contract", "body": "Here is the contract", "cc": "", "bcc": "", "profile": "default", "attachments": ["file.pdf"]},
    "sleep_seconds": {"seconds": 2},
}


# ── 1. Tool Input Contracts: Happy Path Validation ─────────────────────────────

@pytest.mark.parametrize("tool_name,payload", list(VALID_TOOL_PAYLOADS.items()))
def test_tool_input_happy_path(tool_name: str, payload: dict):
    """Every registered tool schema must validate its canonical happy-path payload."""
    model_cls = TOOL_INPUT_CONTRACTS[tool_name]
    validated = validate_contract(model_cls, payload)
    assert isinstance(validated, model_cls)
    # Check that model_dump contains the key fields
    dump = validated.model_dump()
    for k, v in payload.items():
        if v is not None:
            assert dump[k] == v


# ── 2. Tool Input Contracts: Extra/Forbidden Keys Rejection ───────────────────

@pytest.mark.parametrize("tool_name,payload", list(VALID_TOOL_PAYLOADS.items()))
def test_tool_input_rejects_extra_fields(tool_name: str, payload: dict):
    """extra='forbid' must reject any unknown/hallucinated parameters."""
    model_cls = TOOL_INPUT_CONTRACTS[tool_name]
    poisoned_payload = dict(payload)
    poisoned_payload["__hallucinated_extra_key__"] = "unauthorized_data"

    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(model_cls, poisoned_payload)

    err = exc_info.value
    assert err.field == "__hallucinated_extra_key__"
    assert "extra" in err.error_reason.lower() or "not permitted" in err.error_reason.lower()
    assert err.received_value == "unauthorized_data"


# ── 3. Tool Input Contracts: Type Coercion Prevention (strict=True) ───────────

def test_type_coercion_prevention():
    """strict=True must reject strings passed for int/float fields without coercing."""
    # sleep_seconds expects Union[int, float], passing string '10' must fail without coercion
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(SleepSecondsInput, {"seconds": "10"})
    assert "seconds" in exc_info.value.field

    # web_search num_results expects int, passing string '5' must fail
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(WebSearchInput, {"query": "test", "num_results": "five"})
    assert "num_results" in exc_info.value.field

    # execute_command command expects str, passing int must fail
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(ExecuteCommandInput, {"command": 12345})
    assert "command" in exc_info.value.field

    # file_operation operation enum expects 'read'|'write'|'list'|'delete', invalid string must fail
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(FileOperationInput, {"operation": "destroy_everything", "path": "file.txt"})
    assert "operation" in exc_info.value.field


# ── 4. Tool Input Contracts: Missing Required Fields ──────────────────────────

def test_missing_required_fields():
    """Missing mandatory fields must fail-fast with field name and error reason."""
    # execute_command requires 'command'
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(ExecuteCommandInput, {"working_directory": "."})
    assert exc_info.value.field == "command"
    assert "required" in exc_info.value.error_reason.lower()

    # file_operation requires 'operation' and 'path'
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(FileOperationInput, {"operation": "read"})
    assert exc_info.value.field == "path"
    assert "required" in exc_info.value.error_reason.lower()

    # core_memory_update requires 'block_name' and 'content'
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(CoreMemoryUpdateInput, {"block_name": "boss_profile"})
    assert exc_info.value.field == "content"
    assert "required" in exc_info.value.error_reason.lower()

    # draft_email requires 'to', 'subject', 'body'
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(DraftEmailInput, {"to": "client@example.com"})
    assert exc_info.value.field in ("subject", "body")


# ── 5. Tool Output Contract (ToolExecutionOutput) ─────────────────────────────

def test_tool_output_contract():
    """ToolExecutionOutput must strictly enforce success, output, error, duration_ms."""
    # Happy path
    valid_output = {"success": True, "output": "Execution completed", "error": None, "duration_ms": 42}
    validated = validate_contract(ToolExecutionOutput, valid_output)
    assert validated.success is True
    assert validated.duration_ms == 42

    # Extra field rejection
    with pytest.raises(ContractValidationError):
        validate_contract(ToolExecutionOutput, {**valid_output, "extra_meta": "bad"})

    # Type error (success must be bool, not int or string in strict mode)
    with pytest.raises(ContractValidationError):
        validate_contract(ToolExecutionOutput, {**valid_output, "success": "yes"})

    # Missing required field
    with pytest.raises(ContractValidationError):
        validate_contract(ToolExecutionOutput, {"output": "text"})


# ── 6. Core Agent Contracts (AgentChatInput & AgentChatOutput) ────────────────

def test_agent_chat_input_contract():
    """AgentChatInput must enforce strict typing on user_input, files, module_id."""
    # Happy path
    valid = validate_contract(AgentChatInput, {
        "user_input": "Optimize this resume",
        "files": None,
        "module_id": "career_acquisition",
        "model_override": None,
        "optimize_prompt": True,
    })
    assert valid.user_input == "Optimize this resume"
    assert valid.module_id == "career_acquisition"

    # Extra field forbidden
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(AgentChatInput, {
            "user_input": "Hello",
            "unauthorized_injection": "exploit",
        })
    assert exc_info.value.field == "unauthorized_injection"

    # Invalid type
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(AgentChatInput, {
            "user_input": 99999,
        })
    assert exc_info.value.field == "user_input"


def test_agent_chat_output_contract():
    """AgentChatOutput must enforce strict typing on all final synthesis attributes."""
    valid_payload = {
        "reply": "Analysis complete, Boss.",
        "model_used": "deepseek/deepseek-chat",
        "model_display": "DeepSeek V3",
        "route_reason": "High complexity directive",
        "tool_actions": [{"tool": "run_python", "success": True}],
        "skills_used": [{"id": "anti_slop", "name": "Anti-Slop Protocol"}],
        "swarm_actions": [],
        "is_swarm": False,
        "prompt_optimization": {"applied": True},
        "module_id": "ultron_prime",
        "files_analyzed": None,
        "budget": None,
        "lockdown": False,
        "critic_verification": None,
    }
    validated = validate_contract(AgentChatOutput, valid_payload)
    assert validated.reply == "Analysis complete, Boss."
    assert validated.is_swarm is False

    # Extra field forbidden
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(AgentChatOutput, {**valid_payload, "hallucinated_telemetry": 123})
    assert exc_info.value.field == "hallucinated_telemetry"

    # Type error on boolean
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(AgentChatOutput, {**valid_payload, "is_swarm": "not_a_bool"})
    assert exc_info.value.field == "is_swarm"


# ── 7. LangGraph Inter-Node State Contract ────────────────────────────────────

def test_langgraph_swarm_state_contract():
    """SwarmHandoffStateContract must validate state schema between Titan and Nexus nodes."""
    valid_state = {
        "run_id": "lg_run_12345",
        "user_id": "boss",
        "directive": "Design Telemetry API",
        "context": "Enterprise multi-tenant system",
        "titan_task_id": "task_titan_abc",
        "titan_status": "COMPLETED",
        "titan_output": "POST /api/v1/telemetry",
        "titan_execution_time_ms": 120.5,
        "nexus_task_id": "task_nexus_xyz",
        "nexus_status": "COMPLETED",
        "nexus_output": "<TelemetryView />",
        "nexus_execution_time_ms": 95.0,
        "current_step": "nexus",
        "errors": [],
        "total_duration_sec": 0.215,
    }
    validated = validate_contract(SwarmHandoffStateContract, valid_state)
    assert validated.run_id == "lg_run_12345"
    assert validated.titan_status == "COMPLETED"

    # Extra field forbidden
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(SwarmHandoffStateContract, {**valid_state, "corrupted_cache": True})
    assert exc_info.value.field == "corrupted_cache"

    # Missing mandatory field
    incomplete_state = dict(valid_state)
    del incomplete_state["directive"]
    with pytest.raises(ContractValidationError) as exc_info:
        validate_contract(SwarmHandoffStateContract, incomplete_state)
    assert exc_info.value.field == "directive"


# ── 8. Ingress API Request Contracts ──────────────────────────────────────────

def test_api_ingress_contracts():
    """API request payload contracts must reject malformed requests fail-fast."""
    # ChatRequestPayload happy path
    valid_chat = validate_contract(ChatRequestPayload, {
        "user_id": "boss",
        "session_id": "sess_1",
        "message": "Status check",
        "module_id": "ultron_prime",
        "model_override": "auto",
        "model_mode": "auto",
        "optimize_prompt": True,
    })
    assert valid_chat.message == "Status check"

    # ChatRequestPayload extra field
    with pytest.raises(ContractValidationError):
        validate_contract(ChatRequestPayload, {"message": "hi", "injection": "SELECT *"})

    # SessionCreatePayload
    valid_session = validate_contract(SessionCreatePayload, {"user_id": "boss", "title": "New Directives"})
    assert valid_session.title == "New Directives"

    # KillswitchPayloads
    valid_trigger = validate_contract(KillswitchTriggerPayload, {"source": "HUD", "reason": "Test"})
    assert valid_trigger.source == "HUD"

    valid_unlock = validate_contract(KillswitchUnlockPayload, {"secret_key": "ULTRON_SOVEREIGN_KEY"})
    assert valid_unlock.secret_key == "ULTRON_SOVEREIGN_KEY"


# ── 9. ToolExecutor Ingress Integration Gate ──────────────────────────────────

def test_toolexecutor_integration_boundary():
    """ToolExecutor.execute and execute_async must enforce contracts fail-fast before handler execution."""
    executor = ToolExecutor()

    # Happy path: execute sleep_seconds
    res = executor.execute("sleep_seconds", {"seconds": 0.01})
    assert res["success"] is True
    assert "0.01" in res["output"]

    # Rejection of extra keys at ToolExecutor entry
    with pytest.raises(ContractValidationError) as exc_info:
        executor.execute("sleep_seconds", {"seconds": 0.01, "unauthorized_extra": "drop_tables"})
    err = exc_info.value
    assert err.field == "unauthorized_extra"
    assert "extra" in err.error_reason.lower() or "not permitted" in err.error_reason.lower()

    # Rejection of invalid types at ToolExecutor entry
    with pytest.raises(ContractValidationError) as exc_info:
        executor.execute("execute_command", {"command": ["rm", "-rf", "/"]})
    assert "command" in exc_info.value.field

    # Rejection of missing required fields at ToolExecutor entry
    with pytest.raises(ContractValidationError) as exc_info:
        executor.execute("file_operation", {"path": "test.txt"})
    assert exc_info.value.field == "operation"


def test_toolexecutor_async_integration_boundary():
    """ToolExecutor.execute_async must enforce contracts fail-fast in async execution mesh."""
    import asyncio

    async def _test_flow():
        executor = ToolExecutor()

        # Happy path async
        res = await executor.execute_async("sleep_seconds", {"seconds": 0.01})
        assert res["success"] is True

        # Rejection of extra keys in async
        with pytest.raises(ContractValidationError) as exc_info:
            await executor.execute_async("sleep_seconds", {"seconds": 0.01, "extra_pollutant": 123})
        assert exc_info.value.field == "extra_pollutant"

    asyncio.run(_test_flow())


# ── 10. LangGraph Pipeline Integration Gate ────────────────────────────────────

def test_langgraph_pipeline_contract_boundary():
    """LangGraph node handlers must reject corrupt state payloads fail-fast."""
    pipeline = LangGraphTwoStepSwarm()

    # Passing corrupted state to _titan_node
    corrupt_state = {
        "directive": "Build auth",
        "unexpected_extra_field": "pollutant",
    }
    with pytest.raises(ContractValidationError) as exc_info:
        pipeline._titan_node(corrupt_state)
    assert exc_info.value.field in ("run_id", "unexpected_extra_field")

    # Happy path end-to-end execution validates initial and final state contracts
    res = pipeline.execute("Design secure event streaming endpoints")
    assert res["titan_status"] in ("COMPLETED", "FAILED")
    assert res["nexus_status"] in ("COMPLETED", "FAILED")
    assert "total_duration_sec" in res
