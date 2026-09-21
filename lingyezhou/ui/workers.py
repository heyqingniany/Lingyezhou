from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot


class TaskWorker(QObject):
    finished = Signal(object)
    failed = Signal(str, str)
    progress = Signal(str)

    def __init__(self, task: Callable[[Callable[[str], None]], Any]) -> None:
        super().__init__()
        self.task = task

    @Slot()
    def run(self) -> None:
        try:
            result = self.task(self.progress.emit)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())

