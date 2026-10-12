"""
main.py — Direct launcher for the Ultron Rich Interactive CLI.

Usage:
    python main.py
"""
import sys
from pathlib import Path

# Ensure src/ is on sys.path for direct repository checkouts
_src_dir = Path(__file__).resolve().parent / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from ultron.cli.main import main  # noqa: E402

if __name__ == "__main__":
    main()
