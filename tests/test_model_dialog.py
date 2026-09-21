import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from lingyezhou.config import AppConfig
from lingyezhou.ui.config_dialog import ConfigDialog
from lingyezhou.ui.model_dialog import ModelDialog
from lingyezhou.ui.main_window import MainWindow


class ModelDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = AppConfig(model_directory=self.temp.name, startup_choice="local")

    def wait_job(self, dialog):
        deadline = time.monotonic() + 5
        while dialog.thread and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertIsNone(dialog.thread)

    def test_opening_dialog_has_no_network_or_disk_creation(self):
        with patch("lingyezhou.asr.model_store.urlopen") as network:
            dialog = ModelDialog(self.config)
            self.assertIn("未准备好", dialog.summary.text())
            self.assertTrue(dialog.download.isEnabled())
            self.assertFalse(dialog.store.root.exists())
            network.assert_not_called()
            dialog.close()

    def test_download_requires_confirmation_and_failure_allows_retry(self):
        dialog = ModelDialog(self.config)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No), \
             patch.object(dialog.store, "prepare") as prepare:
            dialog.start_download()
            prepare.assert_not_called()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
             patch.object(dialog.store, "prepare", side_effect=OSError("网络中断")):
            dialog.start_download()
            self.wait_job(dialog)
        self.assertIn("网络中断", dialog.message.text())
        self.assertTrue(dialog.download.isEnabled())
        self.assertTrue(dialog.choose.isEnabled())
        dialog.close()

    def test_service_settings_preserve_model_preferences(self):
        dialog = ConfigDialog(self.config)
        changed = dialog.value()
        self.assertEqual(changed.model_directory, self.temp.name)
        self.assertEqual(changed.startup_choice, "local")
        self.assertEqual(changed.ai_provider, "deepseek")
        self.assertEqual(changed.base_url, "https://api.deepseek.com")
        self.assertEqual(changed.model, "deepseek-flash")
        dialog.close()

    def test_service_presets_and_cloud_fields_are_unambiguous(self):
        dialog = ConfigDialog(self.config)
        dialog.ai_provider.setCurrentIndex(dialog.ai_provider.findData("openai"))
        self.assertEqual(dialog.base_url.text(), "https://api.openai.com/v1")
        self.assertEqual(dialog.model.text(), "gpt-4o-mini")
        self.assertTrue(dialog.base_url.isReadOnly())
        dialog.ai_provider.setCurrentIndex(dialog.ai_provider.findData("custom"))
        self.assertFalse(dialog.base_url.isReadOnly())
        dialog.cloud_mode.setCurrentIndex(dialog.cloud_mode.findData("flash"))
        self.assertEqual(dialog.cloud_credentials.currentIndex(), 1)
        dialog.close()

    def test_missing_local_model_opens_manager_without_starting_task(self):
        with patch("lingyezhou.ui.main_window.AppConfig.load", return_value=self.config):
            window = MainWindow()
        window.audio_path = Path(self.temp.name) / "example.wav"
        window.model_combo.setCurrentIndex(1)
        with patch.object(window, "open_models") as manager, patch.object(window, "_run_task") as task:
            window.start_transcription()
            manager.assert_called_once()
            task.assert_not_called()
        window.close()


if __name__ == "__main__":
    unittest.main()
