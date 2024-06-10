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
propaganda = 0
propaganda_max = 20
reaction_max = 3
palavrasMax = 50
mensagem_block = False
trocaPalavra = True
permissoesOriginais = None
opcoes_propaganda = {
    "# Entre no melhor servidor de todos! \n<https://discord.gg/gou>" : "images/gou.jpg",
    "# Não perca! \nPromoções todo dia na <https://amazon.com.br>" : "images/amazon.jpg",
    "# Nova season de Fortnite em breve! \nBaixe grátis em <https://fortnite.com>" : "images/fortnite.jpg",
    "# Siga a página nas redes sociais! \n<https://youtube.com/@MENESSUECOSS>\n<https://web.facebook.com/MenesSuecos>\n<https://www.instagram.com/mene.sueco>" : "images/menes_suecos.png",
    "# Quer aprender a programar? \nAcesse <https://www.codecademy.com> e comece agora!" : "images/codecademy.png",
    "# Ouçam o novo álbum da Taylor Swift, a rainha do pop! \nhttps://open.spotify.com/album/5H7ixXZfsNMGbIE5OBSpcb?si=AcDe8Oy7QSSNSVN2U170UA" : "images/taylor_swift.jpg",
    "# Hora de acordar quarentena! \n<@&1194720159416467527> <@&1194723205022232637>" : "images/acorda.png",
    "# Quer aprender a desenhar? \nAcesse <https://www.skillshare.com> e comece agora!" : "images/skillshare.jpg",
    "# Crie uma conta na melhor rede social! \n<https://tiktok.com>" : "images/tiktok.png",
    "# Precisa de um adestrador de cães? Não se preocupe! Sérgio Moro está aqui pra você!\n<https://www.sergiomoro.com.br>" : "images/sergio_moro.jpg",
    "# Você é furry? Pare imediatamente e busque ajuda! \n<https://www.bible.com/pt>" : "images/psicologo.jpg",
    "# ليكن الله معك \n<https://www.islamreligion.com>" : "images/islam.jpg",
    "# O jogo do tigrinho tá bugado e pagando muito! \nEntre no meu link em <https://discord.gg/gou>" : "images/tigrinho.png",
    "# hagi łagi idzie po ciebie..." : "images/huggywuggy.jpg",
    "# Seja legal com seus amiguinhos!" : "images/brothers.jpg",
    "# O melhor jogo mobile e para computador dos últimos tempos! \nJogue RAID: Shadow Legends no meu link e inicie com 10000 de ouro! <https://store.steampowered.com/app/2333480/RAID_Shadow_Legends/>" : "images/raid.jpg",
    "# World of Tanks é o jogo mais fiel de tanque do mercado! \nEntre no meu link e ganhe 3 tanques por tempo limitado! <https://worldoftanks.com/pt-br/>" : "images/wot.jpg",
    "# Ajude tribos pequenas africanas a recuperarem sua economia! \nTodo centavo ajuda: <https://www.youtube.com/@SsethTzeentach>" : "images/sseth.jpg",
    "# Did you know that the critically acclaimed MMORPG Final Fantasy XIV has a free trial, and includes the entirety of A Realm Reborn AND the award-winning Stormblood expansion up to level 70 with no restrictions on playtime? \nSign up, and enjoy Eorzea today! <https://store.steampowered.com/app/39210/FINAL_FANTASY_XIV_Online/>" : "images/ffxiv.jpg",
    "# O jogo Subway Money está dando muitos ganhos! \nEntre no meu link e comece com R$5.00 de bônus! <https://discord.gg/gou>" : "images/subway.mp4",
    "# Have you seen this man in your dreams? \nHe will be in your dreams tonight." : "images/johnmers.png",
    "# Curta Menes Suecos no Facebook!" : "images/swedish.png",
    "# Não assine a TIM! \nEles são ruins e não prestam! 😠😠" : "images/tim.jpg",
    "# Vi sitter här i Venten och spelar lite Dota \n<https://www.dota2.com/home>" : "images/dota.jpg"
}
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

