import discord
from discord.ext import commands
from discord import app_commands
import random
import string
from python_pt_dictionary import dictionary
import os

MENES_SUECOS = os.getenv('MENES_SUECOS')

class PalavraCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.alfabeto = list(string.ascii_lowercase)

    async def getNewWord(self):
        """Gera uma nova palavra e a define como a palavra proibida no bot."""
        novaPalavra = None
        newWord = None
        while newWord is None or not newWord:
            novaPalavra = random.choice(self.alfabeto) + random.choice(self.alfabeto) + random.choice(self.alfabeto) + random.choice(self.alfabeto) + random.choice(self.alfabeto)
            for i in range(4):
                novaPalavra = novaPalavra.replace(random.choice(self.alfabeto), "")
            newWord = dictionary.select(novaPalavra, dictionary.Selector.PREFIX)
        indexAleatorio = random.randrange(len(newWord))
        self.client.palavraMute = str.lower(newWord[indexAleatorio].text)
        print(f"Palavra foi trocada para: {self.client.palavraMute}")

    @app_commands.command(name = "novapalavra", description="[ADM] Torna uma nova palavra aleatória a palavra proibida")
    async def novapalavra(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            self.client.contador = 0
            await self.getNewWord()
            await interaction.response.send_message(f"A nova palavra é: **{self.client.palavraMute}**", ephemeral=True)
            print(f"Motivo: comando novapalavra")
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name = "redefinepalavra", description="[ADM] Nenhuma palavra dará timeout")
    async def redefinepalavra(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            self.client.palavraMute = None
            print("A palavra escolhida foi redefinida\n Motivo: comando redefinepalavra")
            await interaction.response.send_message("palavraMute foi redefinida. Nenhuma palavra causará timeout.", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name = "mostrapalavra", description="[ADM] Mostra a palavra atual que dá timeout")
    async def mostrapalavra(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            if self.client.palavraMute is None:
                await interaction.response.send_message("Não tem nenhuma palavra atual que dá timeout", ephemeral=True)
            else:
                await interaction.response.send_message(f"**{self.client.palavraMute}** é a palavra atual que dá timeout", ephemeral=True)
                print(f"A palavra escolhida foi mostrada para {interaction.user.name}")
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name = "escolhepalavra", description="[ADM] Define manualmente a palavra que causa timeout")
    async def escolhepalavra(self, interaction: discord.Interaction, novapalavra: str):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            self.client.palavraMute = novapalavra.lower()
            await interaction.response.send_message(f"**{self.client.palavraMute}** é a nova palavra que dá timeout", ephemeral=True)
            print(f"A palavra escolhida foi definida manualmente e agora é {self.client.palavraMute}")
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name = "escolhenummensagens", description="[ADM] Define o número de mensagens para trocar a palavra")
    async def escolhenummensagens(self, interaction: discord.Interaction, numeromensagens: int):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            self.client.palavrasMax = numeromensagens
            await interaction.response.send_message(f"Agora o bot vai trocar de palavra a cada {self.client.palavrasMax} mensagens", ephemeral=True)
            print(f"Número de mensagens para trocar a palavra redefinido para {self.client.palavrasMax}")
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name = "mantempalavra", description="[ADM] Liga/Desliga a troca automática de palavra")
    async def mantempalavra(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            self.client.trocaPalavra = not self.client.trocaPalavra
            status = "LIGADO" if self.client.trocaPalavra else "DESLIGADO"
            print(f"Troca de palavra automática agora está {status}")
            await interaction.response.send_message(f"Troca de palavra automática agora está **{status}**", ephemeral=True)
        else:
            await interaction.response.send_message("Você não possui permissões suficientes", ephemeral=True)

    @app_commands.command(name = "significado", description="Busca o significado de uma palavra")
    async def significado(self, interaction: discord.Interaction, palavra: str):
        if interaction.guild_id == int(MENES_SUECOS):
            word = palavra.capitalize()
            mostraSignificado = dictionary.select(word, dictionary.Selector.PERFECT)
            if mostraSignificado and mostraSignificado.meaning is not None:
                await interaction.response.send_message(f"**{palavra.capitalize()}:**\n{mostraSignificado.meaning}", ephemeral=False)
            else:
                await interaction.response.send_message(f"ERRO: Palavra inválida ou escrita errada (Dica: escreva a palavra com acento)", ephemeral=True)
        else:
            await interaction.response.send_message("Server não permitido", ephemeral=True)

async def setup(client):
    await client.add_cog(PalavraCog(client))
