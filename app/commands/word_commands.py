from __future__ import annotations

import discord
from discord import app_commands

from app.commands.helpers import in_server, is_moderator, reject_permission


def register_commands(tree, context) -> list[app_commands.Command]:
    service = context.word

    @app_commands.command(name="novapalavra", description="[ADM] Torna uma nova palavra aleatoria a palavra proibida")
    async def novapalavra(interaction: discord.Interaction):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        service.reset_message_counter()
        word = await service.get_new_word()
        await interaction.response.send_message(f"A nova palavra e: **{word}**", ephemeral=True)
        print("Motivo: comando novapalavra")

    @app_commands.command(name="redefinepalavra", description="[ADM] Nenhuma palavra dara timeout")
    async def redefinepalavra(interaction: discord.Interaction):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        service.clear()
        await interaction.response.send_message("palavraMute foi redefinida. Nenhuma palavra causara timeout.", ephemeral=True)

    @app_commands.command(name="mostrapalavra", description="[ADM] Mostra a palavra atual que da timeout")
    async def mostrapalavra(interaction: discord.Interaction):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        word = service.state.palavra_mute
        if word is None:
            await interaction.response.send_message("Nao tem nenhuma palavra atual que da timeout", ephemeral=True)
        else:
            await interaction.response.send_message(f"**{word}** e a palavra atual que da timeout", ephemeral=True)
            print(f"A palavra escolhida foi mostrada para {interaction.user.name}")

    @app_commands.command(name="escolhepalavra", description="[ADM] Define manualmente a palavra que causa timeout")
    async def escolhepalavra(interaction: discord.Interaction, novapalavra: str):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        word = service.set_word(novapalavra)
        await interaction.response.send_message(f"**{word}** e a nova palavra que da timeout", ephemeral=True)

    @app_commands.command(name="escolhenummensagens", description="[ADM] Define o numero de mensagens para trocar a palavra")
    async def escolhenummensagens(interaction: discord.Interaction, numeromensagens: int):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        service.set_message_limit(numeromensagens)
        await interaction.response.send_message(f"Agora o bot vai trocar de palavra a cada {service.state.palavras_max} mensagens", ephemeral=True)

    @app_commands.command(name="mantempalavra", description="[ADM] Liga/Desliga a troca automatica de palavra")
    async def mantempalavra(interaction: discord.Interaction):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        enabled = service.toggle_automatic_rotation()
        status = "LIGADO" if enabled else "DESLIGADO"
        await interaction.response.send_message(f"Troca de palavra automatica agora esta **{status}**", ephemeral=True)

    @app_commands.command(name="significado", description="Busca o significado de uma palavra")
    async def significado(interaction: discord.Interaction, palavra: str):
        if not in_server(interaction, context):
            await interaction.response.send_message("Server nao permitido", ephemeral=True)
            return
        result = service.meaning(palavra)
        if result and result.meaning is not None:
            await interaction.response.send_message(f"**{palavra.capitalize()}:**\n{result.meaning}", ephemeral=False)
        else:
            await interaction.response.send_message("ERRO: Palavra invalida ou escrita errada (Dica: escreva a palavra com acento)", ephemeral=True)

    return [novapalavra, redefinepalavra, mostrapalavra, escolhepalavra, escolhenummensagens, mantempalavra, significado]

