"""
contracts.py — Ultron Protocol: Strict Boundary Contracts & Pydantic v2 Enforcement.

Defines fail-fast Pydantic v2 schemas for:
  1. All 19 system tools (Input & Output schemas)
  2. Core Agent invocation inputs and final synthesis outputs
  3. Inter-node state schemas (LangGraph StateGraph handoff)
  4. Ingress API and CLI request payloads

Enforces:
  - `model_config = ConfigDict(extra="forbid", strict=True)` to reject unvalidated/hallucinated
    parameters and forbid silent type coercions.
  - Fail-fast structured ContractValidationError reporting field, expected_type, received_value,
    and error_reason.
"""

from __future__ import annotations
from core.log_config import get_logger

from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ContractValidationError(ValueError):
    """
    Structured validation error raised fail-fast when an ingress or egress payload
    violates strict boundary contracts.
    """

    def __init__(
        self,
        field: str,
        expected_type: str,
        received_value: Any,
        error_reason: str,
        message: str | None = None,
    ) -> None:
        self.field = field
        self.expected_type = expected_type
        self.received_value = received_value
        self.error_reason = error_reason
        full_message = message or (
            f"Contract violation on field '{field}': expected {expected_type}, "
            f"received {type(received_value).__name__} ({received_value!r}). Reason: {error_reason}"
        )
        super().__init__(full_message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "expected_type": self.expected_type,
            "received_value": self.received_value,
            "error_reason": self.error_reason,
        }


class StrictBaseModel(BaseModel):
    """
    Base model enforcing strict typing and forbidding extra/unrecognized fields.
    """
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        arbitrary_types_allowed=True,
    )


def _format_type_annotation(annotation: Any) -> str:
    """Helper to cleanly render Python type annotations in error messages."""
    if annotation is None:
        return "None"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def validate_contract(model_cls: type[StrictBaseModel], payload: Any) -> Any:
    """
    Validate a payload dictionary against a strict contract model.
    Raises ContractValidationError fail-fast on any contract violation.
    """
    if isinstance(payload, model_cls):
        return payload

    if not isinstance(payload, dict):
        raise ContractValidationError(
            field="__root__",
            expected_type="dict",
            received_value=payload,
            error_reason=f"Payload must be a dictionary, received {type(payload).__name__}",
        )

    try:
        return model_cls.model_validate(payload)
    except ValidationError as err:
        errors = err.errors()
        first_err = errors[0] if errors else {}
        loc = first_err.get("loc", ())
        field_name = ".".join(str(p) for p in loc) if loc else "__root__"
        err_type = first_err.get("type", "")
        error_reason = first_err.get("msg", "Validation failed")
        input_val = first_err.get("input")

        # Determine expected type
        field_key = str(loc[0]) if loc else None
        field_info = model_cls.model_fields.get(field_key) if field_key and hasattr(model_cls, "model_fields") else None

        if err_type == "extra_forbidden":
            expected_type = "None (extra fields forbidden)"
        elif err_type == "missing":
            expected_type = _format_type_annotation(field_info.annotation) if field_info else "Required"
            input_val = None
        elif field_info and field_info.annotation is not None:
            expected_type = _format_type_annotation(field_info.annotation)
        else:
            expected_type = err_type

        raise ContractValidationError(
            field=field_name,
            expected_type=expected_type,
            received_value=input_val,
            error_reason=error_reason,
        ) from err


# ── 1. Tool Input Contracts (19 Registered Tools) ─────────────────────────────

class CoreMemoryUpdateInput(StrictBaseModel):
    block_name: str
    content: str


class CoreMemoryAppendInput(StrictBaseModel):
    block_name: str
    text: str


class CoreMemoryReplaceInput(StrictBaseModel):
    block_name: str
    old_text: str
    new_text: str


class StoreFileMemoryInput(StrictBaseModel):
    filename: str
    findings: str


class SearchFileMemoryInput(StrictBaseModel):
    filename: str


class ExecuteCommandInput(StrictBaseModel):
    command: str
    working_directory: str = "."


class FileOperationInput(StrictBaseModel):
    operation: Literal["read", "write", "list", "delete"]
    path: str
    content: str | None = None


class RunPythonInput(StrictBaseModel):
    code: str
    description: str | None = None


class WebSearchInput(StrictBaseModel):
    query: str
    num_results: int = 5


class FetchWebPageInput(StrictBaseModel):
    url: str


class OpenBrowserInput(StrictBaseModel):
    url: str
    profile: str = "default"
    browser: Literal["chrome", "edge", "default"] = "chrome"


class OpenApplicationInput(StrictBaseModel):
    app_name: str
    arguments: str = ""


class DesktopCreateAndShowNoteInput(StrictBaseModel):
    content: str
    filename: str = "ultron_note.txt"
    open_in_foreground: bool = True


class StepStateContract(StrictBaseModel):
    current_step: int
    last_verified_state: str
    expected_next_state: str


