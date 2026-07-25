"""
Replaces the old resolve_replace.py approach.

Free DaVinci Resolve blocks ALL external scripting connections -- not
just ReplaceClip, every Media Pool call requires it. So this module
does NOT run from gui_app.py (external process). Instead it's called
from entry_script.py, which already runs inside Resolve's own
interpreter and therefore never needs an external connection.

Flow: every time FPS Changer is launched from Workspace -> Scripts,
BEFORE rendering the newly selected clip, we check for any previous
sessions sitting in 'converted' state (finished by the GUI but not
yet pulled into Resolve) and import each one into a dedicated "FPS"
bin in the Media Pool.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from main.session import Session


def _find_or_create_bin(media_pool, root_folder, bin_name: str):
    for sub in root_folder.GetSubFolderList():
        if sub.GetName() == bin_name:
            return sub
    return media_pool.AddSubFolder(root_folder, bin_name)


def import_finished_conversions(resolve, log=print):
    """
    Scans _session/ for sessions with status == CONVERTED, imports each
    one's out_path into the "FPS" bin, and marks it IMPORTED.

    Failures on one session are logged and skipped -- they don't block
    processing of other pending sessions, and don't block the render
    step that runs right after this in entry_script.py.
    """
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        return  # nothing to do if no project is open

    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()

    fps_bin = None  # created lazily, only if there's actually something to import

    for session_path in sorted(config.SESSION_DIR.glob("*.json")):
        try:
            session = Session.load_from_path(str(session_path))
        except Exception as e:
            log(f"[FPS Changer] Skipping unreadable session {session_path.name}: {e}")
            continue

        if session.status != config.Status.CONVERTED:
            continue

        if not session.out_path.exists():
            session.mark_error(f"Converted file missing at import time: {session.out_path}")
            continue

        # Only belongs to THIS project -- skip sessions from other projects
        if session.data.get("project_name") != project.GetName():
            continue

        try:
            if fps_bin is None:
                fps_bin = _find_or_create_bin(media_pool, root_folder, config.FPS_BIN_NAME)

            previous_folder = media_pool.GetCurrentFolder()
            media_pool.SetCurrentFolder(fps_bin)
            imported = media_pool.ImportMedia([str(session.out_path)])
            media_pool.SetCurrentFolder(previous_folder)  # restore user's active bin

            if not imported:
                session.mark_error("ImportMedia() returned no items.")
                continue

            session.set_status(config.Status.IMPORTED)
            log(f"[FPS Changer] Imported {session.out_path.name} into '{config.FPS_BIN_NAME}' bin.")

        except Exception as e:
            session.mark_error(f"Import failed: {e}")
            log(f"[FPS Changer] Failed to import {session_path.name}: {e}")