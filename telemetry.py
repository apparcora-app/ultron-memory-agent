# ---------------------------------------------------------------------------
# BACKWARD-COMPATIBILITY SHIM — do not edit
# Relocated to: telemetry/telemetry.py
#
# All existing usage continues to work unchanged:
#   from telemetry import X   -> re-exported below
#   python telemetry.py                                                              -> forwarded below
# ---------------------------------------------------------------------------
import os as _os, sys as _sys

# ── When imported as a module: re-export everything from the real location ──
if __name__ != "__main__":
    from telemetry.telemetry import *       # noqa: F401 F403 E402
    try:
        from telemetry.telemetry import __all__  # noqa: F401 E402
    except ImportError:
        pass

# ── When run as a script: execute the real file directly (no sys.modules clash) ──
else:
    import runpy as _runpy
    _rp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), r"telemetry/telemetry.py")
    _runpy.run_path(_rp, run_name="__main__")
