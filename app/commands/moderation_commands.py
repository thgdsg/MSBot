from __future__ import annotations

import asyncio
import shutil

import discord
from discord import app_commands

from app.commands.helpers import is_moderator, reject_permission


def register_commands(tree, context) -> list[app_commands.Command]:
    service = context.moderation

    @app_commands.command(
        name="enviarmsg",
        description="[ADM] Faz o Yung Bot enviar uma mensagem no chat",
    )
    async def enviarmsg(interaction: discord.Interaction, mensagemescrita: str):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        print("Comando enviarmsg utilizado")
        await interaction.response.send_message("Mensagem enviada", ephemeral=True)
        await interaction.channel.send(mensagemescrita)

    @app_commands.command(name="baixarvideo", description="Baixa um video e envia no chat")
    async def baixarvideo(interaction: discord.Interaction, link: str):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        download_dir = None
        try:
            max_size = getattr(interaction.guild, "filesize_limit", 25 * 1024 * 1024)
            video_path, title, max_height, download_dir = await asyncio.to_thread(
                service.download_video_until_limit, link, max_size
            )
            await interaction.channel.send(
                f"video baixado ({max_height}p): {title}",
                file=discord.File(video_path),
            )
            await interaction.followup.send(
                "video enviado e arquivo local apagado.", ephemeral=True
            )
            print(f"Comando baixarvideo utilizado para {link}")
        except Exception as error:
            print(f"Falha ao baixar/enviar video: {error}")
            await interaction.followup.send(
                f"falha ao baixar ou enviar o video: {error}", ephemeral=True
            )
        finally:
            if download_dir:
                shutil.rmtree(download_dir, ignore_errors=True)

    @app_commands.command(
        name="respondermsg",
        description="[ADM] Faz o Yung Bot responder uma mensagem especifica com texto manual",
    )
    async def respondermsg(
        interaction: discord.Interaction, mensagem_id: str, resposta: str
    ):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        try:
            mensagem = await interaction.channel.fetch_message(int(mensagem_id))
            await interaction.response.send_message("Resposta enviada", ephemeral=True)
            await mensagem.reply(resposta)
            print(f"Comando respondermsg utilizado para a mensagem {mensagem_id}")
        except ValueError:
            await interaction.response.send_message(
                "ID da mensagem deve ser um numero inteiro valido", ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message("Mensagem nao encontrada", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Permissoes insuficientes para responder a esta mensagem", ephemeral=True
            )
        except discord.HTTPException as error:
            await interaction.response.send_message(
                f"Ocorreu um erro ao tentar responder a mensagem: {error}", ephemeral=True
            )

    @app_commands.command(name="mutar", description="[ADM] Muta um membro por um tempo especifico")
    async def mutar(
        interaction: discord.Interaction,
        membro: discord.Member,
        duracao: str,
        motivo: str,
    ):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        result = await service.mute_member(membro, interaction.guild, duracao, motivo)
        if result is None:
            await interaction.response.send_message("Cargo de mute nao encontrado.", ephemeral=True)
            return
        if result == 0 or result[0] == 0:
            await interaction.response.send_message(
                "Duracao invalida. Use o formato '1h30m20s'.", ephemeral=True
            )
            return
        seconds, (_, formatted) = result
        print(f"{membro} foi mutado por {formatted}. Motivo: {motivo}")
        await interaction.response.send_message(
            f"{membro.mention} foi mutado por {formatted}. Motivo: {motivo}", ephemeral=True
        )
        await asyncio.sleep(seconds)
        member_after_wait = interaction.guild.get_member(membro.id)
        if member_after_wait:
            mute_role = discord.utils.get(
                interaction.guild.roles, id=int(context.config.mute_role_id)
            )
            if mute_role and mute_role in member_after_wait.roles:
                await member_after_wait.remove_roles(mute_role)
                print(f"{membro.display_name} foi desmutado apos {formatted}.")
                await service.send_log(f"{membro.mention} foi desmutado apos {formatted}.")

    @app_commands.command(name="desmutar", description="[ADM] Desmuta um membro")
    async def desmutar(interaction: discord.Interaction, membro: discord.Member):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        result = await service.unmute_member(membro, interaction.guild)
        if result is None:
            await interaction.response.send_message("Cargo de mute nao encontrado.", ephemeral=True)
        elif result:
            print(f"{membro.display_name} foi desmutado.")
            await interaction.response.send_message(
                f"{membro.mention} foi desmutado.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{membro.mention} nao esta mutado.", ephemeral=True
            )

    @app_commands.command(
        name="mensagemdivina",
        description="[ADM] Mensagem dos deuses inspirada no TempleOS",
    )
    async def mensagemdivina(interaction: discord.Interaction, numeropalavras: int):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        print("Comando mensagemdivina utilizado")
        await interaction.response.send_message(
            service.divine_message(numeropalavras), ephemeral=False
        )

    return [enviarmsg, baixarvideo, respondermsg, mutar, desmutar, mensagemdivina]
