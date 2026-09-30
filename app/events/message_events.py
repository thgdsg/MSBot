from __future__ import annotations

import random
import asyncio

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord

from app.commands.ai_commands import resolve_referenced_bot_message
from app.services.ai_service import extract_image_urls, reply_in_chunks


try:
    SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:  # Brazil currently uses UTC-3 year-round.
    SAO_PAULO_TZ = timezone(timedelta(hours=-3))


class MessageEventHandler:
    def __init__(self, bot, context):
        self.bot = bot
        self.context = context

    async def on_message(self, message: discord.Message) -> None:
        config = self.context.config
        state = self.context.state
        if message.author.bot or message.guild is None or str(message.guild.id) != config.server_id:
            return

        repository = getattr(self.context, "message_repository", None)
        if repository is not None:
            await asyncio.to_thread(repository.record, message.id, message.guild.id, message.author.id)

        if self.bot.user and self.bot.user.mentioned_in(message):
            content = message.content.replace(f"<@{self.bot.user.id}>", "")
            content = content.replace(f"<@!{self.bot.user.id}>", "").strip()
            image_urls = extract_image_urls(message)
            if not content and not image_urls:
                return

            async with message.channel.typing():
                referenced = await resolve_referenced_bot_message(message, self.bot.user.id)
                response = await self.context.ai.get_response(
                    channel_id=str(message.channel.id),
                    author_name=message.author.display_name,
                    message_text=content,
                    user_id=message.author.id,
                    referenced_bot_message=referenced,
                    channel_name=getattr(message.channel, "name", None),
                    image_urls=image_urls,
                )
                await self.context.logging.log_ai_interaction(
                    source="mention",
                    user_id=message.author.id,
                    user_name=message.author.name,
                    guild_id=message.guild.id if message.guild else None,
                    channel_id=message.channel.id if message.channel else None,
                    message_id=message.id,
                    prompt=content,
                    response=response,
                )
                await reply_in_chunks(message, response)
            return

        await self.bot.process_commands(message)

        word = self.context.word
        if word.contains_forbidden_word(message.content):
            duration = timedelta(minutes=5)
            if not message.author.guild_permissions.moderate_members:
                await message.author.timeout(duration, reason="Falou a palavra proibida.")
                await message.channel.send(
                    f"Parabens, {message.author.mention}! "
                    "Voce falou a palavra proibida e ganhou um timeout de 5 minutos!"
                )
            else:
                await message.channel.send("O ADM sem graca falou a palavra proibida...")

            if state.troca_palavra:
                await word.get_new_word()
                if not message.author.guild_permissions.moderate_members:
                    await message.channel.send("A palavra foi trocada.")

        if not state.mensagem_block:
            should_rotate = word.increment_message_counter()
            state.propaganda += 1

            if should_rotate:
                await word.get_new_word()
                word.reset_message_counter()
                print(f"Palavra trocada por atingir {state.palavras_max} mensagens.")

            if state.propaganda >= state.propaganda_max and not isinstance(message.channel, discord.Thread):
                await self.context.propaganda.send_ad(
                    message.channel, message.guild, bloqueiachat=True
                )
                state.propaganda = 0

        await self.context.first.claim_first(message, datetime.now(SAO_PAULO_TZ))

        tojao_id = config.tojao_id
        if tojao_id and int(tojao_id) in [member.id for member in message.mentions]:
            member = message.guild.get_member(int(tojao_id))
            if member and not member.guild_permissions.moderate_members:
                await message.author.timeout(timedelta(minutes=1), reason="Pingou o Tojao.")
                await message.channel.send("NAO. PINGUE. O. TOJAO.")

        # Mention replies returned above: they never enter this lottery.
        if random.randrange(100) == 0:
            image_urls = extract_image_urls(message)
            if message.content.strip() or image_urls:
                async with message.channel.typing():
                    response = await self.context.ai.get_response(
                        channel_id=str(message.channel.id),
                        author_name=message.author.display_name,
                        user_id=message.author.id,
                        message_text=message.content,
                        channel_name=getattr(message.channel, "name", None),
                        image_urls=image_urls,
                        spontaneous=True,
                    )
                    await self.context.logging.log_ai_interaction(
                        source="spontaneous",
                        user_id=message.author.id, user_name=message.author.name,
                        guild_id=message.guild.id, channel_id=message.channel.id,
                        message_id=message.id, prompt=message.content, response=response,
                    )
                    await reply_in_chunks(message, response)
