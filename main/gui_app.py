"""
FPS Changer GUI - Pass 1.

Launched as a detached subprocess by entry_script.py, with the session
JSON file path passed as argv[1].

Pass 1 scope:
    - Load session, show a preview of the rendered in-clip
    - Let the user pick a target fps (preset dropdown or custom value)
    - Run the ffmpeg conversion (double fps-filter) on confirm
    - Update session status through converting -> converted / error

Pass 2 (separate step) will add: reconnecting to Resolve and calling
ReplaceClip() automatically once conversion succeeds.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(r"D:\FPS Changer")
sys.path.insert(0, str(PROJECT_ROOT))

import config
from main.session import Session
from main.ffmpeg_convert import run_conversion, ConversionError

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDoubleSpinBox, QPushButton, QProgressBar, QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QUrl, QThread, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


CUSTOM_LABEL = "Custom..."


class ConvertWorker(QThread):
    """Runs ffmpeg on a background thread so the GUI never freezes."""
    finished_ok = Signal()
    finished_error = Signal(str)

    def __init__(self, in_path: Path, out_path: Path,
                 target_fps: float, project_fps: float):
        super().__init__()
        self.in_path = in_path
        self.out_path = out_path
        self.target_fps = target_fps
        self.project_fps = project_fps

    def run(self):
        try:
            run_conversion(self.in_path, self.out_path,
                            self.target_fps, self.project_fps)
            self.finished_ok.emit()
        except ConversionError as e:
            self.finished_error.emit(str(e))
        except Exception as e:
            self.finished_error.emit(f"Unexpected error: {e}")


class FpsChangerWindow(QWidget):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.worker = None

        self.setWindowTitle(f"FPS Changer - {session.data['clip_name']}")
        self.resize(720, 560)

        self._build_ui()
        self._load_preview()

    # ── UI construction ─────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # -- video preview --
        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.video_widget, stretch=1)

        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video_widget)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.5)

        # -- playback controls --
        playback_row = QHBoxLayout()
        self.play_btn = QPushButton("Play / Pause")
        self.play_btn.clicked.connect(self._toggle_playback)
        playback_row.addWidget(self.play_btn)
        playback_row.addStretch()
        layout.addLayout(playback_row)

        # -- clip info --
        info_label = QLabel(
            f"Project fps: {self.session.timeline_fps}    |    "
            f"Source: {self.session.in_path.name}"
        )
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)

        # -- fps picker --
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("Target FPS:"))

        self.fps_combo = QComboBox()
        for val in config.DEFAULT_FPS_OPTIONS:
            self.fps_combo.addItem(str(val))
        self.fps_combo.addItem(CUSTOM_LABEL)
        self.fps_combo.currentTextChanged.connect(self._on_fps_combo_changed)
        fps_row.addWidget(self.fps_combo)

        self.fps_custom_spin = QDoubleSpinBox()
        self.fps_custom_spin.setRange(0.1, 240.0)
        self.fps_custom_spin.setDecimals(2)
        self.fps_custom_spin.setValue(self.session.timeline_fps / 2)
        self.fps_custom_spin.setVisible(False)
        fps_row.addWidget(self.fps_custom_spin)

        fps_row.addStretch()
        layout.addLayout(fps_row)

        # -- convert button + progress --
        self.convert_btn = QPushButton("Convert")
        self.convert_btn.clicked.connect(self._on_convert_clicked)
        layout.addWidget(self.convert_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _load_preview(self):
        self.player.setSource(QUrl.fromLocalFile(str(self.session.in_path)))
        self.player.setLoops(QMediaPlayer.Infinite)
        self.player.play()

    def _toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_fps_combo_changed(self, text: str):
        self.fps_custom_spin.setVisible(text == CUSTOM_LABEL)

    def _get_target_fps(self) -> float:
        if self.fps_combo.currentText() == CUSTOM_LABEL:
            return self.fps_custom_spin.value()
        return float(self.fps_combo.currentText())

    # ── conversion ──────────────────────────────────────────────
    def _on_convert_clicked(self):
        target_fps = self._get_target_fps()

        if target_fps > self.session.timeline_fps:
            QMessageBox.warning(
                self, "Invalid FPS",
                f"Target fps ({target_fps}) can't be higher than the "
                f"project fps ({self.session.timeline_fps})."
            )
            return

        self.convert_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.status_label.setText(f"Converting to {target_fps} fps...")

        self.session.set_status(config.Status.CONVERTING)

        self.worker = ConvertWorker(
            in_path=self.session.in_path,
            out_path=self.session.out_path,
            target_fps=target_fps,
            project_fps=self.session.timeline_fps,
        )
        self.worker.finished_ok.connect(self._on_convert_success)
        self.worker.finished_error.connect(self._on_convert_error)
        self.worker.start()

    def _on_convert_success(self):
        self.session.set_status(config.Status.CONVERTED)
        self.progress.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.status_label.setText(f"Done. Saved to: {self.session.out_path}")
        QMessageBox.information(
            self, "Conversion Complete",
            f"Converted clip saved to:\n{self.session.out_path}\n\n"
            "(Automatic replacement in Resolve isn't wired up yet -- "
            "this is Pass 1.)"
        )

    def _on_convert_error(self, message: str):
        self.session.mark_error(message)
        self.progress.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.status_label.setText("Conversion failed.")
        QMessageBox.critical(self, "Conversion Failed", message)

    def closeEvent(self, event):
        self.player.stop()
        event.accept()


def main():
    if len(sys.argv) < 2:
        print("Usage: gui_app.py <session_file_path>")
        sys.exit(1)

    session_file_path = sys.argv[1]
    session = Session.load_from_path(session_file_path)

    app = QApplication(sys.argv)
    window = FpsChangerWindow(session)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()