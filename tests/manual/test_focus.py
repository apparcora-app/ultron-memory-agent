import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.tool_definitions import ToolExecutor
import subprocess
import time

def run_tests():
    executor = ToolExecutor()
    
    # Open notepad
    print("Opening Notepad...")
    subprocess.Popen("notepad.exe")
    time.sleep(2)
    
    # Open calculator and focus it
    print("Opening Calculator (stealing focus)...")
    subprocess.Popen("calc.exe")
    time.sleep(2)
    
    # Attempt to send keys to Notepad (which exists but is NOT focused)
    print("Attempting to send keys to Notepad...")
    inp = {
        "action": "send_keys",
        "window_title": "Notepad",
        "keys": "hello"
    }
    out = executor._handle_control_desktop_gui(inp)
    print('GUI_ACTION:', out)

    # Cleanup
    subprocess.run("taskkill /F /IM notepad.exe", shell=True)
    subprocess.run("taskkill /F /IM calc.exe", shell=True)
    subprocess.run("taskkill /F /IM CalculatorApp.exe", shell=True)

if __name__ == '__main__':
    run_tests()
