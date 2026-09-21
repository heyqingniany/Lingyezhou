from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lingyezhou.asr.whisper import WhisperBackend


class WhisperBackendTests(unittest.TestCase):
    def test_transcribe_maps_segments_and_uses_terms_as_prompt(self):
        model = Mock()
        model.transcribe.return_value = (
            iter([SimpleNamespace(start=1.25, end=3.5, text=" 聆页舟很好用。 ")]),
            SimpleNamespace(duration=4.0),
        )
        backend = WhisperBackend(device="cpu")
        backend._model = model
        result = backend.transcribe("sample.wav", ["聆页舟", "CTranslate2"])
        self.assertEqual(result.duration_ms, 4000)
        self.assertEqual(result.segments[0].start, 1250)
        self.assertEqual(result.segments[0].text, "聆页舟很好用。")
        kwargs = model.transcribe.call_args.kwargs
        self.assertIsNone(kwargs["language"])
        self.assertIn("CTranslate2", kwargs["initial_prompt"])
        self.assertEqual(kwargs["hotwords"], "聆页舟 CTranslate2")
        self.assertTrue(kwargs["multilingual"])
        self.assertTrue(kwargs["vad_filter"])

    def test_model_is_loaded_only_from_verified_local_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Mock()
            store.paths.return_value = {"whisper": directory}
            model = object()
            fake_module = SimpleNamespace(WhisperModel=Mock(return_value=model))
            with patch.dict("sys.modules", {"faster_whisper": fake_module}):
                backend = WhisperBackend(store=store, device="cpu")
                self.assertIs(backend._get_model(), model)
            fake_module.WhisperModel.assert_called_once_with(
                directory, device="cpu", compute_type="int8", local_files_only=True
            )


if __name__ == "__main__":
    unittest.main()
