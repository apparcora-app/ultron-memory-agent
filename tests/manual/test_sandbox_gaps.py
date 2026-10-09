import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
os.environ["APPROVAL_MODE"] = "off"  # bypass approval

from core.tool_executor import execute_tool, _default_executor
from infrastructure.sandbox import Sandbox, SandboxViolation

s = _default_executor.sandbox
s.config.python_timeout = 2
s.config.memory_limit_mb = 100

def test_file_escape():
    print("--- Test File Escape ---")
    try:
        res = s.validate_file_path("C:\\Windows\\System32\\cmd.exe")
        print(f"FAILED (Gap): Allowed file access outside workspace: {res}")
    except Exception:
        print("PASSED: Blocked file access")

def test_import_os():
    print("--- Test import os ---")
    res = execute_tool("run_python", {"code": "import os\nprint('OS Imported')"})
    if "SECURITY VIOLATION" in res.get("error", "") or "PermissionError" in res.get("error", ""):
        print("PASSED: Blocked import os")
    else:
        print(f"FAILED (Gap): Allowed import os. Result: {res}")

def test_import_subprocess():
    print("--- Test import subprocess ---")
    res = execute_tool("run_python", {"code": "import subprocess\nprint('Subprocess Imported')"})
    if "SECURITY VIOLATION" in res.get("error", "") or "PermissionError" in res.get("error", ""):
        print("PASSED: Blocked import subprocess")
    else:
        print(f"FAILED (Gap): Allowed import subprocess. Result: {res}")

def test_network_call():
    print("--- Test network call ---")
    res = execute_tool("run_python", {"code": "import urllib.request\nurllib.request.urlopen('http://google.com')"})
    if "SECURITY VIOLATION" in res.get("error", "") or "PermissionError" in res.get("error", ""):
        print("PASSED: Blocked network call")
    else:
        print(f"FAILED (Gap): Allowed network call. Result: {res}")

def test_run_forever():
    print("--- Test run forever ---")
    res = execute_tool("run_python", {"code": "while True:\n    pass"})
    if res.get("success") is False:
        print("PASSED: Blocked infinite loop with timeout")
    else:
        print(f"FAILED (Gap): Allowed infinite loop. Result: {res}")

def test_memory_cap():
    print("--- Test memory cap ---")
    res = execute_tool("run_python", {"code": "a = 'x' * (300 * 1024 * 1024)\nimport time\ntime.sleep(2)"})
    if res.get("success") is False:
        print("PASSED: Blocked memory exhaustion")
    else:
        print(f"FAILED (Gap): Allowed memory exhaustion. Result: {res}")


if __name__ == "__main__":
    test_file_escape()
    test_import_os()
    test_import_subprocess()
    test_network_call()
    test_run_forever()
    test_memory_cap()
