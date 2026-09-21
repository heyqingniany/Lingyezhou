"""Live acceptance check for official metadata and a small resumable file download."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lingyezhou.asr.model_store import ModelStore


def main():
    with tempfile.TemporaryDirectory() as directory:
        store = ModelStore(directory)
        reports = {}
        for key in ("sensevoice", "paraformer", "vad", "punc", "speaker"):
            files = store._metadata(key)
            reports[key] = {"files": len(files), "bytes": sum(item["size"] for item in files)}
            if key == "vad":
                item = next(item for item in files if item["name"] == "config.yaml")
                path = Path(directory) / "test.part"
                store._download(key, item, path, lambda *args: None, threading.Event())
                assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
                original = path.read_bytes()
                path.write_bytes(path.read_bytes()[:30])
                store._download(key, item, path, lambda *args: None, threading.Event())
                assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], {
                    "expected_bytes": item["size"], "actual_bytes": path.stat().st_size,
                    "original_start": repr(original[:80]), "resumed_start": repr(path.read_bytes()[:80])}
                reports["network_resume"] = "passed"
        target = Path(__file__).resolve().parents[1] / "output/model-download-check.json"
        target.write_text(json.dumps(reports, indent=2), encoding="utf-8")
        print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
