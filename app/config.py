from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    token: str | None
    server_id: str | None
    tojao_id: str | None
    log_channel_id: str | None
    mute_role_id: str | None
    owner_id: str | None
    nvidia_api_key: str | None
    channel_bot_id: str | None = None

    @classmethod
    def from_environment(cls, root_dir: Path | None = None) -> "AppConfig":
        resolved_root = Path(root_dir or PROJECT_ROOT).resolve()
        load_dotenv(resolved_root / ".env")
        return cls(
            root_dir=resolved_root,
            token=os.getenv("DISCORD_TOKEN"),
            server_id=os.getenv("MENES_SUECOS"),
            tojao_id=os.getenv("TOJAO"),
            log_channel_id=os.getenv("LOG_CHANNEL_ID"),
            mute_role_id=os.getenv("MUTE_ROLE_ID"),
            owner_id=os.getenv("DAFONZ_ID"),
            nvidia_api_key=os.getenv("NVIDIA_API_KEY"),
            channel_bot_id=os.getenv("CANAL_BOT"),
        )

    @property
    def server_int(self) -> int:
        if not self.server_id:
            raise RuntimeError("MENES_SUECOS nao configurado no .env")
        return int(self.server_id)

    def path(self, filename: str) -> Path:
        return self.root_dir / filename

    def validate_runtime(self) -> None:
        if not self.token:
            raise RuntimeError("DISCORD_TOKEN nao configurado no .env")
        self.server_int
