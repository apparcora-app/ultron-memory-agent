import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import os
import sys
import time

def require_approval(action: str, details: str, timeout: int = 30) -> bool:
    if os.environ.get("APPROVAL_MODE", "on").lower() != "on":
        return True

    mock_input = os.environ.get("_MOCK_APPROVAL_INPUT")
    if mock_input is not None:
        if mock_input == "TIMEOUT":
            print(f"\n[TIMEOUT] Action denied.")
            return False
        else:
            decision = mock_input.strip().lower()
            if decision == "approve":
                print("[APPROVED] Executing action.")
                return True
            else:
                print(f"[DENIED] Action blocked.")
                return False

    print(f"\n================ HUMAN APPROVAL REQUIRED ================")
    print(f"ACTION : {action}")
    print(f"DETAILS:\n{details}")
    print(f"---------------------------------------------------------")
    print(f"Type 'approve' or 'deny' within {timeout} seconds. (Default: deny)")
    print(f"=========================================================\n> ", end="", flush=True)

    import msvcrt
    
    start_time = time.time()
    input_str = ""
    while True:
        if time.time() - start_time > timeout:
            print("\n[TIMEOUT] Action denied.")
            return False
        
        if msvcrt.kbhit():
            char = msvcrt.getwche()
            if char in ('\r', '\n'):
                print()
                break
            elif char == '\b':
                if len(input_str) > 0:
                    input_str = input_str[:-1]
                    sys.stdout.write(" \b")
                    sys.stdout.flush()
            else:
                input_str += char
        time.sleep(0.05)

    decision = input_str.strip().lower()
    if decision == "approve":
        print("[APPROVED] Executing action.")
        return True
    else:
        print(f"[DENIED] Action blocked. (Input: '{decision}')")
        return False

if __name__ == "__main__":
    os.environ["_MOCK_APPROVAL_INPUT"] = "approve"
    print(require_approval("test_action", "some details"))
    
    os.environ["_MOCK_APPROVAL_INPUT"] = "deny"
    print(require_approval("test_action", "some details"))

    os.environ["_MOCK_APPROVAL_INPUT"] = "TIMEOUT"
    print(require_approval("test_action", "some details"))
