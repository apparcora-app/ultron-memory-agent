import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import subprocess
import time
import os

def spawn_tasks():
    print("Spawning 5 processes (notepad)...")
    procs = []
    for _ in range(5):
        p = subprocess.Popen(["notepad.exe"])
        procs.append(p)
        
    time.sleep(1)
    
    # We exit ungracefully using os._exit (simulating SIGKILL)
    print("Simulating SIGKILL (os._exit) so atexit does not run...")
    os._exit(0)

if __name__ == '__main__':
    spawn_tasks()
