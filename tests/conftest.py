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
