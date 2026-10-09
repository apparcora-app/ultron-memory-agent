# ---------------------------------------------------------------------------
# BACKWARD-COMPATIBILITY SHIM — do not edit
# Relocated to: infrastructure/desktop_action_verifier.py
#
# All existing usage continues to work unchanged:
#   from desktop_action_verifier import X   -> re-exported below
#   python desktop_action_verifier.py                                                              -> forwarded below
# ---------------------------------------------------------------------------
import os as _os, sys as _sys

# ── When imported as a module: re-export everything from the real location ──
if __name__ != "__main__":
    from infrastructure.desktop_action_verifier import *       # noqa: F401 F403 E402
    try:
        from infrastructure.desktop_action_verifier import __all__  # noqa: F401 E402
    except ImportError:
        pass

# ── When run as a script: execute the real file directly (no sys.modules clash) ──
else:
    import runpy as _runpy
    _rp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), r"infrastructure/desktop_action_verifier.py")
    _runpy.run_path(_rp, run_name="__main__")
