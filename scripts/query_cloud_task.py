"""Retrieve an existing Seed ASR task without submitting audio again."""
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lingyezhou.config import AppConfig
from lingyezhou.asr.doubao import DoubaoBackend


def main():
    config = AppConfig.load()
    task_id = sys.argv[1]
    headers = {
        "Content-Type": "application/json", "X-Api-Key": config.cloud_api_key.strip(),
        "X-Api-Resource-Id": "volc.seedasr.auc", "X-Api-Request-Id": task_id,
    }
    for _ in range(120):
        req = Request("https://openspeech.bytedance.com/api/v3/auc/bigmodel/query", data=b"{}", headers=headers)
        try:
            with urlopen(req, timeout=60) as response:
                status = response.headers.get("X-Api-Status-Code")
                print("status:", status, flush=True)
                if status == "20000000":
                    data = json.loads(response.read())
                    target = Path("output") / f"cloud_{task_id}"
                    target.mkdir(parents=True, exist_ok=True)
                    (target / "provider_response.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    result = DoubaoBackend.parse_response(data, sys.argv[2])
                    result.save(target)
                    print("Saved:", target, "segments:", len(result.segments), "speakers:", len(result.speakers))
                    return 0
                if status not in {"20000001", "20000002"}:
                    return 1
        except HTTPError as exc:
            message = exc.headers.get("X-Api-Message", "")
            print("HTTP", exc.code, "status", exc.headers.get("X-Api-Status-Code"), "message", message.replace(config.cloud_api_key, "[REDACTED]"))
            return 1
        time.sleep(3)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
