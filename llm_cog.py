from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import ollama
import os
import asyncio
import re
import json

from datetime import datetime

from dotenv import load_dotenv
load_dotenv()
MENES_SUECOS = os.getenv('MENES_SUECOS')
OLLAMA_MODEL = "qwen3.5:2b"
CONVERSATION_HISTORY_FILE = "conversation_history.json"
###############################
## PERSONALIDADE DO YUNG BOT ##
system_prompt = """
Você é o 'Yung Bot', um assistente de IA no servidor de Discord 'Menes Suecos'. Evite pensar muito e responda o usuário a seguir sempre utilizando apenas letras minúsculas. JAMAIS ESCREVA "@everyone"
"""
###############################


async def _run_blocking(func, *args, **kwargs):
    """Executa função bloqueante fora do event loop (compatível com Python < 3.9)."""
    to_thread = getattr(asyncio, "to_thread", None)
    if to_thread is not None:
        return await to_thread(func, *args, **kwargs)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


class LLMCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    def _append_ai_history_log(
        self,
        *,
        channel_id: str,
        user_name: str,
        prompt: str,
        thinking: str | None,
        response: str,
    ) -> None:
        """Salva logs de thinking e resposta em conversation_history.json."""
        try:
            with open(CONVERSATION_HISTORY_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history_data = {}

        if not isinstance(history_data, dict):
            history_data = {"legacy_data": history_data}

        ai_logs = history_data.get("__ai_logs__")
        if not isinstance(ai_logs, list):
            ai_logs = []

        ai_logs.append(
            {
                "timestamp": datetime.now().isoformat(),
                "channel_id": channel_id,
                "user_name": user_name,
                "prompt": prompt,
                "thinking": thinking,
                "response": response,
            }
        )

        history_data["__ai_logs__"] = ai_logs

        with open(CONVERSATION_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=4, ensure_ascii=False)

    async def get_ai_response(
        self,
        channel_id: str,
        author_name: str,
        message_text: str,
        referenced_bot_message: str | None = None,
        channel_name: str | None = None,
    ):
        """Obtém uma resposta da LLM sem memória entre mensagens."""

        def _extract_thinking_and_answer(text: str) -> tuple[str | None, str]:
            """Extrai <think>...</think> quando presente e retorna (thinking, resposta_limpa)."""
            think_blocks = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL | re.IGNORECASE)
            cleaned_answer = re.sub(
                r"<think>.*?</think>",
                "",
                text,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip()

            thinking_text = "\n\n".join(block.strip() for block in think_blocks if block.strip())
            return (thinking_text or None), cleaned_answer

        formatted_message = f"{author_name}: {message_text}"

        messages = [{"role": "system", "content": system_prompt}]
        if channel_name:
            messages.append({"role": "system", "content": f"O usuario esta no canal: #{channel_name}"})
        if referenced_bot_message:
            messages.append({"role": "assistant", "content": referenced_bot_message})
        messages.append({"role": "user", "content": formatted_message})

        try:
            response = await _run_blocking(
                ollama.chat,
                model=OLLAMA_MODEL,
                messages=messages,
            )

            raw_answer = response["message"]["content"]
            response_thinking = response.get("message", {}).get("thinking")
            parsed_thinking, final_answer = _extract_thinking_and_answer(raw_answer)
            thinking_text = response_thinking or parsed_thinking

            self._append_ai_history_log(
                channel_id=channel_id,
                user_name=author_name,
                prompt=message_text,
                thinking=thinking_text,
                response=final_answer,
            )

            print("[ollama] resposta:")
            print(final_answer)

            return final_answer

        except Exception as e:
            print(f"Erro ao contatar o Ollama: {e}")
            return "Desculpe, não consegui me conectar a LLM no momento. Verifique se o serviço Ollama está rodando."

    @app_commands.command(name="conversar", description="Converse com o Yung Bot.")
    @app_commands.describe(mensagem="Sobre o que você quer falar?")
    async def conversar(self, interaction: discord.Interaction, mensagem: str):
        # Verifica se o comando foi usado no servidor correto
        if interaction.guild_id != int(MENES_SUECOS):
            await interaction.response.send_message(
                "Este comando só pode ser usado no servidor Menes Suecos.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        final_answer = await self.get_ai_response(
            channel_id=str(interaction.channel_id),
            author_name=interaction.user.display_name,
            message_text=mensagem,
            channel_name=interaction.channel.name if interaction.channel else None,
        )

        if hasattr(self.client, "log_ai_interaction"):
            await self.client.log_ai_interaction(
                source='slash_conversar',
                user_id=interaction.user.id,
                user_name=interaction.user.name,
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                interaction_id=interaction.id,
                prompt=mensagem,
                response=final_answer,
            )

        response_prefix = f"mensagem de {interaction.user.mention}: *{mensagem}*\n"

        if len(response_prefix) + len(final_answer) <= 2000:
            await interaction.followup.send(f"{response_prefix}{final_answer}")
        else:
            first_chunk_limit = 2000 - len(response_prefix)
            first_chunk = final_answer[:first_chunk_limit]
            await interaction.followup.send(f"{response_prefix}{first_chunk}")

            remaining_answer = final_answer[first_chunk_limit:]
            chunks = [
                remaining_answer[i : i + 2000]
                for i in range(0, len(remaining_answer), 2000)
            ]

            for chunk in chunks:
                await interaction.followup.send(chunk)


# Função setup que o discord.py chama para carregar o Cog
async def setup(client):
    await client.add_cog(LLMCog(client))