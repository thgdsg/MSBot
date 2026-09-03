from __future__ import annotations

import discord
from discord import app_commands

from app.commands.helpers import is_moderator, reject_permission


def register_commands(tree, context) -> list[app_commands.Command]:
    service = context.propaganda

    @app_commands.command(name="mudaconfigpropaganda", description="[ADM] Muda configuracoes da propaganda")
    async def mudaconfigpropaganda(interaction: discord.Interaction, numeromsgslidas: int, numeroreacoes: int):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        context.state.propaganda_max = numeromsgslidas
        context.state.reaction_max = numeroreacoes
        await interaction.response.send_message(
            f"Configuracoes da propaganda alteradas para {numeromsgslidas} mensagens lidas e {numeroreacoes} reacoes",
            ephemeral=True,
        )

    @app_commands.command(name="enviapropaganda", description="[ADM] Envia uma propaganda no servidor")
    async def enviapropaganda(interaction: discord.Interaction, bloqueiachat: bool, escolha: int | None = None):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        await interaction.response.defer(ephemeral=True)
        await service.send_ad(interaction.channel, interaction.guild, bloqueiachat, escolha)
        await interaction.followup.send("Propaganda enviada.", ephemeral=True)

    @app_commands.command(name="desbloqueiachat", description="[ADM] Desbloqueia o chat e reseta propaganda")
    async def desbloqueiachat(interaction: discord.Interaction):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        had_block_message = context.state.mensagem_block is not None
        had_permission_lock = not interaction.channel.permissions_for(
            interaction.guild.default_role
        ).send_messages
        changed = await service.unblock(interaction.channel, interaction.guild)
        if had_block_message:
            await interaction.response.send_message("Chat desbloqueado com sucesso", ephemeral=True)
        elif changed and had_permission_lock:
            await interaction.response.send_message("Permissoes do canal resetadas.", ephemeral=True)
        else:
            await interaction.response.send_message("O chat ja esta desbloqueado", ephemeral=True)

    @app_commands.command(name="bloqueiachat", description="[ADM] Bloqueia o chat")
    async def bloqueiachat(interaction: discord.Interaction):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        if await service.block(interaction.channel, interaction.guild):
            await interaction.response.send_message("Chat bloqueado com sucesso", ephemeral=True)
        else:
            await interaction.response.send_message("O chat ja esta bloqueado", ephemeral=True)

    return [mudaconfigpropaganda, enviapropaganda, desbloqueiachat, bloqueiachat]
