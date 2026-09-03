from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BotState:
    palavra_mute: str | None = None
    contador: int = 0
    propaganda: int = 0
    propaganda_max: int = 50
    reaction_max: int = 3
    palavras_max: int = 50
    troca_palavra: bool = True
    mensagem_block: Any = None
    permissoes_originais: Any = None
    ignorar_omd: bool = False
    flag_first: bool = True
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    log_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    first_reset_task: asyncio.Task | None = None

