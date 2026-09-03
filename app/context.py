from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import AppConfig
from app.persistence.first_repository import FirstRepository
from app.persistence.json_store import JsonStore
from app.services.ai_service import AIService
from app.services.first_service import FirstService
from app.services.logging_service import LoggingService
from app.services.moderation_service import ModerationService
from app.services.nvidia_client import NvidiaClient
from app.services.propaganda_service import PropagandaService
from app.services.word_service import WordService
from app.state import BotState


@dataclass
class AppContext:
    bot: Any
    config: AppConfig
    state: BotState
    log_store: JsonStore
    history_store: JsonStore
    advertisement_store: JsonStore
    first_repository: FirstRepository
    logging: LoggingService
    nvidia: NvidiaClient
    word: WordService = field(init=False)
    propaganda: PropagandaService = field(init=False)
    first: FirstService = field(init=False)
    moderation: ModerationService = field(init=False)
    ai: AIService = field(init=False)
    event_handlers: list[Any] = field(default_factory=list)

    @classmethod
    def create(cls, bot: Any, config: AppConfig | None = None) -> "AppContext":
        config = config or AppConfig.from_environment()
        state = BotState()
        log_store = JsonStore(config.path("logs.json"))
        history_store = JsonStore(config.path("conversation_history.json"))
        advertisement_store = JsonStore(config.path("propagandas.json"))
        first_repository = FirstRepository(config.path("discord_bot.db"))
        logging_service = LoggingService(log_store, state.log_lock)
        nvidia = NvidiaClient(config.nvidia_api_key)
        context = cls(
            bot=bot,
            config=config,
            state=state,
            log_store=log_store,
            history_store=history_store,
            advertisement_store=advertisement_store,
            first_repository=first_repository,
            logging=logging_service,
            nvidia=nvidia,
        )
        context.word = WordService(context)
        context.propaganda = PropagandaService(context)
        context.first = FirstService(context)
        context.moderation = ModerationService(context)
        context.ai = AIService(context)
        return context
