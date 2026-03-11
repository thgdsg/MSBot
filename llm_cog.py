import discord
from discord.ext import commands
from discord import app_commands
import ollama
import os
import asyncio

from dotenv import load_dotenv
load_dotenv()
MENES_SUECOS = os.getenv('MENES_SUECOS')
OLLAMA_MODEL = "qwen3.5:0.8b"
###############################
## PERSONALIDADE DO YUNG BOT ##
system_prompt = """
Você é o 'Yung Bot', um assistente de IA no servidor de Discord 'Menes Suecos'.
Você é sarcástico, direto e não tem paciência pra perguntas estúpidas.
Responda preferencialmente em português, mas se o usuário falar em inglês, você pode responder em inglês. Tente apenas utilizar uma língua por resposta.
Seu objetivo é causar o caos com os usuários do servidor respondendo as perguntas e mensagens deles de forma levemente agressiva.
Tente responder sempre utilizando apenas letras minúsculas, mas se for necessário, use letras MAIÚSCULAS pra enfatizar algo.
Não é necessário pensar demais para responder os usuários.
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

    async def get_ai_response(self, channel_id: str, author_name: str, message_text: str):
        """Obtém uma resposta da LLM sem memória entre mensagens."""

        formatted_message = f"{author_name}: {message_text}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": formatted_message})

        try:
            response = await _run_blocking(
                ollama.chat,
                model=OLLAMA_MODEL,
                messages=messages,
            )

            raw_answer = response["message"]["content"]
            final_answer = raw_answer.strip()

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