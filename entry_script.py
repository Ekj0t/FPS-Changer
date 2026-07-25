"""
FPS Changer - entry point launched from Resolve's Workspace -> Scripts menu.

This file is symlinked from Resolve's Scripts/Utility folder to this real
location at D:\\FPS Changer\\entry_script.py.

Kept intentionally thin:
    1. Render the clip under the playhead (in/out range) to staging/
    2. Launch gui_app.py as a detached subprocess, passing it the session
       file path
    3. Exit immediately -- does NOT wait for the GUI, so Resolve's UI
       thread is never blocked

Runs INSIDE Resolve's own Python interpreter. No PySide6, no GUI code here.
"""

import sys
import subprocess
import traceback
from pathlib import Path

PROJECT_ROOT = Path(r"D:\FPS Changer")
sys.path.insert(0, str(PROJECT_ROOT))

import config
from main.resolve_render import render_selected_clip, RenderError


def show_error_dialog(title: str, message: str):
    """
    Resolve doesn't show a console when a script is launched from the
    Workspace -> Scripts menu (no visible stdout), so a Windows message
    box is the only reliable way to surface an error to the user here.
    """
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        # Last-resort fallback if even the message box fails
        print(f"[{title}] {message}")


def log_exception(context: str, exc: Exception):
    log_path = config.LOGS_DIR / "entry_script.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n--- {context} ---\n")
        f.write(traceback.format_exc())
        f.write("\n")


def launch_gui(session_file_path: Path):
    """
    Launches gui_app.py using the project's own venv interpreter, detached
    from Resolve's process so it keeps running after this script exits.
    GUI's stdout/stderr are redirected to a log file for debugging, since
    a detached process has no console to print to anyway.
    """
    gui_script = config.MAIN_DIR / "gui_app.py"
    log_path = config.LOGS_DIR / "gui_app.log"

    with open(log_path, "a", encoding="utf-8") as log_file:
        subprocess.Popen(
            [str(config.VENV_PYTHONW), str(gui_script), str(session_file_path)],
            stdout=log_file,
            stderr=log_file,
            close_fds=True,
        )


def main():
    try:
        session = render_selected_clip()
    except RenderError as e:
        log_exception("render_selected_clip failed", e)
        show_error_dialog("FPS Changer - Render Failed", str(e))
        return
    except Exception as e:
        log_exception("Unexpected error during render", e)
        show_error_dialog(
            "FPS Changer - Unexpected Error",
            f"Something went wrong:\n{e}\n\nSee logs/entry_script.log for details."
        )
        return

    session_file_path = config.session_file(session.run_id)

    try:
        launch_gui(session_file_path)
    except Exception as e:
        log_exception("Failed to launch GUI subprocess", e)
        show_error_dialog(
            "FPS Changer - GUI Launch Failed",
            f"Render succeeded, but the GUI could not be launched:\n{e}\n\n"
            f"Rendered file: {session.in_path}"
        )
        return


if __name__ == "__main__":
    main()