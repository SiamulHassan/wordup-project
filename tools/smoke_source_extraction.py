"""Run the real GUI extraction worker against one screenshot and report completion."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.controller import AppController
from app.gui import MainWindow


def main() -> int:
    app = QApplication([])
    controller = AppController()
    controller.resumable_session = lambda: None  # avoid an unrelated modal in this smoke test
    window = MainWindow(controller)
    window._add_image_paths([Path(sys.argv[1])])
    window.analyze()
    elapsed_ms = 0

    def check() -> None:
        nonlocal elapsed_ms
        elapsed_ms += 100
        if window.extract_thread is None:
            print(
                f"EXTRACTION_OK words={len(window.model.words)} "
                f"purple={window.stats.purple_tiles} cyan={window.stats.cyan_tiles}"
            )
            app.quit()
            return
        if elapsed_ms >= 120_000:
            print("EXTRACTION_TIMEOUT")
            app.exit(1)

    timer = QTimer()
    timer.timeout.connect(check)
    timer.start(100)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
