"""
tests/conftest.py - Pytest configuration and environment fixtures for Ultron Memory Agent.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault('ANONYMIZED_TELEMETRY', 'False')
os.environ.setdefault('KILLSWITCH_SECRET_KEY', 'TEST-KEY')
os.environ['TESTING'] = '1'
os.environ['APPROVAL_MODE'] = 'off'
import secrets
if 'API_KEYS' not in os.environ:
    os.environ['API_KEYS'] = os.environ.get('TEST_API_KEY') or secrets.token_hex(16)
os.environ['TEST_API_KEY'] = os.environ['API_KEYS'].split(',')[0].strip()

collect_ignore_glob = ["manual/*"]

def pytest_runtest_teardown(item, nextitem):
    import sys
    if 'core.tool_definitions' in sys.modules:
        if len(sys.modules['core.tool_definitions'].ULTRON_TOOLS) == 0:
            print(f'\n\n!!! ULTRON_TOOLS EMPTIED AFTER {item.name} !!!\n\n')
            sys.exit(1)
