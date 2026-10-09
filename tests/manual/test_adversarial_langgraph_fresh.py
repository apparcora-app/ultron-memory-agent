import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import sys
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.verify_langgraph_handoff import main
import pipelines.langgraph_pipeline as lgp

def mock_get_llm_callable(*args, **kwargs):
    def bad_caller(*a, **kw):
        raise ConnectionResetError("Connection reset by peer during SSL handshake")
    return bad_caller

print("--- ADVERSARIAL TEST: INDUCING ConnectionResetError ---")
with patch.object(lgp, '_get_default_llm_caller', new=mock_get_llm_callable):
    try:
        main()
    except AssertionError as e:
        print(f"\n[CONFIRMED STILL FIXED] Test failed as expected on structural error: {e}")
    except Exception as e:
        print(f"\n[CONFIRMED STILL FIXED] Test failed as expected propagating error: {e}")
