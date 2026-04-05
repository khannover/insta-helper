import os
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _default_home() -> Path:
    base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "insta-helper"


def main() -> None:
    root = _bundle_root()
    backend_dir = root / "backend"
    if not backend_dir.exists():
        backend_dir = root

    sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("INSTA_HELPER_HOME", str(_default_home()))

    from main import app  # Imported after sys.path adjustment.

    host = os.getenv("INSTA_HELPER_HOST", "127.0.0.1")
    port = int(os.getenv("INSTA_HELPER_PORT", "8000"))

    threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()