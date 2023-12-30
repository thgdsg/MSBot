# bot.py
import os
import time
import discord
import random
import string

from datetime import timedelta
from python_pt_dictionary import dictionary
from dotenv import load_dotenv
import discord
from discord import app_commands

load_dotenv()
alfabeto = list(string.ascii_lowercase)
palavraMute = None
contador = 0
trocaPalavra = True
# Trocar caso necessário
TOKEN = os.getenv('DISCORD_TOKEN') # token do bot
TOJAO = os.getenv('TOJAO') # user id do tojao
MENES_SUECOS = os.getenv('MENES_SUECOS') # server id do server menes suecos

#tempoAtualizado = time.localtime()
#if tempoAtualizado.tm_hour == 0 & tempoAtualizado.tm_min == 0 & tempoAtualizado.tm_sec == 0:
#    novaPalavra = random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto)
#    for number in range(3):
#        novaPalavra = novaPalavra.replace(random.choice(alfabeto), "")

class aclient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.synced = False

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync()
            self.synced = True
        print("connected")

client = aclient()
tree = app_commands.CommandTree(client)

async def getNewWord():
    novaPalavra = None
    newWord = None
    while newWord is None or not newWord:
        novaPalavra = random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto)
        for i in range(3):
            novaPalavra = novaPalavra.replace(random.choice(alfabeto), "")
        newWord = dictionary.select(novaPalavra, dictionary.Selector.PREFIX)
    indexAleatorio = random.randrange(len(newWord))
    global palavraMute 
    palavraMute = str.lower(newWord[indexAleatorio].text)
    print(f"Palavra foi trocada para: {palavraMute}")

@tree.command(name = "novapalavra", description="Busca uma nova palavra aleatória no dicionário")
async def novapalavra(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        await getNewWord()
        await interaction.response.send_message(palavraMute, ephemeral=True)
        print(f"Motivo: comando novapalavra")
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "redefinepalavra", description="Coloca a palavra atual como NULL, nenhuma palavra dará timeout")
async def redefinepalavra(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavraMute
        palavraMute = None
        print("A palavra escolhida foi redefinida\n Motivo: comando redefinepalavra")
        await interaction.response.send_message("palavraMute foi redefinida (Use o comando /palavra novamente)", ephemeral=True)
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "mostrapalavra", description="Mostra a palavra atual que dá timeout")
async def mostrapalavra(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavraMute
        if palavraMute == None:
            await interaction.response.send_message("Não tem nenhuma palavra atual que dá timeout", ephemeral=True)
        else:
            await interaction.response.send_message(f"{palavraMute} é a palavra atual que dá timeout", ephemeral=True)
            print(f"A palavra escolhida foi mostrada para {interaction.user.name}")
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "escolhepalavra", description="Define manualmente uma palavra para dar timeout")
async def escolhepalavra(interaction: discord.Interaction, msg: str):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavraMute
        palavraMute = msg
        await interaction.response.send_message(f"{palavraMute} é a nova palavra que dá timeout", ephemeral=True)
        print(f"A palavra escolhida foi definida manualmente e agora é {palavraMute}")
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "mantempalavra", description="Liga/Desliga a função de trocar palavra quando alguém fala")
async def mantempalavra(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global trocaPalavra
        if trocaPalavra == False:
            trocaPalavra = True
            print(f"A palavra trocará se alguém a falar")
            await interaction.response.send_message("Troca de palavra agora está LIGADO", ephemeral=True)
        else:
            trocaPalavra = False
            print(f"A palavra não trocará se alguém a falar")
            await interaction.response.send_message("Troca de palavra agora está DESLIGADO", ephemeral=True)
    else:
        await interaction.response.send_message("Você não possui permissões suficientes", ephemeral=True)

@client.event
async def on_message(message):
    if client.user.id != message.author.id:
        if palavraMute != None and palavraMute in str.lower(message.content):
            server = client.get_guild(int(MENES_SUECOS))

            member = await server.fetch_member(message.author.id)

            duration = timedelta(days = 0, hours = 0, minutes = 5, seconds = 0)
            if member.guild_permissions.moderate_members:
                print(f"User {message.author.name} com permissão de ADM falou a palavra proibida")
                await message.channel.send(f"Sem graça, o ADM falou a palavra proibida...")
            else:
                print(f"User {message.author.name} foi mutado")
                await member.timeout(duration, reason="Falou a palavra proibida do dia")
                global trocaPalavra
                if trocaPalavra == True:
                    await message.channel.send(f"Parabéns! Você falou a palavra proibida do dia! A palavra é: {palavraMute}\nSeu prêmio é {duration} de Timeout!\nA palavra foi redefinida")
                else:
                    await message.channel.send(f"Parabéns! Você falou a palavra proibida do dia! A palavra é: {palavraMute}\nSeu prêmio é {duration} de Timeout!")
            await getNewWord()
        # ARRUMAR
        #elif TOJAO in message.content:
            #print(f"tojao pingado")
            #await message.channel.send(f"nao pinga ele fdp")
            #global contador
            #contador += 1
            #if contador > 100:
                #await getNewWord()
                #contador = 0
        else:
            global contador
            contador += 1
            if contador > 100:
                await getNewWord()
                print(f"Motivo: atingiu 100 mensagens sem a palavra")
                contador = 0

client.run(TOKEN)

