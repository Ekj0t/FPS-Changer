"""
Step 1-2 of the FPS Changer workflow.

Runs INSIDE Resolve's own Python interpreter (called from entry_script.py,
which is launched via Workspace -> Scripts -> FPS Changer).

Responsibilities:
    - Connect to the running Resolve instance
    - Find the clip under the playhead on the current timeline
      (this is the documented, reliable definition of "selected clip" --
       see note in README about parking the playhead vs. click-selecting)
    - Render that clip's in/out range to staging/ as "<clipname>__<runid>_in.mp4"
    - Return a Session object once the render is confirmed complete
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from main.session import Session


class RenderError(Exception):
    pass


# ── connecting to Resolve ──────────────────────────────────────────

def get_resolve():
    """
    Scripts launched via Workspace -> Scripts already have a `resolve`
    global injected by Resolve itself. We check for that first (fast path,
    no extra imports). Falls back to explicit connection for robustness
    if ever run in a context where that global isn't present.
    """
    g = sys.modules["__main__"].__dict__
    if "resolve" in g and g["resolve"] is not None:
        return g["resolve"]

    config.setup_resolve_env()
    import DaVinciResolveScript as dvr
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise RenderError(
            "Could not connect to DaVinci Resolve. Is Resolve running?"
        )
    return resolve


# ── finding the clip ───────────────────────────────────────────────

def get_current_project(resolve):
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise RenderError("No project is currently open in Resolve.")
    return project


def get_playhead_timeline_item(project):
    """
    Returns the TimelineItem sitting under the playhead on the current
    timeline's active video track.
    """
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise RenderError("No timeline is currently open.")

    item = timeline.GetCurrentVideoItem()
    if item is None:
        raise RenderError(
            "No clip found under the playhead. Park the playhead on top "
            "of the clip you want to convert, then run the script again."
        )
    return timeline, item


# ── rendering ───────────────────────────────────────────────────────

def start_render(project, timeline, item, session: Session):
    """
    Configures a render job scoped to exactly this clip's in/out range
    on the timeline, and starts it.
    """
    start_frame = item.GetStart()
    end_frame = item.GetEnd()

    # Explicit format/codec so output is predictable regardless of the
    # project's current deliver-page settings.
    ok = project.SetCurrentRenderFormatAndCodec("mp4", "H264")
    if not ok:
        raise RenderError("Failed to set render format to mp4/H264.")

    render_settings = {
        "SelectAllFrames": False,
        "MarkIn": start_frame,
        "MarkOut": end_frame,
        "TargetDir": str(config.STAGING_DIR),
        "CustomName": session.in_path.stem,   # filename without extension
        "ExportVideo": True,
        "ExportAudio": True,
    }

    ok = project.SetRenderSettings(render_settings)
    if not ok:
        raise RenderError("Failed to apply render settings.")

    job_id = project.AddRenderJob()
    if not job_id:
        raise RenderError("Failed to add render job.")

    started = project.StartRendering(job_id)
    if not started:
        raise RenderError("Failed to start rendering.")

    return job_id


def wait_for_render(project, job_id, poll_interval=0.5, timeout=600):
    """
    Blocks until rendering finishes. Polls project.IsRenderingInProgress().
    timeout is a safety net (seconds) so a stuck render doesn't hang forever.
    """
    elapsed = 0.0
    while project.IsRenderingInProgress():
        time.sleep(poll_interval)
        elapsed += poll_interval
        if elapsed > timeout:
            raise RenderError(
                f"Render did not finish within {timeout}s timeout."
            )

    status = project.GetRenderJobStatus(job_id)
    job_state = status.get("JobStatus") if status else None
    if job_state != "Complete":
        raise RenderError(
            f"Render finished but job status was '{job_state}', expected 'Complete'."
        )


# ── orchestrator ───────────────────────────────────────────────────

def render_selected_clip() -> Session:
    """
    Full step 1-2 flow. Called by entry_script.py.
    Returns a Session object (already saved to disk with status='rendered').
    """
    resolve = get_resolve()
    project = get_current_project(resolve)
    timeline, item = get_playhead_timeline_item(project)

    media_pool_item = item.GetMediaPoolItem()
    if media_pool_item is None:
        raise RenderError(
            "Selected timeline item has no linked Media Pool item "
            "(is it a generator, title, or adjustment clip?)."
        )

    clip_name = media_pool_item.GetClipProperty("Clip Name") or item.GetName()
    mp_item_unique_id = media_pool_item.GetUniqueId()
    timeline_fps = float(project.GetSetting("timelineFrameRate"))

    session = Session.create(
        clip_name=clip_name,
        mp_item_unique_id=mp_item_unique_id,
        project_name=project.GetName(),
        timeline_fps=timeline_fps,
    )

    try:
        job_id = start_render(project, timeline, item, session)
        wait_for_render(project, job_id)
    except RenderError as e:
        session.mark_error(str(e))
        raise

    if not session.in_path.exists():
        session.mark_error(
            f"Render reported complete but output file not found: {session.in_path}"
        )
        raise RenderError(session.data["error_msg"])

    session.set_status(config.Status.RENDERED)
    return session