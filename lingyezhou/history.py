from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from lingyezhou.models.transcript import Transcript
from lingyezhou.paths import user_data_dir


class HistoryStore:
    """Local recording archive. Audio remains at its original location."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else user_data_dir() / "history"

    def _folder(self, record_id: str) -> Path:
        if not record_id or any(char not in "0123456789T-abcdef" for char in record_id):
            raise ValueError("无效的历史记录编号")
        return self.root / record_id

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def add(self, transcript: Transcript, scene: str) -> str:
        now = datetime.now().astimezone()
        record_id = now.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        folder = self._folder(record_id)
        folder.mkdir(parents=True, exist_ok=False)
        self._write_json(folder / "transcript.json", transcript.to_dict())
        self._write_json(folder / "record.json", {
            "id": record_id,
            "created_at": now.isoformat(timespec="seconds"),
            "source_file": transcript.source_file,
            "source_name": Path(transcript.source_file).name,
            "scene": scene,
            "duration_ms": transcript.duration_ms,
            "speaker_count": len(transcript.speakers),
            "segment_count": len(transcript.segments),
            "analysis_mode": "",
            "report_markdown": "",
            "analysis_data": {},
            "qa_messages": [],
        })
        return record_id

    def list(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        records = []
        for path in self.root.glob("*/record.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict) and value.get("id") == path.parent.name:
                    records.append(value)
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(records, key=lambda item: str(item.get("created_at", "")), reverse=True)

    def get(self, record_id: str) -> dict:
        path = self._folder(record_id) / "record.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("id") != record_id:
            raise ValueError("历史记录内容无效")
        return value

    def load_transcript(self, record_id: str) -> Transcript:
        value = json.loads((self._folder(record_id) / "transcript.json").read_text(encoding="utf-8"))
        return Transcript.from_dict(value)

    def update_transcript(self, record_id: str, transcript: Transcript) -> None:
        self._write_json(self._folder(record_id) / "transcript.json", transcript.to_dict())
        record = self.get(record_id)
        record.update(
            duration_ms=transcript.duration_ms,
            speaker_count=len(transcript.speakers),
            segment_count=len(transcript.segments),
        )
        self._write_json(self._folder(record_id) / "record.json", record)

    def update_report(self, record_id: str, mode: str, data: dict, markdown: str) -> None:
        record = self.get(record_id)
        record.update(analysis_mode=mode, analysis_data=data, report_markdown=markdown)
        self._write_json(self._folder(record_id) / "record.json", record)

    def update_chat(self, record_id: str, messages: list[dict]) -> None:
        record = self.get(record_id)
        record["qa_messages"] = messages
        self._write_json(self._folder(record_id) / "record.json", record)

    def delete(self, record_id: str) -> None:
        folder = self._folder(record_id)
        root = self.root.resolve()
        target = folder.resolve()
        if target.parent != root:
            raise ValueError("无效的历史记录目录")
        if not target.is_dir():
            raise FileNotFoundError("历史记录不存在")
        shutil.rmtree(target)

    def comparison_payload(self, record_ids: list[str]) -> list[dict]:
        result = []
        transcript_limit = max(7500, 60000 // max(1, len(record_ids)))
        for record_id in record_ids:
            record = self.get(record_id)
            transcript = self.load_transcript(record_id)
            result.append({
                "id": record_id,
                "date": record.get("created_at"),
                "name": record.get("source_name"),
                "scene": record.get("scene"),
                "duration_ms": record.get("duration_ms"),
                "report": record.get("analysis_data") or {},
                "transcript": transcript.to_display_text()[:transcript_limit] if not record.get("analysis_data") else "",
            })
        return sorted(result, key=lambda item: str(item.get("date") or ""))