# Subrotina para enviar uma propaganda no chat
async def sendAd(message, bloqueiachat, escolha = None, interaction = None):
    global propaganda, mensagem_block, opcoes_propaganda, permissoesOriginais
    if interaction:
        if mensagem_block:
            await mensagem_block.delete()
            await mensagem_block.channel.set_permissions(mensagem_block.guild.default_role, overwrite=permissoesOriginais)
            permissoesOriginais = None 
            mensagem_block = False
        if escolha == None:
                random_message, random_file = random.choice(list(opcoes_propaganda.items()))
        else:
            try:
                position = escolha - 1
                random_message, random_file = list(opcoes_propaganda.items())[position]
            except IndexError:
                random_message, random_file = random.choice(list(opcoes_propaganda.items()))
        sent_message = await interaction.channel.send(f"{random_message}", file=discord.File(random_file))
        if bloqueiachat == True:
            propaganda = 0
            print(f"Propaganda enviada, bloqueando chat")
            mensagem_block = sent_message
            permissoesOriginais = interaction.channel.overwrites_for(interaction.guild.default_role)
            await sent_message.add_reaction("✅")  # Add a "✅" reaction to the message
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)  # Remove everyone's permissions to send messages in the channel
            await interaction.response.send_message("Propaganda enviada, bloqueando o chat", ephemeral=True)
        else:
            await interaction.response.send_message("Propaganda enviada", ephemeral=True)
    else:
        if mensagem_block:
            await mensagem_block.delete()
            await mensagem_block.channel.set_permissions(mensagem_block.guild.default_role, overwrite=permissoesOriginais)
            permissoesOriginais = None 
            mensagem_block = False
            
        random_message, random_file = random.choice(list(opcoes_propaganda.items()))
        sent_message = await message.channel.send(f"{random_message}", file=discord.File(random_file))
        propaganda = 0
        print(f"Propaganda enviada, bloqueando chat")
        mensagem_block = sent_message
        permissoesOriginais = message.channel.overwrites_for(message.guild.default_role)
        await sent_message.add_reaction("✅")  # Add a "✅" reaction to the message
        await message.channel.set_permissions(message.guild.default_role, send_messages=False)  # Remove everyone's permissions to send messages in the channel

@tree.command(name = "novapalavra", description="[ADM] Busca uma nova palavra aleatória no dicionário")
async def novapalavra(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global contador
        contador = 0
        await getNewWord()
        await interaction.response.send_message(palavraMute, ephemeral=True)
        print(f"Motivo: comando novapalavra")
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "redefinepalavra", description="[ADM] Coloca a palavra atual como NULL, nenhuma palavra dará timeout")
async def redefinepalavra(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavraMute
        palavraMute = None
        print("A palavra escolhida foi redefinida\n Motivo: comando redefinepalavra")
        await interaction.response.send_message("palavraMute foi redefinida (Use o comando /novapalavra novamente)", ephemeral=True)
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "mostrapalavra", description="[ADM] Mostra a palavra atual que dá timeout")
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

@tree.command(name = "escolhepalavra", description="[ADM] Define manualmente a palavra que causa timeout")
async def escolhepalavra(interaction: discord.Interaction, novapalavra: str):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavraMute
        palavraMute = novapalavra
        await interaction.response.send_message(f"{palavraMute} é a nova palavra que dá timeout", ephemeral=True)
        print(f"A palavra escolhida foi definida manualmente e agora é {palavraMute}")
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "escolhenummensagens", description="[ADM] Define o número de mensagens lidas para redefinir a palavra que da timeout")
async def escolhenummensagens(interaction: discord.Interaction, numeromensagens: int):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavrasMax
        palavrasMax = numeromensagens
        await interaction.response.send_message(f"Agora o bot vai trocar de palavra a cada {palavrasMax} mensagens", ephemeral=True)
        print(f"Número de mensagens para trocar a palavra redefinido para {palavrasMax}")
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name = "mantempalavra", description="[ADM] Liga/Desliga a função de trocar palavra ao ler um número X de mensagens")
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

@tree.command(name = "mudaconfigpropaganda", description="[ADM] Muda configurações da propaganda")
async def mudaconfigpropaganda(interaction: discord.Interaction, numeromsgslidas: int, numeroreacoes: int):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global propaganda_max, reaction_max
        propaganda_max = numeromsgslidas
        reaction_max = numeroreacoes
        await interaction.response.send_message(f"Configurações de propaganda alteradas para {propaganda_max} mensagens lidas e {reaction_max} reações", ephemeral=True)
        print(f"Configurações de propaganda alteradas para {propaganda_max} mensagens lidas e {reaction_max} reações")
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

