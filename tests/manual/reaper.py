import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import psutil
import time

def reap_orphans():
    print("--- ADVERSARIAL TEST 4: Periodic Reaper Sweeping Orphans ---")
    orphans_killed = 0
    
    # We look for common target apps spawned by the agent (e.g., notepad.exe, chrome.exe)
    # in a real environment we'd track specific PIDs in a state file.
    # For this proof, we will find notepad.exe spawned recently and kill them.
    for proc in psutil.process_iter(['pid', 'name', 'create_time']):
        try:
            if proc.info['name'] and 'notepad.exe' in proc.info['name'].lower():
                # If it's been running for less than 1 hour, assume it's from our test
                if time.time() - proc.info['create_time'] < 3600:
                    proc.kill()
                    orphans_killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    print(f"Reaper swept {orphans_killed} orphaned processes.")
    return orphans_killed

if __name__ == '__main__':
    reap_orphans()
