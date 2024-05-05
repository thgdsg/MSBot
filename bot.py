# bot.py
import os
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
palavrasMax = 100
trocaPalavra = True
# Trocar caso necessário
TOKEN = os.getenv('DISCORD_TOKEN') # token do bot
TOJAO = os.getenv('TOJAO') # user id do tojao
MENES_SUECOS = os.getenv('MENES_SUECOS') # server id do server menes suecos

class aclient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.synced = False

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync()
            self.synced = True
        print("Connected to Discord")

client = aclient()
tree = app_commands.CommandTree(client)

# Subrotina para pegar uma palavra nova
async def getNewWord():
    novaPalavra = None
    newWord = None
    while newWord is None or not newWord:
        novaPalavra = random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto)
        for i in range(4):
            novaPalavra = novaPalavra.replace(random.choice(alfabeto), "")
        newWord = dictionary.select(novaPalavra, dictionary.Selector.PREFIX)
    indexAleatorio = random.randrange(len(newWord))
    global palavraMute 
    palavraMute = str.lower(newWord[indexAleatorio].text)
    print(f"Palavra foi trocada para: {palavraMute}")

@tree.command(name = "novapalavra", description="Busca uma nova palavra aleatória no dicionário")
async def novapalavra(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global contador
        contador = 0
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
async def escolhepalavra(interaction: discord.Interaction, novapalavra: str):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavraMute
        palavraMute = novapalavra
        await interaction.response.send_message(f"{palavraMute} é a nova palavra que dá timeout", ephemeral=True)
        print(f"A palavra escolhida foi definida manualmente e agora é {palavraMute}")
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "escolhenummensagens", description="Define o número de mensagens lidas para redefinir a palavra que da timeout")
async def escolhenumpalavras(interaction: discord.Interaction, numeropalavras: int):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavrasMax
        palavrasMax = numeropalavras
        await interaction.response.send_message(f"Agora o bot vai trocar de palavra a cada {palavrasMax} mensagens", ephemeral=True)
        print(f"Número de mensagens para trocar a palavra redefinido para {palavrasMax}")
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

@tree.command(name = "significado", description="Busca o significado de uma palavra")
async def significado(interaction: discord.Interaction, palavra: str):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        word = palavra.capitalize()
        mostraSignificado = dictionary.select(word, dictionary.Selector.PERFECT)
        if mostraSignificado.meaning != None:
            await interaction.response.send_message(f"{mostraSignificado.meaning}", ephemeral=False)
        else:
            await interaction.response.send_message(f"ERRO: Palavra inválida ou escrita errada (Dica: escreva a palavra com acento)", ephemeral=True)
    elif interaction.guild_id == int(MENES_SUECOS):
        word = palavra.capitalize()
        mostraSignificado = dictionary.select(word, dictionary.Selector.PERFECT)
        if mostraSignificado.meaning != None:
            await interaction.response.send_message(f"{mostraSignificado.meaning}", ephemeral=True)
        else:
            await interaction.response.send_message(f"ERRO: Palavra inválida ou escrita errada (Dica: escreva a palavra com acento)", ephemeral=True)
    else:
        await interaction.response.send_message("Server não permitido", ephemeral=True)

# meme command
@tree.command(name = "mensagemdivina", description="Mensagem dos deuses inspirada no TempleOS")
async def mensagemdivina(interaction: discord.Interaction, numeropalavras: int):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        fraseAleatoria = ""
        a = random.randint(0, 10000)
        for i in range(numeropalavras):
            a += 1
            random.seed(a)
            novaPalavra = None
            newWord = None
            while newWord is None or not newWord:
                novaPalavra = random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto) + random.choice(alfabeto)
                for i in range(4):
                    novaPalavra = novaPalavra.replace(random.choice(alfabeto), "")
                newWord = dictionary.select(novaPalavra, dictionary.Selector.PREFIX)
            indexAleatorio = random.randrange(len(newWord))
            fraseAleatoria = fraseAleatoria + " " + str.lower(newWord[indexAleatorio].text)
        print(f"Comando mensagemdivina utilizado")
        await interaction.response.send_message(f"{fraseAleatoria}", ephemeral=False)
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@client.event
async def on_message(message):
    global palavrasMax
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
                global contador
                contador = 0
                if trocaPalavra == True:
                    await message.channel.send(f"Parabéns! Você falou a palavra proibida do dia! A palavra é: {palavraMute}\nSeu prêmio é {duration} de Timeout!\nA palavra foi redefinida")
                    await getNewWord()
                    print(f"Motivo: Falaram a palavra")
                else:
                    await message.channel.send(f"Parabéns! Você falou a palavra proibida do dia! A palavra é: {palavraMute}\nSeu prêmio é {duration} de Timeout!")
        #elif TOJAO in message.content:
            #print(f"tojao pingado")
            #await message.channel.send(f"Mateus 5:48\nPortanto, sejam perfeitos como perfeito é o Pai celestial de vocês.\nnao pingue o tojao.")
            #contador += 1
            #if contador > palavrasMax and trocaPalavra == True:
                #await getNewWord()
                #print(f"Motivo: atingiu {palavrasMax} mensagens sem a palavra")
                #contador = 0
        else:
            contador += 1
            if contador >= palavrasMax and trocaPalavra == True:
                await getNewWord()
                print(f"Motivo: atingiu {palavrasMax} mensagens sem a palavra")
                contador = 0

client.run(TOKEN)

