import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    parent_dir = MODULE_DIR.parent
    BUNDLE_DIR = parent_dir if (parent_dir / "frontend").exists() else MODULE_DIR


def _default_home() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "insta-helper"
    return Path.home() / ".insta-helper"


APP_HOME = Path(os.getenv("INSTA_HELPER_HOME", _default_home())).resolve()
DATA_DIR = Path(os.getenv("INSTA_HELPER_DATA_DIR", APP_HOME / "data")).resolve()
UPLOAD_DIR = Path(os.getenv("INSTA_HELPER_UPLOAD_DIR", APP_HOME / "uploads")).resolve()

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_frontend_dir() -> Path | None:
    candidates = [
        BUNDLE_DIR / "frontend",
        MODULE_DIR.parent / "frontend",
        MODULE_DIR / "frontend",
    ]
    for candidate in candidates:
        if candidate.exists() and (candidate / "index.html").exists():
            return candidate
    return None


FRONTEND_DIR = get_frontend_dir()


@lru_cache(maxsize=1)
def get_ffmpeg_executable() -> str:
    env_value = os.getenv("INSTA_HELPER_FFMPEG")
    candidates = [
        Path(env_value) if env_value else None,
        BUNDLE_DIR / "bin" / "ffmpeg.exe",
        BUNDLE_DIR / "bin" / "ffmpeg",
        MODULE_DIR / "bin" / "ffmpeg.exe",
        MODULE_DIR / "bin" / "ffmpeg",
    ]

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)

    for command_name in ["ffmpeg.exe", "ffmpeg"]:
        resolved = shutil.which(command_name)
        if resolved:
            return resolved

    raise RuntimeError(
        "FFmpeg executable not found. Install ffmpeg or set INSTA_HELPER_FFMPEG."
    )


@lru_cache(maxsize=1)
def get_font_path() -> str | None:
    env_value = os.getenv("INSTA_HELPER_FONT")
    candidates = [
        Path(env_value) if env_value else None,
        BUNDLE_DIR / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
        MODULE_DIR / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ]

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)

    return None