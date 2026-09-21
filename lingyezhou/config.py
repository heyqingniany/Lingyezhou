from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    ai_provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-flash"
    cloud_api_key: str = ""
    cloud_app_id: str = ""
    cloud_access_token: str = ""
    cloud_mode: str = "standard"
    model_directory: str = ""
    startup_choice: str = ""

    @property
    def cloud_ready(self) -> bool:
        return bool(self.cloud_api_key.strip() or (self.cloud_app_id.strip() and self.cloud_access_token.strip()))

    @property
    def llm_ready(self) -> bool:
        return bool(self.base_url.strip() and self.api_key.strip() and self.model.strip())

    @classmethod
    def load(cls, path: Path | str = "config.local.json") -> "AppConfig":
        target = Path(path)
        if not target.is_file():
            return cls()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            defaults = cls()
            if "ai_provider" not in data:
                base = str(data.get("base_url", ""))
                key = str(data.get("api_key", ""))
                model = str(data.get("model", ""))
                if "deepseek" in base:
                    data["ai_provider"] = "deepseek"
                elif "openai.com" in base and not key and model in {"", "gpt-4o-mini"}:
                    data.update(ai_provider="deepseek", base_url=defaults.base_url, model=defaults.model)
                elif "openai.com" in base:
                    data["ai_provider"] = "openai"
                else:
                    data["ai_provider"] = "custom"
            return cls(**{f.name: str(data.get(f.name, getattr(defaults, f.name))) for f in fields(cls)})
        except (OSError, json.JSONDecodeError, TypeError):
            return cls()

    def save(self, path: Path | str = "config.local.json") -> None:
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
