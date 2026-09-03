from __future__ import annotations

import discord
from discord import app_commands

from app.commands.helpers import in_server
from app.views.first_views import MonthlyLeaderboardView, SimpleLeaderboardView


def _is_owner(interaction: discord.Interaction, context) -> bool:
    return bool(context.config.owner_id) and str(interaction.user.id) == context.config.owner_id


def register_commands(tree, context) -> list[app_commands.Command]:
    service = context.first

    @app_commands.command(
        name="adicionafirst",
        description="[ADM] Adiciona manualmente uma contagem de 'first' a um usuario.",
    )
    async def adicionafirst(interaction: discord.Interaction, user_id: str, count: int):
        if not _is_owner(interaction, context):
            await interaction.response.send_message(
                "Voce nao tem permissao para usar este comando.", ephemeral=True
            )
            return
        try:
            user = await service.fetch_user(user_id)
            existing = service.get_user(str(user.id))
            new_count = service.adjust_first_count(str(user.id), user.name, count)
            if existing is not None:
                message = f"Contagem atualizada! Novo total para {user.name}: {new_count}"
            else:
                message = f"Usuario {user.name} adicionado com {count} 'first'."
            await interaction.response.send_message(message, ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("ID de usuario invalido.", ephemeral=True)
        except (ValueError, TypeError):
            await interaction.response.send_message("ID de usuario invalido.", ephemeral=True)
        except Exception as error:
            await interaction.response.send_message(f"Ocorreu um erro: {error}", ephemeral=True)

    @app_commands.command(
        name="removefirst",
        description="[ADM] Remove manualmente uma contagem de 'first' de um usuario.",
    )
    async def removefirst(interaction: discord.Interaction, user_id: str, count: int):
        if not _is_owner(interaction, context):
            await interaction.response.send_message(
                "Voce nao tem permissao para usar este comando.", ephemeral=True
            )
            return
        try:
            user = await service.fetch_user(user_id)
            if service.get_user(str(user.id)) is None:
                await interaction.response.send_message(
                    f"Usuario {user.name} nao encontrado no banco de dados.", ephemeral=True
                )
                return
            new_count = service.adjust_first_count(str(user.id), user.name, -count)
            await interaction.response.send_message(
                f"Contagem atualizada! Novo total para {user.name}: {new_count}", ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message("ID de usuario invalido.", ephemeral=True)
        except (ValueError, TypeError):
            await interaction.response.send_message("ID de usuario invalido.", ephemeral=True)
        except Exception as error:
            await interaction.response.send_message(f"Ocorreu um erro: {error}", ephemeral=True)

    @app_commands.command(
        name="top10first",
        description="Mostra o top 10 pessoas que ja foram first (geral ou mensal).",
    )
    @app_commands.describe(mensal="Deseja ver o placar mensal? (Padrao: Nao)")
    async def top10first(interaction: discord.Interaction, mensal: bool = False):
        if not in_server(interaction, context):
            await interaction.response.send_message(
                "Este comando so pode ser usado no servidor Menes Suecos.", ephemeral=True
            )
            return
        if mensal:
            view = MonthlyLeaderboardView(service, interaction.user.id, timeout=60)
            await interaction.response.send_message(view.content(), view=view)
        else:
            view = SimpleLeaderboardView(service, interaction.user.id, timeout=60)
            await interaction.response.send_message(view.content(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="buscafirsts",
        description="Busca a quantidade de firsts de um usuario pelo nome ou apelido.",
    )
    async def buscafirsts(interaction: discord.Interaction, username: str):
        if not in_server(interaction, context):
            await interaction.response.send_message("Server nao permitido", ephemeral=True)
            return
        guild = interaction.guild
        member = discord.utils.find(
            lambda candidate: candidate.display_name.lower() == username.lower()
            or candidate.name.lower() == username.lower(),
            guild.members,
        )
        if not member:
            await interaction.response.send_message(
                f"Usuario {username} nao encontrado no servidor.", ephemeral=True
            )
            return
        result = service.get_user(str(member.id))
        if result:
            found_username, first_count = result
            await interaction.response.send_message(
                f"Usuario: {found_username}\nQuantidade de 'firsts': {first_count}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"Usuario {username} nao encontrado no banco de dados.", ephemeral=True
            )

    return [adicionafirst, removefirst, top10first, buscafirsts]
