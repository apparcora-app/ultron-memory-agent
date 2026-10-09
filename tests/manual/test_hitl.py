import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import os
import sys
import json
import asyncio
from infrastructure.sandbox import Sandbox, SandboxConfig, SandboxViolation
from core.tool_definitions import ToolExecutor

def test_sandbox_validation():
    print("--- Sandbox Validation Tests ---")
    sandbox = Sandbox(SandboxConfig(allowed_paths=[os.path.abspath('.')]))
    
    # 1. Shell command (approve)
    os.environ["_MOCK_APPROVAL_INPUT"] = "approve"
    try:
        sandbox.validate_command("dir")
        print("Command 'dir' with 'approve': ALLOWED")
    except SandboxViolation as e:
        print(f"Command 'dir' with 'approve': BLOCKED ({e})")
        
    # 2. Shell command (deny)
    os.environ["_MOCK_APPROVAL_INPUT"] = "deny"
    try:
        sandbox.validate_command("dir")
        print("Command 'dir' with 'deny': ALLOWED")
    except SandboxViolation as e:
        print(f"Command 'dir' with 'deny': BLOCKED ({e})")

    # 3. Python code (timeout)
    os.environ["_MOCK_APPROVAL_INPUT"] = "TIMEOUT"
    try:
        sandbox.validate_python_code("print('hello')")
        print("Python 'print' with 'timeout': ALLOWED")
    except SandboxViolation as e:
        print(f"Python 'print' with 'timeout': BLOCKED ({e})")

    # 4. File delete (deny)
    os.environ["_MOCK_APPROVAL_INPUT"] = "deny"
    try:
        sandbox.validate_file_path("test.txt", operation="delete")
        print("File 'delete' with 'deny': ALLOWED")
    except SandboxViolation as e:
        print(f"File 'delete' with 'deny': BLOCKED ({e})")

    # 5. File read (should NOT prompt)
    os.environ["_MOCK_APPROVAL_INPUT"] = "TIMEOUT"  # if it prompts, it will fail
    try:
        sandbox.validate_file_path("test.txt", operation="read")
        print("File 'read' (no prompt): ALLOWED")
    except SandboxViolation as e:
        print(f"File 'read' (no prompt): BLOCKED ({e})")

async def test_agent_tools():
    print("\n--- Agent Tool Execution Tests ---")
    from agent import MemoryAgent
    agent = MemoryAgent()
    
    # Test DB memory write through agent wrapper check
    os.environ["_MOCK_APPROVAL_INPUT"] = "deny"
    res = agent._check_irreversible_action("core_memory_update", {"memory_id": "123"})
    print(f"Agent tool 'core_memory_update' with 'deny': {'ALLOWED' if res else 'BLOCKED'}")

    os.environ["_MOCK_APPROVAL_INPUT"] = "approve"
    res = agent._check_irreversible_action("send_email", {"to": "test@example.com"})
    print(f"Agent tool 'send_email' with 'approve': {'ALLOWED' if res else 'BLOCKED'}")

    os.environ["_MOCK_APPROVAL_INPUT"] = "TIMEOUT"
    res = agent._check_irreversible_action("control_desktop_gui", {"action": "click"})
    print(f"Agent tool 'control_desktop_gui' with 'timeout': {'ALLOWED' if res else 'BLOCKED'}")

if __name__ == "__main__":
    test_sandbox_validation()
    asyncio.run(test_agent_tools())
