import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.tool_definitions import ToolExecutor, _ACTIVE_PROCESSES
import time
import os

def run_tests():
    executor = ToolExecutor()
    print("Active processes before:", len(_ACTIVE_PROCESSES))
    # Open 10 notepad instances
    for _ in range(10):
        executor.execute('execute_command', {'command': 'notepad'})
    
    print("Active processes after spawning:", len(_ACTIVE_PROCESSES))
    # We will just let the script exit. atexit should kill them.
    # To prove it, we'll write a wrapper that runs this script and then checks if notepad is running.

if __name__ == '__main__':
    run_tests()
