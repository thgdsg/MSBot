from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord

from app.events.message_events import MessageEventHandler
from app.events.reaction_events import ReactionEventHandler


try:
    SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:  # Windows without an installed IANA tz database.
    SAO_PAULO_TZ = timezone(timedelta(hours=-3))


class LifecycleEventHandler:
    def __init__(self, bot, context):
        self.bot = bot
        self.context = context

    @staticmethod
    def _seconds_until_next_midnight_sp() -> float:
        now = datetime.now(SAO_PAULO_TZ)
        next_day = (now + timedelta(days=1)).date()
        next_midnight = datetime.combine(next_day, time(0, 0, 0), tzinfo=SAO_PAULO_TZ)
        return max(0.0, (next_midnight - now).total_seconds())

    async def _first_reset_scheduler(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            delay = self._seconds_until_next_midnight_sp()
            print(f"Proximo reset do 'first' em ~{int(delay)}s (00:00 SP).")
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return
            try:
                guild = self.bot.get_guild(self.context.config.server_int)
                await self.context.first.reset_daily(guild)
            except Exception as error:
                print(f"Erro no reset do 'first': {error}")

    async def on_ready(self) -> None:
        await self.bot.wait_until_ready()
        print(f"Conectado ao Discord como {self.bot.user}!")
        self.context.first.setup()
        task = self.context.state.first_reset_task
        if task is None or task.done():
            self.context.state.first_reset_task = asyncio.create_task(
                self._first_reset_scheduler()
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        await self.context.logging.log_command(interaction)
        return True


def register_events(bot, context) -> list[object]:
    message_handler = MessageEventHandler(bot, context)
    reaction_handler = ReactionEventHandler(context)
    lifecycle_handler = LifecycleEventHandler(bot, context)
    # Bot.on_message already calls process_commands; replacing it avoids a
    # second invocation because MessageEventHandler also handles that path.
    bot.on_message = message_handler.on_message
    bot.add_listener(reaction_handler.on_reaction_add, "on_reaction_add")
    bot.add_listener(reaction_handler.on_message_delete, "on_message_delete")
    bot.add_listener(lifecycle_handler.on_ready, "on_ready")
    bot.tree.interaction_check = lifecycle_handler.interaction_check
    return [message_handler, reaction_handler, lifecycle_handler]


def register_all_events(bot, context) -> list[object]:
    handlers = register_events(bot, context)
    context.event_handlers.extend(handlers)
    return handlers
