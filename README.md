# FPS Changer for DaVinci Resolve

A DaVinci Resolve scripting tool that automates the "stop-motion" / stepped-frame-rate
effect on a clip using `ffmpeg`, without the confusing math or unreliable behavior of
Resolve's built-in retime tool.

Instead of manually calculating a change speed / freeze-frame combination inside Resolve,
this tool lets you pick a target FPS directly, handles the conversion externally with
`ffmpeg`, and pulls the finished clip back into your project automatically.

---

## Why this exists

Resolve's inbuilt stop-motion effect works by controlling time-freeze/hold duration,
which means getting a specific "look" FPS requires manual frame-hold math, and it can
behave inconsistently on certain clips/codecs.

This tool replicates the effect with a much more predictable method: an `ffmpeg` double
`fps` filter chain — decimate down to your target FPS, then duplicate back up to your
project's FPS. Same duration, same container FPS as your timeline, no math required.

---

## How it works

1. **Select a clip** — park the playhead on top of the clip in your Resolve timeline.
2. **Run the script** — Workspace → Scripts → **FPS Changer**.
3. The script renders that clip's exact in/out range to a staging folder.
4. A GUI opens automatically, showing a preview of the rendered clip and an FPS picker
   (common presets, or a custom value).
5. Pick your FPS and hit **Convert** — `ffmpeg` processes the clip in the background
   (GUI stays fully responsive).
6. The converted clip is saved to the staging folder.
7. **Run the script again** (on this or any other clip, or with the playhead on empty
   timeline space) — the tool automatically imports any finished conversions into a
   dedicated **FPS** bin in your Media Pool.

---

## Why two steps instead of one automatic hand-off

DaVinci Resolve's **free edition does not support external scripting connections** —
only Resolve Studio does. Since the GUI runs as a separate process (needed to keep
Resolve's UI from freezing during conversion), it cannot talk back to Resolve directly
on the free edition.

The workaround: the GUI never touches the Resolve API. Instead, every time the script is
launched from Resolve's own Scripts menu (which *does* have a live connection), it first
checks for any finished-but-not-yet-imported conversions and pulls them into the Media
Pool automatically — before doing anything else.

This means:
- Running the script with a clip under the playhead → renders + opens the GUI, **and**
  imports any pending finished conversions first.
- Running the script with the playhead over empty space → **only** checks for and
  imports pending conversions, no render happens.

If you're on **Resolve Studio**, this two-step process still works exactly the same way
— it was simply designed around the lowest common denominator.

---

## Features

- Automatic in/out range rendering straight from the timeline selection (playhead-based)
- Simple FPS picker: dropdown of common presets + custom value entry
- Video preview while choosing FPS
- Background `ffmpeg` conversion — GUI never freezes
- Automatic import into a dedicated **FPS** bin in the Media Pool
- Session-based architecture — every run is tracked in a small JSON state file, so
  nothing is lost if a step fails partway through
- Automatic cleanup of intermediate render files after conversion
- Robust error handling with clear on-screen messages (no silent failures)

---

## Requirements

- **DaVinci Resolve** (free or Studio) — developed and tested on 20.3
- **Python 3.9+** (a dedicated virtual environment is used for the GUI — see Setup)
- **PySide6** (installed into the project's own venv)
- **ffmpeg**, available on your system PATH

---

## Folder Structure

```
FPS Changer/
├── entry_script.py      # Launcher, symlinked into Resolve's Scripts menu
├── config.py             # All paths, constants, Resolve env-var setup
├── main/
│   ├── resolve_render.py   # Finds clip under playhead, renders in/out range
│   ├── resolve_import.py   # Imports finished conversions into the FPS bin
│   ├── gui_app.py           # FPS picker GUI (runs as external subprocess)
│   ├── ffmpeg_convert.py    # The actual ffmpeg conversion logic
│   └── session.py           # Shared session-state (JSON) read/write helpers
├── staging/               # Rendered in-clips and converted out-clips
├── _session/               # JSON state files for in-progress runs
├── archive/                # JSON state files for completed, imported runs
├── logs/                   # Error logs (entry_script.log, gui_app.log)
└── venv/                   # Isolated Python environment for the GUI
```

---

## Setup

1. Clone/copy this project folder to your machine.
2. Create the virtual environment and install dependencies:
   ```
   python -m venv venv
   venv\Scripts\pip.exe install -r requirements.txt
   ```
3. In `config.py`, confirm/update:
   - `RESOLVE_SCRIPT_API` and `RESOLVE_SCRIPT_LIB` match your Resolve install location
   - `FFMPEG_PATH` (default `"ffmpeg"`, assumes it's on your system PATH)
4. Symlink `entry_script.py` into Resolve's Scripts folder so it shows up under
   Workspace → Scripts:
   ```
   mklink "%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\FPS Changer.py" "<path-to-project>\entry_script.py"
   ```
5. Restart Resolve (or reload scripts) — **FPS Changer** should now appear under
   Workspace → Scripts.

---

## Usage

1. Park the playhead over the clip you want to convert.
2. Workspace → Scripts → **FPS Changer**.
3. Wait for the render to finish — the GUI opens automatically.
4. Pick a target FPS (dropdown or custom value) and click **Convert**.
5. Once conversion finishes, run the script again (playhead can be anywhere, including
   empty space) to import the converted clip into the **FPS** bin.
6. Drag the clip from the **FPS** bin onto your timeline.

---

## Known Issues / Limitations

- **No fully automatic clip replacement on the timeline.** Because of the free-edition
  scripting restriction described above, the converted clip is imported into a bin —
  you still need to manually drag it onto the timeline. On Resolve Studio, a direct
  `ReplaceClip()` hand-off is technically possible but is not currently implemented.
- **Intermediate `_in.mp4` files in `staging/` are not currently being deleted.**
  Cleanup logic is implemented to remove the intermediate render immediately after a
  successful `ffmpeg` conversion, but it is not reliably firing in current testing —
  these files may accumulate over time and should be deleted manually for now. The
  final converted `_out.mp4` files are **not** affected by this and should never be
  deleted manually while they're in use on a timeline, since Resolve links to them
  directly by file path.
- **"Selected clip" means "clip under the playhead"**, not click-selection in the
  timeline UI — Resolve's scripting API doesn't expose reliable click-selection across
  versions, so playhead position is used instead.
- Tested primarily on Windows; paths and subprocess handling are Windows-specific
  (`pythonw.exe`, `mklink`, etc.). Adapting for macOS/Linux would require path and
  process-launch changes.

---

## License

*(Add your preferred license here.)*