class ControlDesktopGuiInput(StrictBaseModel):
    action: Literal[
        "focus_window",
        "send_keys",
        "close_window",
        "click_element",
        "click_coordinates",
        "capture_screen",
        "list_open_windows",
    ]
    window_title: str = ""
    keys: str = ""
    element_name: str = ""
    x: int | None = None
    y: int | None = None
    step_state: StepStateContract | None = None


class SearchEmailsInput(StrictBaseModel):
    query: str = ""
    sender: str = ""
    subject: str = ""
    unread_only: bool = False
    profile: str = "default"
    limit: int = 10


class ReadEmailThreadInput(StrictBaseModel):
    message_id: str
    profile: str = "default"
    folder: str = "INBOX"


class DraftEmailInput(StrictBaseModel):
    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""
    profile: str = "default"


class SendEmailInput(StrictBaseModel):
    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""
    profile: str = "default"
    attachments: list[str] | None = None


class SleepSecondsInput(StrictBaseModel):
    seconds: Union[int, float]


# ── 2. Tool Output Contracts ──────────────────────────────────────────────────

class ToolExecutionOutput(StrictBaseModel):
    success: bool
    output: str
    error: str | None = None
    duration_ms: int = 0


# Tool Contract Registry
TOOL_INPUT_CONTRACTS: dict[str, type[StrictBaseModel]] = {
    "core_memory_update": CoreMemoryUpdateInput,
    "core_memory_append": CoreMemoryAppendInput,
    "core_memory_replace": CoreMemoryReplaceInput,
    "store_file_memory": StoreFileMemoryInput,
    "search_file_memory": SearchFileMemoryInput,
    "execute_command": ExecuteCommandInput,
    "file_operation": FileOperationInput,
    "run_python": RunPythonInput,
    "web_search": WebSearchInput,
    "fetch_web_page": FetchWebPageInput,
    "open_browser": OpenBrowserInput,
    "open_application": OpenApplicationInput,
    "desktop_create_and_show_note": DesktopCreateAndShowNoteInput,
    "control_desktop_gui": ControlDesktopGuiInput,
    "search_emails": SearchEmailsInput,
    "read_email_thread": ReadEmailThreadInput,
    "draft_email": DraftEmailInput,
    "send_email": SendEmailInput,
    "sleep_seconds": SleepSecondsInput,
}

TOOL_OUTPUT_CONTRACTS: dict[str, type[StrictBaseModel]] = {
    tool_name: ToolExecutionOutput for tool_name in TOOL_INPUT_CONTRACTS
}


# ── 3. Core Agent Boundary Contracts ──────────────────────────────────────────

class AgentChatInput(StrictBaseModel):
    user_input: str
    files: list[Any] | None = None
    module_id: str = "ultron_prime"
    model_override: str | None = None
    optimize_prompt: bool = True


class AgentChatOutput(StrictBaseModel):
    reply: str
    model_used: str
    model_display: str
    route_reason: str
    tool_actions: list[dict[str, Any]] = Field(default_factory=list)
    skills_used: list[dict[str, Any]] = Field(default_factory=list)
    swarm_actions: list[dict[str, Any]] = Field(default_factory=list)
    is_swarm: bool = False
    prompt_optimization: dict[str, Any] = Field(default_factory=dict)
    module_id: str | None = None
    files_analyzed: list[dict[str, Any]] | None = None
    budget: dict[str, Any] | None = None
    lockdown: bool = False
    critic_verification: dict[str, Any] | None = None


# ── 4. Inter-Node State Contracts (LangGraph) ─────────────────────────────────

class SwarmHandoffStateContract(StrictBaseModel):
    run_id: str
    user_id: str
    directive: str
    context: str
    titan_task_id: str
    titan_status: str
    titan_output: str
    titan_execution_time_ms: float
    nexus_task_id: str
    nexus_status: str
    nexus_output: str
    nexus_execution_time_ms: float
    current_step: str
    errors: list[str]
    total_duration_sec: float
    version: int = 1


# ── 5. Ingress API Request Contracts ──────────────────────────────────────────

class ChatRequestPayload(StrictBaseModel):
    user_id: str = "boss"
    session_id: str = ""
    message: str = ""
    module_id: str = "ultron_prime"
    model_override: str = "auto"
    model_mode: str = "auto"
    optimize_prompt: bool = True
    operation_mode: str = "SWARM"


class SessionCreatePayload(StrictBaseModel):
    user_id: str = "boss"
    module_id: str = "ultron_prime"
    title: str = "New Directives"


class SessionRenamePayload(StrictBaseModel):
    title: str
    user_id: str = "boss"


class KillswitchTriggerPayload(StrictBaseModel):
    source: str = "HUD_EMERGENCY_BUTTON"
    reason: str = "Operator emergency override"


class KillswitchUnlockPayload(StrictBaseModel):
    secret_key: str

_log = get_logger('contracts')
