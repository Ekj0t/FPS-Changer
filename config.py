"""
Central configuration for FPS Changer.
Every other file imports paths/constants from here — nothing hardcoded elsewhere.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────
# Project root — everything else derives from this
# ─────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

MAIN_DIR      = PROJECT_ROOT / "main"
STAGING_DIR   = PROJECT_ROOT / "staging"
ARCHIVE_DIR   = PROJECT_ROOT / "archive"
SESSION_DIR   = PROJECT_ROOT / "_session"
LOGS_DIR      = PROJECT_ROOT / "logs"
VENV_DIR      = PROJECT_ROOT / "venv"

# Python executable inside the project's venv (used by entry_script.py
# to launch gui_app.py as a subprocess with the right interpreter)
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
VENV_PYTHONW = VENV_DIR / "Scripts" / "pythonw.exe"

# Ensure runtime folders exist (safe to call every run)
for _dir in (STAGING_DIR, ARCHIVE_DIR, SESSION_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# ffmpeg
# ─────────────────────────────────────────────
FFMPEG_PATH = "ffmpeg"   # confirmed on PATH, so no full path needed

# ─────────────────────────────────────────────
# DaVinci Resolve scripting API — env vars required to import
# DaVinciResolveScript from an external (non-Resolve-launched) process.
# Windows paths for Resolve 20.3.
# ─────────────────────────────────────────────
RESOLVE_SCRIPT_API = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
RESOLVE_SCRIPT_LIB = r"E:\Programs\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
RESOLVE_MODULES_PATH = str(Path(RESOLVE_SCRIPT_API) / "Modules")

def setup_resolve_env():
    """
    Call this at the top of any script (entry_script.py, gui_app.py, etc.)
    BEFORE importing DaVinciResolveScript, so the import can find the API.
    """
    os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
    os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    if RESOLVE_MODULES_PATH not in existing_pythonpath:
        os.environ["PYTHONPATH"] = (
            f"{existing_pythonpath};{RESOLVE_MODULES_PATH}"
            if existing_pythonpath else RESOLVE_MODULES_PATH
        )
    # Also add directly to sys.path for the current process,
    # since PYTHONPATH changes only affect NEW subprocesses, not this one.
    import sys
    if RESOLVE_MODULES_PATH not in sys.path:
        sys.path.append(RESOLVE_MODULES_PATH)


# ─────────────────────────────────────────────
# Session / naming
# ─────────────────────────────────────────────
def session_file(run_id: str) -> Path:
    return SESSION_DIR / f"{run_id}.json"

def in_clip_path(clip_name: str, run_id: str) -> Path:
    return STAGING_DIR / f"{clip_name}__{run_id}_in.mp4"

def out_clip_path(clip_name: str, run_id: str) -> Path:
    return STAGING_DIR / f"{clip_name}__{run_id}_out.mp4"

# ─────────────────────────────────────────────
# fps options offered in the GUI
# ─────────────────────────────────────────────
DEFAULT_FPS_OPTIONS = [1, 2, 4, 6, 8, 10, 12, 15, 24]

# Session states — simple state machine, see session.py
class Status:
    RENDERING   = "rendering"
    RENDERED    = "rendered"
    CONVERTING  = "converting"
    CONVERTED   = "converted"
    REPLACING   = "replacing"
    DONE        = "done"
    ERROR       = "error"