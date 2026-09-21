import hashlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from lingyezhou.asr import model_store as models
from lingyezhou.asr.sensevoice import SenseVoiceBackend
from lingyezhou.asr.paraformer import ParaformerBackend


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


class ModelStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = models.ModelStore(self.temp.name)
        self.content = b"model-data-for-verification"
        self.item = {"name": "model.pt", "size": len(self.content), "sha256": hashlib.sha256(self.content).hexdigest()}
        catalog = {key: models.Component("tests/" + key, key, ("model.pt",), len(self.content)) for key in models.COMPONENTS}
        patcher = patch.object(models, "COMPONENTS", catalog)
        patcher.start()
        self.addCleanup(patcher.stop)

    def install(self, engine="sensevoice"):
        with patch.object(self.store, "_metadata", return_value=[self.item]), \
             patch.object(models, "urlopen", side_effect=lambda *a, **kw: Response(self.content)):
            self.store.prepare(engine, lambda *args: None, threading.Event())

    def test_fresh_state_and_missing_backend_never_download(self):
        with patch.object(models, "urlopen") as network, \
             patch("lingyezhou.asr.sensevoice.import_funasr") as imported:
            self.assertFalse(self.store.ready("sensevoice"))
            with self.assertRaisesRegex(RuntimeError, "本地模型尚未准备好"):
                SenseVoiceBackend(store=self.store)._get_model()
            with self.assertRaises(RuntimeError):
                ParaformerBackend(store=self.store)._get_model()
            imported.assert_not_called()
            network.assert_not_called()
        self.assertFalse(self.store.root.exists())

    def test_install_is_verified_and_second_prepare_is_offline(self):
        self.install()
        self.assertTrue(self.store.ready("sensevoice"))
        with patch.object(models, "urlopen", side_effect=AssertionError("No network expected")):
            self.store.prepare("sensevoice", lambda *args: None, threading.Event())
            paths = self.store.paths("sensevoice")
        self.assertEqual(len(paths), 4)
        (self.store.component_path("sensevoice") / "model.pt").write_bytes(b"truncated")
        self.assertFalse(self.store.ready("sensevoice"))

    def test_hash_failure_does_not_mark_ready(self):
        with patch.object(self.store, "_metadata", return_value=[self.item]), \
             patch.object(models, "urlopen", side_effect=lambda *a, **kw: Response(b"x" * len(self.content))):
            with self.assertRaisesRegex(ValueError, "校验失败"):
                self.store.prepare("sensevoice", lambda *args: None, threading.Event())
        self.assertFalse(self.store.ready("sensevoice"))
        self.assertFalse((self.store.component_path("sensevoice") / "manifest.json").exists())

    def test_short_response_keeps_progress_for_retry(self):
        with patch.object(self.store, "_metadata", return_value=[self.item]), \
             patch.object(models, "urlopen", side_effect=lambda *a, **kw: Response(self.content[:5])):
            with self.assertRaisesRegex(OSError, "已保留进度"):
                self.store.prepare("sensevoice", lambda *args: None, threading.Event())
        self.assertEqual((self.store.component_path("sensevoice") / "model.pt.part").read_bytes(), self.content[:5])
        self.install()
        self.assertTrue(self.store.ready("sensevoice"))

    def test_resume_and_server_ignoring_range(self):
        part = Path(self.temp.name) / "download.part"
        part.write_bytes(self.content[:5])
        with patch.object(models, "urlopen", return_value=Response(self.content[5:], 206, {"Content-Range": "bytes 5-25/26"})) as network:
            self.store._download("sensevoice", self.item, part, lambda *a: None, threading.Event())
            self.assertEqual(network.call_args.args[0].get_header("Range"), "bytes=5-")
        self.assertEqual(part.read_bytes(), self.content)
        part.write_bytes(self.content[:5])
        with patch.object(models, "urlopen", return_value=Response(self.content, 200)):
            self.store._download("sensevoice", self.item, part, lambda *a: None, threading.Event())
        self.assertEqual(part.read_bytes(), self.content)

    def test_bad_resume_header_is_rejected(self):
        part = Path(self.temp.name) / "download.part"
        part.write_bytes(self.content[:5])
        with patch.object(models, "urlopen", return_value=Response(self.content, 206, {"Content-Range": "bytes 0-25/26"})):
            with self.assertRaises(ValueError):
                self.store._download("sensevoice", self.item, part, lambda *a: None, threading.Event())
        self.assertEqual(part.read_bytes(), self.content[:5])

    def test_mirror_returns_partial_body_as_http_200(self):
        part = Path(self.temp.name) / "download.part"
        part.write_bytes(self.content[:5])
        with patch.object(models, "urlopen", return_value=Response(self.content[5:], 200)):
            self.store._download("sensevoice", self.item, part, lambda *a: None, threading.Event())
        self.assertEqual(part.read_bytes(), self.content)

    def test_pause_keeps_partial_download(self):
        event = threading.Event()
        part = Path(self.temp.name) / "download.part"
        with patch.object(models, "urlopen", return_value=Response(self.content)):
            with self.assertRaises(models.DownloadCancelled):
                self.store._download("sensevoice", self.item, part, lambda *a: event.set(), event)
        self.assertEqual(part.read_bytes(), self.content)

    def test_delete_retains_shared_models_and_user_files(self):
        self.install()
        self.install("paraformer")
        sentinel = Path(self.temp.name) / "recording.txt"
        sentinel.write_text("keep")
        self.assertEqual(self.store.delete_engine("sensevoice"), ["sensevoice"])
        self.assertTrue(self.store.ready("paraformer"))
        self.assertFalse(self.store.ready("sensevoice"))
        self.store.delete_engine("paraformer")
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertTrue((self.store.root / ".owner.json").exists())

    def test_refuse_delete_unowned_directory(self):
        self.store.root.mkdir()
        sentinel = self.store.root / "notes.txt"
        sentinel.write_text("keep")
        with self.assertRaises(ValueError):
            self.store.delete_engine("sensevoice")
        self.assertTrue(sentinel.exists())

    def test_concurrent_management_is_rejected(self):
        from filelock import FileLock
        self.store._own_root()
        with FileLock(str(self.store.root / ".operation.lock")):
            with self.assertRaisesRegex(RuntimeError, "另一个"):
                self.store.delete_engine("sensevoice")

    def test_metadata_requires_official_hash_for_required_files(self):
        payload = {"Data": {"Files": [{"Path": "../model.pt", "Type": "blob", "Size": 10, "Sha256": "a" * 64}]}}
        with patch.object(models, "urlopen", return_value=Response(json.dumps(payload).encode())):
            with self.assertRaisesRegex(ValueError, "清单不完整"):
                self.store._metadata("sensevoice")


if __name__ == "__main__":
    unittest.main()
