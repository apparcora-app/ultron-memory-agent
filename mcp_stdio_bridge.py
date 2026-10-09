# ---------------------------------------------------------------------------
# BACKWARD-COMPATIBILITY SHIM — do not edit
# Relocated to: infrastructure/mcp_stdio_bridge.py
#
# All existing usage continues to work unchanged:
#   from mcp_stdio_bridge import X   -> re-exported below
#   python mcp_stdio_bridge.py                                                              -> forwarded below
# ---------------------------------------------------------------------------
import os as _os, sys as _sys

# ── When imported as a module: re-export everything from the real location ──
if __name__ != "__main__":
    from infrastructure.mcp_stdio_bridge import *       # noqa: F401 F403 E402
    try:
        from infrastructure.mcp_stdio_bridge import __all__  # noqa: F401 E402
    except ImportError:
        pass

# ── When run as a script: execute the real file directly (no sys.modules clash) ──
else:
    import runpy as _runpy
    _rp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), r"infrastructure/mcp_stdio_bridge.py")
    _runpy.run_path(_rp, run_name="__main__")
