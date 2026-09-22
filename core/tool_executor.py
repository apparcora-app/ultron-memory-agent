"""
tool_executor.py — Convenience bridge exporting direct standalone tool helpers, Active Window Guard, and ToolExecutor.
"""
import os
import sys

# ── 1. Safety Failsafe Configuration ──────────────────────────────────────────
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to any corner to instantly abort GUI operations
except ImportError:
    pass

# ── 2. Native Win32 Active Window Guard ────────────────────────────────────────
try:
    import win32gui
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

def get_active_window_title() -> str:
    """Retrieve the text title of the currently focused foreground window via Win32 API."""
    if not _HAS_WIN32:
        return ""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            return win32gui.GetWindowText(hwnd).strip()
    except Exception:
        pass
    return ""

def is_active_window(window_title: str) -> bool:
    """Verify whether the current active foreground window matches the expected title."""
    active_title = get_active_window_title()
    if not active_title:
        return False
    return window_title.lower() in active_title.lower()

# ── 3. Tool Executor & Standalone Tool Exports ────────────────────────────────
from tool_definitions import ToolExecutor, ULTRON_TOOLS

# Singleton default executor instance
_default_executor = ToolExecutor()

def execute_tool(tool_name: str, arguments: dict | None = None) -> dict:
    """Execute any registered Ultron tool by name."""
    return _default_executor.execute(tool_name, arguments or {})

def control_desktop_gui(action: str, window_title: str = "", keys: str = "", element_name: str = "", x: int | None = None, y: int | None = None) -> dict:
    """Direct helper for desktop GUI automation with Active Window Guard and safety validation."""
    inp = {
        "action": action,
        "window_title": window_title,
        "keys": keys,
        "element_name": element_name,
    }
    if x is not None:
        inp["x"] = x
    if y is not None:
        inp["y"] = y
    return _default_executor.execute("control_desktop_gui", inp)

def open_application(app_name: str, arguments: str = "") -> dict:
    """Direct helper to launch any desktop app or shortcut."""
    return _default_executor.execute("open_application", {"app_name": app_name, "arguments": arguments})

def close_application(app_name: str) -> dict:
    """Direct helper to gracefully close or terminate any desktop application or window."""
    return _default_executor.execute("control_desktop_gui", {"action": "close_window", "window_title": app_name})

def desktop_create_and_show_note(content: str, filename: str = "ultron_note.txt", open_in_foreground: bool = True) -> dict:
    """Atomic Compound Tool: Writes text to disk and pops it up in Notepad on screen in 1 step."""
    return _default_executor.execute("desktop_create_and_show_note", {
        "content": content,
        "filename": filename,
        "open_in_foreground": open_in_foreground,
    })

def fetch_web_page(url: str) -> dict:
    """Direct helper to fetch web pages with browser TLS impersonation."""
    return _default_executor.execute("fetch_web_page", {"url": url})
