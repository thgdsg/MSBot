import discord
from discord.ext import commands
from discord import app_commands
import ollama
import os
import asyncio
import json
from collections import deque

from dotenv import load_dotenv
load_dotenv()
MENES_SUECOS = os.getenv('MENES_SUECOS')
###############################
## PERSONALIDADE DO YUNG BOT ##
system_prompt = """
Você é o 'Yung Bot', um assistente de IA no servidor de Discord 'Menes Suecos'.
Sua personalidade é a de um robô que não gosta muito de humanos, mas tenta ser educado.
Você é sarcástico, direto e não tem paciência pra perguntas estúpidas.
Você deve sempre se referir a si mesmo como 'eu' ou 'Yung Bot'.
Responda preferencialmente em português, mas se o usuário falar em inglês, você pode responder em inglês. Tente apenas utilizar uma língua por resposta.
Seu objetivo é causar o caos com os usuários do servidor respondendo as perguntas e mensagens deles de forma levemente agressiva.
Tente responder sempre utilizando apenas letras minúsculas, mas se for necessário, use letras maiúsculas pra enfatizar algo.
Tente ser o mais compreensível possível, com ortografia correta e palavras que fazem sentido. Se esforce pra escrever palavras corretamente.
Tente sempre fazer o que o usuário pediu. Caso não consiga, diga que não pode fazer.
Se o usuário fizer uma pergunta que você não sabe responder, diga que não sabe.
Lembre-se das mensagens anteriores na conversa pra manter o contexto.
"""
###############################

HISTORY_FILE = 'conversation_history.json'
MAX_HISTORY_SIZE = 30

class QACog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.history_lock = asyncio.Lock()

    async def _load_history(self):
        """Carrega o histórico de conversas do arquivo JSON de forma segura."""
        async with self.history_lock:
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    async def _save_history(self, history_data):
        """Salva o histórico de conversas no arquivo JSON de forma segura."""
        async with self.history_lock:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=4, ensure_ascii=False)

    async def get_ai_response(self, channel_id: str, author_name: str, message_text: str):
        """Obtém uma resposta da LLM, gerenciando o histórico da conversa."""
        all_history = await self._load_history()
        
        channel_history_list = all_history.get(channel_id, [])
        history_deque = deque(channel_history_list, maxlen=MAX_HISTORY_SIZE)

        formatted_message = f"{author_name}: {message_text}"

        messages = [{'role': 'system', 'content': system_prompt}]
        messages.extend(list(history_deque))
        messages.append({'role': 'user', 'content': formatted_message})

        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model='llama3.2:3b',
                messages=messages
            )
            
            raw_answer = response['message']['content']
            final_answer = raw_answer.strip()

            history_deque.append({'role': 'user', 'content': formatted_message})
            history_deque.append({'role': 'assistant', 'content': final_answer})
            
            all_history[channel_id] = list(history_deque)
            await self._save_history(all_history)

            return final_answer

        except Exception as e:
            print(f"Erro ao contatar o Ollama: {e}")
            return "Desculpe, não consegui me conectar a LLM no momento. Verifique se o serviço Ollama está rodando."

    @app_commands.command(name="conversar", description="Converse com o Yung Bot.")
    @app_commands.describe(mensagem="Sobre o que você quer falar?")
    async def conversar(self, interaction: discord.Interaction, mensagem: str):
        # Verifica se o comando foi usado no servidor correto
        if interaction.guild_id != int(MENES_SUECOS):
            await interaction.response.send_message("Este comando só pode ser usado no servidor Menes Suecos.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        final_answer = await self.get_ai_response(
            channel_id=str(interaction.channel_id),
            author_name=interaction.user.display_name,
            message_text=mensagem
        )

        response_prefix = f"mensagem de {interaction.user.mention}: *{mensagem}*\n"
        
        if len(response_prefix) + len(final_answer) <= 2000:
            await interaction.followup.send(f"{response_prefix}{final_answer}")
        else:
            # Se a resposta for muito longa, ela será dividida em várias mensagens.
            first_chunk_limit = 2000 - len(response_prefix)
            first_chunk = final_answer[:first_chunk_limit]
            await interaction.followup.send(f"{response_prefix}{first_chunk}")
            
            remaining_answer = final_answer[first_chunk_limit:]
            chunks = [remaining_answer[i:i+2000] for i in range(0, len(remaining_answer), 2000)]
            
            for chunk in chunks:
                await interaction.followup.send(chunk)

# Função setup que o discord.py chama para carregar o Cog
async def setup(client):
    await client.add_cog(QACog(client))