from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self, default: Any) -> Any:
        try:
            with self.path.open("r", encoding="utf-8") as file:
                value = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return default
        return value if isinstance(value, type(default)) else default

    def save(self, data: Any) -> None:
        temporary_path = self.path.with_name(f"{self.path.name}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        temporary_path.replace(self.path)

    def append(self, entry: dict) -> None:
        data = self.load([])
        data.append(entry)
        self.save(data)

