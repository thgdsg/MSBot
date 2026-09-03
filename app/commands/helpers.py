from __future__ import annotations


def in_server(interaction, context) -> bool:
    return interaction.guild_id == context.config.server_int


def is_moderator(interaction, context) -> bool:
    return in_server(interaction, context) and interaction.user.guild_permissions.moderate_members


async def reject_permission(interaction, message: str = "Voce nao tem permissoes suficientes") -> None:
    await interaction.response.send_message(message, ephemeral=True)

