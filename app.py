"""
app.py — Direct launcher for the Ultron Cybernetic Web Dashboard.

Usage:
    python app.py
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure root .env is loaded
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

# Ensure src/ is on sys.path for direct repository checkouts
_src_dir = Path(__file__).resolve().parent / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

print("\n[Ultron] Initializing Cybernetic Web Server... (loading frameworks, please wait ~8s)\n", flush=True)

from ultron.cli.web import app, main  # noqa: E402

__all__ = ["app", "main"]

if __name__ == "__main__":
    main()
