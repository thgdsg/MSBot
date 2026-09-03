from __future__ import annotations

from datetime import datetime
from typing import Any

from app.persistence.json_store import JsonStore


class LoggingService:
    def __init__(self, store: JsonStore, lock):
        self.store = store
        self.lock = lock

    async def log_command(self, interaction) -> None:
        async with self.lock:
            entries = self.store.load([])
            entries.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "user_id": interaction.user.id,
                    "user_name": interaction.user.name,
                    "command": interaction.command.name if interaction.command else "unknown",
                    "options": self._extract_options(interaction),
                }
            )
            self.store.save(entries)

    async def log_ai_interaction(self, **data: Any) -> None:
        async with self.lock:
            entries = self.store.load([])
            entries.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "type": "ai_interaction",
                    **data,
                }
            )
            self.store.save(entries)

    @staticmethod
    def _extract_options(interaction) -> dict[str, str]:
        if not interaction.data or "options" not in interaction.data:
            return {}
        return {
            option["name"]: str(option["value"])
            for option in interaction.data.get("options", [])
        }

