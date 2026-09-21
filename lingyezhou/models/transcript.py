from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class TranscriptSegment:
    start: int
    end: int
    speaker: int
    text: str

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptSegment":
        return cls(
            start=int(data.get("start", 0)),
            end=int(data.get("end", data.get("start", 0))),
            speaker=int(data.get("speaker", data.get("spk", 0))),
            text=str(data.get("text", data.get("sentence", ""))).strip(),
        )


@dataclass(slots=True)
class Transcript:
    source_file: str
    duration_ms: int = 0
    segments: list[TranscriptSegment] = field(default_factory=list)
    speaker_roles: dict[int, str] = field(default_factory=dict)
    hotwords: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Transcript":
        roles = data.get("speaker_roles", {})
        return cls(
            source_file=str(data.get("source_file", "")),
            duration_ms=int(data.get("duration_ms", 0)),
            segments=[TranscriptSegment.from_dict(item) for item in data.get("segments", []) if isinstance(item, dict)],
            speaker_roles={int(key): str(value) for key, value in roles.items()} if isinstance(roles, dict) else {},
            hotwords=[str(value) for value in data.get("hotwords", [])],
        )

    @property
    def speakers(self) -> list[int]:
        return sorted({segment.speaker for segment in self.segments})

    def role_for(self, speaker: int) -> str:
        return self.speaker_roles.get(speaker) or f"Speaker {speaker}"

    @staticmethod
    def format_time(milliseconds: int) -> str:
        total_seconds = max(0, milliseconds // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def to_display_text(self) -> str:
        return "\n\n".join(
            f"[{self.format_time(s.start)}] {self.role_for(s.speaker)}\n{s.text}"
            for s in self.segments
        )

    def to_plain_text(self) -> str:
        return self.to_display_text() + ("\n" if self.segments else "")

    @staticmethod
    def format_srt_time(milliseconds: int) -> str:
        value = max(0, milliseconds)
        hours, remainder = divmod(value, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, millis = divmod(remainder, 1_000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    def to_srt(self) -> str:
        blocks = []
        for index, segment in enumerate(self.segments, 1):
            blocks.append(
                f"{index}\n{self.format_srt_time(segment.start)} --> "
                f"{self.format_srt_time(segment.end)}\n"
                f"{self.role_for(segment.speaker)}：{segment.text}"
            )
        return "\n\n".join(blocks) + ("\n" if blocks else "")

    def to_markdown(self) -> str:
        title = f"# 转写记录：{Path(self.source_file).name}\n\n"
        return title + self.to_display_text() + "\n"

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "duration_ms": self.duration_ms,
            "speaker_roles": {str(k): v for k, v in self.speaker_roles.items()},
            "hotwords": list(self.hotwords),
            "segments": [asdict(segment) for segment in self.segments],
        }

    def save(self, output_dir: Path | str = "output") -> tuple[Path, Path]:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        json_path = target / "transcript.json"
        md_path = target / "transcript.md"
        json_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(self.to_markdown(), encoding="utf-8")
        return json_path, md_path
