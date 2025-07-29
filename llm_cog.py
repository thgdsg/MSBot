import discord
from discord.ext import commands
from discord import app_commands
import ollama
import os
import asyncio

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
Tente ser o mais compreensível possível, com ortografia correta e palavras que fazem sentido.
Tente sempre fazer o que o usuário pediu. Caso não consiga, diga que não pode fazer.
Se o usuário fizer uma pergunta que você não sabe responder, diga que não sabe.
"""
###############################

class QACog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @app_commands.command(name="conversar", description="Converse com o Yung Bot.")
    @app_commands.describe(mensagem="Sobre o que você quer falar?")
    async def conversar(self, interaction: discord.Interaction, mensagem: str):
        # Verifica se o comando foi usado no servidor correto
        if interaction.guild_id != int(MENES_SUECOS):
            await interaction.response.send_message("Este comando só pode ser usado no servidor Menes Suecos.", ephemeral=True)
            return

        # Defer a resposta, pois a LLM pode demorar para responder
        # Mostra "O bot está pensando..." pro usuário.
        await interaction.response.defer(thinking=True)

        try:
            # Executa a chamada síncrona da LLM em uma thread separada para não bloquear o bot
            response = await asyncio.to_thread(
                ollama.chat,
                model='llama3.2:3b',
                messages=[
                    {
                        'role': 'system',
                        'content': system_prompt,
                    },
                    {
                        'role': 'user',
                        'content': mensagem,
                    },
                ]
            )
            
            # Pega o conteúdo bruto da resposta da LLM
            raw_answer = response['message']['content']

            # A resposta da LLM é usada diretamente
            final_answer = raw_answer.strip()

            # Formata a resposta para marcar o usuário e enviar como texto simples.
            # O limite de caracteres de uma mensagem do Discord é 2000.
            response_prefix = f"mensagem de {interaction.user.mention}: *{mensagem}*\n"
            
            # Verifica se a resposta inteira cabe em uma única mensagem
            if len(response_prefix) + len(final_answer) <= 2000:
                await interaction.followup.send(f"{response_prefix}{final_answer}")
            else:
                # Se a resposta for muito longa, ela será dividida em várias mensagens.
                # Envia a primeira parte com a menção do usuário.
                first_chunk_limit = 2000 - len(response_prefix)
                first_chunk = final_answer[:first_chunk_limit]
                await interaction.followup.send(f"{response_prefix}{first_chunk}")
                
                # Envia o resto da resposta em pedaços de 2000 caracteres.
                remaining_answer = final_answer[first_chunk_limit:]
                chunks = [remaining_answer[i:i+2000] for i in range(0, len(remaining_answer), 2000)]
                
                for chunk in chunks:
                    # As mensagens seguintes são enviadas sem a menção.
                    await interaction.followup.send(chunk)

        except Exception as e:
            # Em caso de erro (ex: servidor Ollama não está rodando), envia uma mensagem de erro
            print(f"Erro ao contatar o Ollama: {e}")
            await interaction.followup.send("Desculpe, não consegui me conectar a LLM no momento. Verifique se o serviço Ollama está rodando.", ephemeral=True)

# Função setup que o discord.py chama para carregar o Cog
async def setup(client):
    await client.add_cog(QACog(client))