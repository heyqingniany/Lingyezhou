from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from interviewlens.logging_config import configure_logging
from interviewlens.ui.main_window import MainWindow


def main() -> int:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("InterviewLens.Desktop")
    configure_logging()
    app = QApplication(sys.argv)
    application_font = app.font()
    if application_font.pointSize() <= 0:
        application_font.setPointSize(10)
    application_font.setFamilies(["Microsoft YaHei UI", "Segoe UI"])
    app.setFont(application_font)
    app.setApplicationName("InterviewLens")
    app.setOrganizationName("InterviewLens")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
