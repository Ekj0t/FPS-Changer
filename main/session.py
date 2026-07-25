"""
Session state management for a single FPS Changer run.

A "session" tracks one clip's journey through:
rendering -> rendered -> converting -> converted -> replacing -> done
(or -> error at any point)

Stored as a small JSON file in _session/<run_id>.json so that
entry_script.py (running inside Resolve) and gui_app.py (external
subprocess) can hand off state to each other reliably.
"""

import json
import time
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


class Session:
    def __init__(self, run_id: str, data: dict):
        self.run_id = run_id
        self.data = data

    # ── creation ──────────────────────────────────────────────
    @classmethod
    def create(cls, clip_name: str, mp_item_unique_id: str,
               project_name: str, timeline_fps: float) -> "Session":
        """
        Called by entry_script.py to start a new run.
        Generates a run_id, builds in/out paths, writes initial state.
        """
        run_id = time.strftime("%H%M%S") + "_" + uuid.uuid4().hex[:6]
        clip_name = _sanitize(clip_name)

        data = {
            "run_id": run_id,
            "clip_name": clip_name,
            "mp_item_unique_id": mp_item_unique_id,
            "project_name": project_name,
            "timeline_fps": timeline_fps,
            "in_path": str(config.in_clip_path(clip_name, run_id)),
            "out_path": str(config.out_clip_path(clip_name, run_id)),
            "status": config.Status.RENDERING,
            "error_msg": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        session = cls(run_id, data)
        session.save()
        return session

    # ── loading existing session ─────────────────────────────
    @classmethod
    def load(cls, run_id: str) -> "Session":
        path = config.session_file(run_id)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(run_id, data)

    @classmethod
    def load_from_path(cls, session_path: str) -> "Session":
        """Used by gui_app.py, which receives the full path as argv[1]."""
        path = Path(session_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data["run_id"], data)

    # ── saving / updating ─────────────────────────────────────
    def save(self):
        self.data["updated_at"] = time.time()
        path = config.session_file(self.run_id)
        # write to temp file then rename -> avoids partial/corrupt reads
        # if the other process polls at the wrong instant
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        tmp_path.replace(path)

    def set_status(self, status: str, error_msg: str = None):
        self.data["status"] = status
        if error_msg is not None:
            self.data["error_msg"] = error_msg
        self.save()

    def mark_error(self, message: str):
        self.set_status(config.Status.ERROR, error_msg=message)

    # ── convenience accessors ────────────────────────────────
    @property
    def in_path(self) -> Path:
        return Path(self.data["in_path"])

    @property
    def out_path(self) -> Path:
        return Path(self.data["out_path"])

    @property
    def status(self) -> str:
        return self.data["status"]

    @property
    def mp_item_unique_id(self) -> str:
        return self.data["mp_item_unique_id"]

    @property
    def timeline_fps(self) -> float:
        return self.data["timeline_fps"]

    def __repr__(self):
        return f"<Session {self.run_id} status={self.status}>"


def _sanitize(name: str) -> str:
    """Strip characters that are unsafe in filenames."""
    keep = "-_.() "
    cleaned = "".join(c if c.isalnum() or c in keep else "_" for c in name)
    return cleaned.strip().replace(" ", "_")