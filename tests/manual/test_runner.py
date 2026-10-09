import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import subprocess
import time

def count_notepad():
    out = subprocess.check_output('tasklist /FI "IMAGENAME eq notepad.exe"', shell=True).decode('utf-8', 'ignore')
    return out.count('notepad.exe')

initial = count_notepad()
print('Initial notepads:', initial)

subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'test_orphans.py')], shell=True)

time.sleep(2)
final = count_notepad()
print('Final notepads:', final)
assert initial == final, 'Orphaned notepads found!'
print('SUCCESS: No orphans left.')
