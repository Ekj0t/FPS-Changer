"""
FPS conversion logic using ffmpeg.

Replicates Resolve's stop-motion/time-freeze effect using the double
fps-filter trick:

    -vf "fps=<target_fps>,fps=<project_fps>"

First pass decimates down to the target look-rate (drops frames to hit
that rate), second pass duplicates frames back up to the project's
timeline fps. Net result: same clip duration, same container fps as the
rest of the timeline, but visually "stepped" at the chosen fps -- exactly
the stutter effect, without the manual math or Resolve's retime quirks.

Audio is passed through untouched (-c:a copy) since duration doesn't
change -- only which video frames are shown, and how long each is held.
"""

import subprocess
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


class ConversionError(Exception):
    pass


def build_command(in_path: Path, out_path: Path,
                   target_fps: float, project_fps: float) -> list:
    return [
        config.FFMPEG_PATH,
        "-y",                              # overwrite out_path if it exists
        "-i", str(in_path),
        "-vf", f"fps={target_fps},fps={project_fps}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(out_path),
    ]


def run_conversion(in_path: Path, out_path: Path,
                    target_fps: float, project_fps: float) -> None:
    """
    Runs ffmpeg synchronously. Raises ConversionError with ffmpeg's own
    stderr output on failure, since that's almost always more useful than
    a generic message for diagnosing codec/filter issues.

    Intended to be called from a background thread in the GUI, not the
    main Qt thread, since this blocks until ffmpeg finishes.
    """
    if not in_path.exists():
        raise ConversionError(f"Input file not found: {in_path}")

    if target_fps <= 0:
        raise ConversionError(f"Target fps must be positive, got {target_fps}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_command(in_path, out_path, target_fps, project_fps)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # ffmpeg's real error is in stderr, last ~20 lines is usually enough
        tail = "\n".join(result.stderr.strip().splitlines()[-20:])
        raise ConversionError(f"ffmpeg failed (exit {result.returncode}):\n{tail}")

    if not out_path.exists():
        raise ConversionError(
            "ffmpeg reported success but output file was not created."
        )