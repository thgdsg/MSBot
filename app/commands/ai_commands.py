from __future__ import annotations

import discord
from discord import app_commands

from app.commands.helpers import in_server, is_moderator, reject_permission
from app.services.ai_service import MODEL_LIST, THINKING_MODES, extract_image_urls, message_text_for_prompt, reply_in_chunks


async def resolve_referenced_bot_message(message, bot_user_id: int) -> str | None:
    if not message.reference or not message.reference.message_id:
        return None
    referenced = message.reference.resolved
    if not isinstance(referenced, discord.Message):
        try:
            referenced = await message.channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
    if isinstance(referenced, discord.Message) and referenced.author and referenced.author.id == bot_user_id:
        return referenced.content
    return None


async def send_channel_in_chunks(channel, response: str) -> None:
    chunks = [
        response[index : index + 2000]
        for index in range(0, len(response), 2000)
    ] or ["(sem conteudo)"]
    for chunk in chunks:
        await channel.send(chunk)


def register_commands(tree, context) -> list[app_commands.Command]:
    service = context.ai

    @app_commands.command(name="conversar", description="Converse com o Yung Bot.")
    @app_commands.describe(mensagem="Sobre o que voce quer falar?")
    async def conversar(interaction: discord.Interaction, mensagem: str):
        if not in_server(interaction, context):
            await interaction.response.send_message("Este comando so pode ser usado no servidor Menes Suecos.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        answer = await service.get_response(
            channel_id=str(interaction.channel_id),
            author_name=interaction.user.display_name,
            user_id=interaction.user.id,
            message_text=mensagem,
            channel_name=getattr(interaction.channel, "name", None),
        )
        await context.logging.log_ai_interaction(
            source="slash_conversar", user_id=interaction.user.id, user_name=interaction.user.name,
            guild_id=interaction.guild_id, channel_id=interaction.channel_id,
            interaction_id=interaction.id, prompt=mensagem, response=answer,
        )
        prefix = f"mensagem de {interaction.user.mention}: *{mensagem}*\n"
        if len(prefix) + len(answer) <= 2000:
            await interaction.followup.send(prefix + answer)
            return
        await interaction.followup.send(prefix + answer[: 2000 - len(prefix)])
        for index in range(2000 - len(prefix), len(answer), 2000):
            await interaction.followup.send(answer[index : index + 2000])

    @app_commands.command(
        name="enviarmsgllm",
        description="[ADM] Faz o bot enviar uma mensagem gerada pela LLM.",
    )
    @app_commands.describe(
        prompt="Instrucao que sera enviada para a LLM",
        modelo="Modelo usado somente nesta mensagem (opcional)",
    )
    @app_commands.choices(
        modelo=[app_commands.Choice(name=model, value=model) for model in MODEL_LIST]
    )
    async def enviarmsgllm(
        interaction: discord.Interaction,
        prompt: str,
        modelo: app_commands.Choice[str] | None = None,
    ):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        selected_model = modelo.value if modelo else None
        answer = await service.get_response(
            channel_id=str(interaction.channel_id),
            author_name=interaction.user.display_name,
            user_id=interaction.user.id,
            message_text=prompt,
            channel_name=getattr(interaction.channel, "name", None),
            model_override=selected_model,
        )
        await context.logging.log_ai_interaction(
            source="slash_enviarmsgllm",
            user_id=interaction.user.id,
            user_name=interaction.user.name,
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            interaction_id=interaction.id,
            prompt=prompt,
            response=answer,
        )
        await send_channel_in_chunks(interaction.channel, answer)
        await interaction.followup.send("Mensagem enviada.", ephemeral=True)

    @app_commands.command(name="respondermsgllm", description="[ADM] Faz o bot responder uma mensagem pelo ID usando a LLM.")
    @app_commands.describe(mensagem_id="ID da mensagem que o bot deve buscar e responder")
    async def responder_msg(interaction: discord.Interaction, mensagem_id: str):
        if not in_server(interaction, context) and interaction.channel_id != 1194707301442002974:
            await interaction.response.send_message("Este comando so pode ser usado no servidor Menes Suecos e no canal de imagens e videos.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.moderate_members:
            await reject_permission(interaction)
            return
        if not mensagem_id.isdigit() or not interaction.channel or not hasattr(interaction.channel, "fetch_message"):
            await interaction.response.send_message("ID de mensagem invalido ou canal indisponivel.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            target = await interaction.channel.fetch_message(int(mensagem_id))
        except discord.NotFound:
            await interaction.followup.send("Nao encontrei uma mensagem com esse ID neste canal.", ephemeral=True)
            return
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send("Nao consegui buscar essa mensagem.", ephemeral=True)
            return
        prompt = message_text_for_prompt(target)
        if not prompt:
            await interaction.followup.send("A mensagem buscada nao tem texto, anexo ou embed para responder.", ephemeral=True)
            return
        async with interaction.channel.typing():
            answer = await service.get_response(
                channel_id=str(interaction.channel_id), author_name=target.author.display_name,
                user_id=target.author.id, message_text=prompt,
                channel_name=getattr(interaction.channel, "name", None),
                image_urls=extract_image_urls(target),
            )
            await reply_in_chunks(target, answer)
        await context.logging.log_ai_interaction(
            source="slash_respondermsg", user_id=interaction.user.id, user_name=interaction.user.name,
            guild_id=interaction.guild_id, channel_id=interaction.channel_id,
            interaction_id=interaction.id, message_id=target.id, prompt=prompt, response=answer,
        )
        await interaction.followup.send(f"respondi a mensagem `{target.id}`.", ephemeral=True)

    @app_commands.command(name="alterarmodelo", description="[ADM] Altera o modelo atual usado nas respostas do bot.")
    @app_commands.describe(modelo="Modelo a ser usado:")
    @app_commands.choices(modelo=[app_commands.Choice(name=model, value=model) for model in MODEL_LIST])
    async def alterar_modelo(interaction: discord.Interaction, modelo: app_commands.Choice[str]):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        service.current_model = modelo.value
        service.current_fallback_model = "minimaxai/minimax-m3"
        await interaction.response.send_message(f"modelo alterado para {service.current_model}.", ephemeral=True)

    @app_commands.command(name="alterarthinking", description="[ADM] Altera o modo de thinking dos modelos DeepSeek V4.")
    @app_commands.describe(modo="Modo de thinking/reasoning a ser usado")
    @app_commands.choices(modo=[app_commands.Choice(name=mode, value=mode) for mode in THINKING_MODES])
    async def alterar_thinking(interaction: discord.Interaction, modo: app_commands.Choice[str]):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        if not service.nvidia.supports_reasoning(service.current_model):
            await interaction.response.send_message("O modo thinking so pode ser alterado quando o modelo atual for DeepSeek V4.", ephemeral=True)
            return
        service.current_reasoning_effort = modo.value
        await interaction.response.send_message(f"modo thinking alterado para {service.current_reasoning_effort}.", ephemeral=True)

    @app_commands.command(name="vermemoria", description="[ADM] Mostra a memoria atual do bot.")
    async def ver_memoria(interaction: discord.Interaction):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        memory = service.memory.all_text()
        if not memory:
            await interaction.response.send_message("MEMORY.md esta vazio.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        for index in range(0, len(memory), 1800):
            await interaction.followup.send(f"```md\n{memory[index : index + 1800]}\n```", ephemeral=True)

    @app_commands.command(name="resetamemoria", description="[ADM] Reinicia a memoria persistente da LLM para o estado inicial.")
    async def resetamemoria(interaction: discord.Interaction):
        if not is_moderator(interaction, context):
            await reject_permission(interaction)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with service.memory.lock:
            service.memory.reset()
        await interaction.followup.send("memoria reiniciada usando `memory_backup.md` e buffers limpos.", ephemeral=True)

    return [
        conversar,
        enviarmsgllm,
        responder_msg,
        alterar_modelo,
        alterar_thinking,
        ver_memoria,
        resetamemoria,
    ]
