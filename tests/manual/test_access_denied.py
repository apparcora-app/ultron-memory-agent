import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import subprocess
import time
from unittest.mock import patch
from governance.process_tracker import ProcessTracker

def run_adversarial_test():
    tracker = ProcessTracker()
    
    # Spawn a real process
    print("Spawning a real Notepad process...")
    proc = subprocess.Popen(["notepad.exe"])
    tracker.register(proc)
    
    # Mock proc.terminate to raise PermissionError
    original_terminate = proc.terminate
    def mock_terminate():
        raise PermissionError("Access is denied")
    proc.terminate = mock_terminate
    
    # Attempt termination
    print("Attempting to terminate via ProcessTracker (with simulated AccessDenied)...")
    res = tracker.terminate(proc.pid, timeout_sec=0.5)
    
    print(f"Terminate result: {res} (Expected: False)")
    
    # Cleanup real process since mock prevented it
    print("Cleaning up real process...")
    original_terminate()
    proc.wait()

if __name__ == '__main__':
    run_adversarial_test()
