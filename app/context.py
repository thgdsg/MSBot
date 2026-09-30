from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import AppConfig
from app.logging_config import configure_nvidia_error_logging, migrate_json_log
from app.persistence.first_repository import FirstRepository
from app.persistence.json_store import JsonStore
from app.persistence.message_repository import MessageRepository
from app.services.ai_service import AIService
from app.services.first_service import FirstService
from app.services.logging_service import LoggingService
from app.services.moderation_service import ModerationService
from app.services.nvidia_client import NvidiaClient
from app.services.propaganda_service import PropagandaService
from app.services.web_search_service import WebSearchService
from app.services.word_service import WordService
from app.state import BotState
from app.tools.registry import ToolRegistry


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
    web_search: WebSearchService = field(init=False)
    tools: ToolRegistry = field(init=False)
    message_repository: MessageRepository = field(init=False)
    event_handlers: list[Any] = field(default_factory=list)

    @classmethod
    def create(cls, bot: Any, config: AppConfig | None = None) -> "AppContext":
        config = config or AppConfig.from_environment()
        state = BotState()
        log_dir = config.path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        configure_nvidia_error_logging(log_dir)
        legacy_log_path = config.path("logs.json")
        interaction_log_path = log_dir / "interactions.json"
        migrate_json_log(legacy_log_path, interaction_log_path, [])
        legacy_history_path = config.path("conversation_history.json")
        history_log_path = log_dir / "conversation_history.json"
        migrate_json_log(legacy_history_path, history_log_path, {})
        log_store = JsonStore(interaction_log_path)
        history_store = JsonStore(history_log_path)
        advertisement_store = JsonStore(config.path("propagandas.json"))
        first_repository = FirstRepository(config.path("discord_bot.db"))
        logging_service = LoggingService(log_store, state.log_lock)
        nvidia = NvidiaClient(config.nvidia_api_key)
        web_search = WebSearchService()
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
        context.message_repository = MessageRepository(config.path("message_counts.db"))
        context.propaganda = PropagandaService(context)
        context.first = FirstService(context)
        context.moderation = ModerationService(context)
        context.web_search = web_search
        context.tools = ToolRegistry(web_search, context)
        context.ai = AIService(context)
        return context
