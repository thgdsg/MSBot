from __future__ import annotations

import random

import discord


class PropagandaService:
    def __init__(self, context):
        self.context = context

    @property
    def state(self):
        return self.context.state

    @property
    def advertisements(self) -> list[dict]:
        value = self.context.advertisement_store.load([])
        return value if isinstance(value, list) else []

    async def send_ad(self, channel, guild, bloqueiachat: bool, escolha: int | None = None) -> None:
        options = self.advertisements
        selected = None
        if escolha is not None:
            selected = next((item for item in options if item.get("numero") == escolha), None)
        if selected is None:
            selected = random.choice(options)

        if self.state.mensagem_block:
            try:
                previous_channel = self.state.mensagem_block.channel
                previous_guild = self.state.mensagem_block.guild
                await previous_channel.set_permissions(
                    previous_guild.default_role,
                    overwrite=self.state.permissoes_originais,
                )
                await self.state.mensagem_block.delete()
            except (discord.NotFound, discord.Forbidden) as error:
                print(f"Não foi possível limpar o bloqueio anterior: {error}")
            finally:
                self.state.mensagem_block = None
                self.state.permissoes_originais = None

        image_path = selected.get("imagem")
        if image_path:
            image_path = self.context.config.path(str(image_path))
        sent_message = await channel.send(
            str(selected["texto"]),
            file=discord.File(image_path) if image_path else None,
        )

        if bloqueiachat:
            self.state.propaganda = 0
            self.state.mensagem_block = sent_message
            self.state.permissoes_originais = channel.overwrites_for(guild.default_role)
            await sent_message.add_reaction("✅")
            await channel.set_permissions(guild.default_role, send_messages=False)
            print("Propaganda enviada, bloqueando chat")

    async def unblock(self, channel, guild) -> bool:
        if self.state.mensagem_block:
            try:
                self.state.ignorar_omd = True
                await self.state.mensagem_block.delete()
            except discord.NotFound:
                print("Mensagem de bloqueio já havia sido deletada.")
            finally:
                self.state.ignorar_omd = False

            if self.state.permissoes_originais is not None:
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=self.state.permissoes_originais,
                )
            self.state.mensagem_block = None
            self.state.permissoes_originais = None
            return True

        if not channel.permissions_for(guild.default_role).send_messages:
            await channel.set_permissions(guild.default_role, send_messages=True)
            return True
        return False

    async def block(self, channel, guild) -> bool:
        if channel.permissions_for(guild.default_role).send_messages:
            await channel.set_permissions(guild.default_role, send_messages=False)
            return True
        return False

    async def handle_reaction_unlock(self, reaction) -> None:
        if not self.state.mensagem_block or reaction.message.id != self.state.mensagem_block.id:
            return
        if str(reaction.emoji) != "✅" or reaction.count < self.state.reaction_max:
            return

        async with self.state.lock:
            if not self.state.mensagem_block:
                return
            print("Contagem de reações atingida. Desbloqueando chat.")
            channel = self.state.mensagem_block.channel
            try:
                self.state.ignorar_omd = True
                await self.state.mensagem_block.delete()
            except discord.NotFound:
                pass
            finally:
                self.state.ignorar_omd = False

            if self.state.permissoes_originais is not None:
                await channel.set_permissions(
                    reaction.message.guild.default_role,
                    overwrite=self.state.permissoes_originais,
                )
            self.state.mensagem_block = None
            self.state.permissoes_originais = None

    async def handle_deleted_message(self, message) -> None:
        if self.state.ignorar_omd or not self.state.mensagem_block:
            return
        if message.id != self.state.mensagem_block.id:
            return

        print("Mensagem de bloqueio foi deletada, restaurando permissões.")
        if self.state.permissoes_originais is not None:
            await message.channel.set_permissions(
                message.guild.default_role,
                overwrite=self.state.permissoes_originais,
            )
        self.state.mensagem_block = None
        self.state.permissoes_originais = None

