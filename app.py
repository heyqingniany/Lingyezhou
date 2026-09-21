from __future__ import annotations

import sys
import multiprocessing
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from lingyezhou.paths import initialize_working_directory

from lingyezhou.logging_config import configure_logging
from lingyezhou.ui.main_window import MainWindow


def main() -> int:
    multiprocessing.freeze_support()
    initialize_working_directory()
    if sys.stdout is None or sys.stderr is None:
        Path("logs").mkdir(exist_ok=True)
        stream = open("logs/runtime-console.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Lingyezhou.Desktop")
    configure_logging()
    app = QApplication(sys.argv)
    application_font = app.font()
    if application_font.pointSize() <= 0:
        application_font.setPointSize(10)
    application_font.setFamilies(["Microsoft YaHei UI", "Segoe UI"])
    app.setFont(application_font)
    app.setApplicationName("聆页舟")
    app.setOrganizationName("聆页舟")
    window = MainWindow()
    if "--self-test-report" in sys.argv:
        from lingyezhou.diagnostics import run
        return run(window, sys.argv)
    window.show()
    QTimer.singleShot(0, window.offer_startup_choice)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