# meme command
@tree.command(name = "enviapropaganda", description="[ADM] Envia uma propaganda no chat")
async def enviapropaganda(interaction: discord.Interaction, bloqueiachat: bool, escolha: int = None):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        await sendAd(None, bloqueiachat, escolha, interaction)

@tree.command(name = "desbloqueiachat", description="[ADM] Desbloqueia o chat e reseta propaganda")
async def desbloqueiachat(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global mensagem_block
        if mensagem_block:
            await mensagem_block.delete()
            await mensagem_block.channel.set_permissions(mensagem_block.guild.default_role, send_messages=True) 
            mensagem_block = False
            print(f"Chat desbloqueado")
            await interaction.response.send_message("Chat desbloqueado com sucesso", ephemeral=True)
        else:
            await interaction.response.send_message("O chat já está desbloqueado", ephemeral=True)

@tree.command(name = "bloqueiachat", description="[ADM] Bloqueia o chat")
async def bloqueiachat(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        if interaction.channel.permissions_for(interaction.guild.default_role).send_messages == True:
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False) 
            print(f"Chat bloqueado")
            await interaction.response.send_message("Chat bloqueado com sucesso", ephemeral=True)
        else:
            await interaction.response.send_message("O chat já está bloqueado", ephemeral=True)

# meme command
@tree.command(name = "mensagemdivina", description="[ADM] Mensagem dos deuses inspirada no TempleOS")
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
    global palavrasMax, propaganda, mensagem_block, propaganda_max, opcoes_propaganda, permissoesOriginais
    if client.user.id != message.author.id:
        global trocaPalavra, contador
        if palavraMute != None and palavraMute in str.lower(message.content):
            server = client.get_guild(int(MENES_SUECOS))

            member = await server.fetch_member(message.author.id)

            duration = timedelta(days = 0, hours = 0, minutes = 5, seconds = 0)
            if member.guild_permissions.moderate_members:
                print(f"User {message.author.name} com permissão de ADM falou a palavra proibida")
                await message.channel.send(f"Sem graça, o ADM falou a palavra proibida...")
                if trocaPalavra == True:
                    await getNewWord()
                    print(f"Motivo: Falaram a palavra proibida")
            else:
                print(f"User {message.author.name} foi mutado")
                await member.timeout(duration, reason="Falou a palavra proibida do dia")
                contador = 0
                if trocaPalavra == True:
                    await message.channel.send(f"Parabéns! Você falou a palavra proibida do dia! A palavra é: {palavraMute}\nSeu prêmio é {duration} de Timeout!\nA palavra foi redefinida")
                    await getNewWord()
                    print(f"Motivo: Falaram a palavra proibida")
                else:
                    await message.channel.send(f"Parabéns! Você falou a palavra proibida do dia! A palavra é: {palavraMute}\nSeu prêmio é {duration} de Timeout!")
        else:
            contador += 1
            propaganda += 1
            if contador >= palavrasMax and trocaPalavra == True:
                await getNewWord()
                print(f"Motivo: atingiu {palavrasMax} mensagens sem a palavra")
                contador = 0
            if propaganda >= propaganda_max:
                await sendAd(message, True)


@client.event
async def on_reaction_add(reaction, user):
    global mensagem_block, reaction_max, permissoesOriginais
    react_message = reaction.message
    if react_message == mensagem_block:
        mensagem_block = await react_message.channel.fetch_message(react_message.id)
        for reaction in mensagem_block.reactions:
            if reaction.count >= reaction_max:
                print(f'Reaction: {reaction.emoji} | Count: {reaction.count} | Deletando mensagem de propaganda e liberando chat')
                await mensagem_block.delete()
                await mensagem_block.channel.set_permissions(mensagem_block.guild.default_role, overwrite=permissoesOriginais)
                permissoesOriginais = None 
                mensagem_block = False
                break
    else:
        pass

client.run(TOKEN)

