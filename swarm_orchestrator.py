# ---------------------------------------------------------------------------
# BACKWARD-COMPATIBILITY SHIM — do not edit
# Relocated to: pipelines/swarm_orchestrator.py
#
# All existing usage continues to work unchanged:
#   from swarm_orchestrator import X   -> re-exported below
#   python swarm_orchestrator.py                                                              -> forwarded below
# ---------------------------------------------------------------------------
import os as _os, sys as _sys

# ── When imported as a module: re-export everything from the real location ──
if __name__ != "__main__":
    from pipelines.swarm_orchestrator import *       # noqa: F401 F403 E402
    try:
        from pipelines.swarm_orchestrator import __all__  # noqa: F401 E402
    except ImportError:
        pass

# ── When run as a script: execute the real file directly (no sys.modules clash) ──
else:
    import runpy as _runpy
    _rp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), r"pipelines/swarm_orchestrator.py")
    _runpy.run_path(_rp, run_name="__main__")
