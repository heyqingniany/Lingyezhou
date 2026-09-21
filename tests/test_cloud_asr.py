import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from lingyezhou.asr.base import ASRError
from lingyezhou.asr.doubao import DoubaoBackend
from lingyezhou.config import AppConfig


def response_data():
    return {
        "audio_info": {"duration": 10000},
        "result": {"utterances": [
            {"start_time": 100, "end_time": 900, "text": "你好。", "additions": {"speaker": "1"}},
            {"start_time": 1000, "end_time": 2000, "text": "换签。", "additions": {"speaker": "2"}},
            {"start_time": 2100, "end_time": 2400, "text": "嗯。", "additions": {"speaker": "3"}},
            {"start_time": 2500, "end_time": 5000, "text": "9000 元。", "additions": {"speaker": "2"}},
        ]},
    }


class CloudTests(unittest.TestCase):
    def test_file_size_limits_follow_selected_cloud_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.mp3"
            with path.open("wb") as stream:
                stream.seek(100_000_000)
                stream.write(b"0")
            with self.assertRaises(ASRError):
                DoubaoBackend(api_key="key", mode="flash").validate_audio(path)
            DoubaoBackend(api_key="key", mode="standard").validate_audio(path)

    @patch("lingyezhou.asr.doubao.time.sleep")
    @patch("lingyezhou.asr.doubao.urlopen")
    def test_standard_submits_once_then_polls(self, mocked, sleep):
        from contextlib import ExitStack
        from unittest.mock import mock_open
        replies = []
        for status, payload in [("20000000", {}), ("20000001", {}), ("20000000", response_data())]:
            response = MagicMock()
            response.headers = {"X-Api-Status-Code": status}
            response.read.return_value = json.dumps(payload).encode()
            manager = MagicMock()
            manager.__enter__.return_value = response
            replies.append(manager)
        mocked.side_effect = replies
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.wav"
            source.write_bytes(b"fixture")
            with patch.object(Path, "mkdir"), patch.object(Path, "write_text"):
                result = DoubaoBackend(api_key="test-key").transcribe(source)
        requests = [call.args[0] for call in mocked.call_args_list]
        self.assertTrue(requests[0].full_url.endswith("/submit"))
        self.assertTrue(all(r.full_url.endswith("/query") for r in requests[1:]))
        self.assertEqual(len({r.get_header("X-api-request-id") for r in requests}), 1)
        self.assertEqual(requests[0].get_header("X-api-resource-id"), "volc.seedasr.auc")
        self.assertEqual(len(result.speakers), 3)

    def test_preserves_short_third_speaker_and_timestamps(self):
        result = DoubaoBackend.parse_response(response_data(), "demo.wav")
        self.assertEqual(len(result.speakers), 3)
        self.assertEqual([s.speaker for s in result.segments], [0, 1, 2, 1])
        self.assertEqual(result.segments[2].end, 2400)
        self.assertIn("9000", result.to_srt())

    def test_missing_speaker_is_explicit(self):
        data = response_data()
        del data["result"]["utterances"][0]["additions"]
        result = DoubaoBackend.parse_response(data, "demo.wav")
        self.assertEqual(result.role_for(0), "未区分说话人")

    def test_invalid_timestamps_rejected(self):
        data = response_data()
        data["result"]["utterances"][0]["end_time"] = 0
        with self.assertRaises(ASRError):
            DoubaoBackend.parse_response(data, "demo.wav")

    @patch("lingyezhou.asr.doubao.urlopen")
    def test_request_auth_and_cloud_failures(self, mocked):
        response = MagicMock()
        response.headers = {"X-Api-Status-Code": "20000000"}
        response.read.return_value = json.dumps(response_data()).encode()
        mocked.return_value.__enter__.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "demo.wav"
            source.write_bytes(b"audio-fixture")
            for backend in (DoubaoBackend(api_key="test-key", mode="flash"), DoubaoBackend(app_id="app", access_token="token", mode="flash")):
                result = backend.transcribe(source)
                request = mocked.call_args.args[0]
                headers = {k.lower(): v for k, v in request.header_items()}
                self.assertEqual(headers["x-api-resource-id"], "volc.bigasr.auc_turbo")
                self.assertIn("x-api-key" if backend.api_key else "x-api-access-key", headers)
                payload = json.loads(request.data)
                self.assertTrue(payload["request"]["enable_speaker_info"])
                self.assertFalse(payload["request"]["enable_ddc"])
                self.assertEqual(len(result.segments), 4)
            response.headers["X-Api-Status-Code"] = "45000001"
            with self.assertRaises(ASRError):
                DoubaoBackend(api_key="test-key").transcribe(source)
            mocked.reset_mock()
            mocked.side_effect = URLError("timeout")
            with self.assertRaises(ASRError):
                DoubaoBackend(api_key="test-key").transcribe(source)
            self.assertEqual(mocked.call_count, 1)

    def test_old_config_load_and_cloud_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"api_key":"existing-text-key"}', encoding="utf-8")
            config = AppConfig.load(path)
            self.assertFalse(config.cloud_ready)
            self.assertEqual(config.api_key, "existing-text-key")
            config.cloud_api_key = "speech-key"
            config.save(path)
            self.assertTrue(AppConfig.load(path).cloud_ready)


if __name__ == "__main__":
    unittest.main()
