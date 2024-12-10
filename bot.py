# bot.py
import os
import discord
import random
import string
import sqlite3
import pytz

from datetime import datetime, time, timedelta
from python_pt_dictionary import dictionary
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import tasks
import asyncio

load_dotenv()
# Variáveis globais
alfabeto = list(string.ascii_lowercase)
palavraMute = None
contador = 0
propaganda = 0
propaganda_max = 50
reaction_max = 3
palavrasMax = 50
mensagem_block = False
trocaPalavra = True
permissoesOriginais = None
flagFirst = True
lock = asyncio.Lock()
ignorar_omd = False
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
    # total de 24 propagandas
}

def get_top_users_from_db(mn, mx):
    conn = sqlite3.connect('discord_bot.db')
    c = conn.cursor()
    c.execute('SELECT username, first_count FROM users ORDER BY first_count DESC LIMIT ? OFFSET ?', (mx - mn, mn))
    result = c.fetchall()
    conn.close()
    return result

class SimpleView(discord.ui.View):
    def __init__(self, user_id, timeout=10):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.message = None
        self.mn = 0
        self.mx = 10

    async def on_timeout(self) -> None:
        if self.message:
            for i in self.children:
                i.disabled = True
            await self.message.edit(view=self)

    @discord.ui.button(label="previous", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return

        if self.mx != 10:
            self.mn -= 10
            self.mx -= 10
            response = get_top_users_from_db(self.mn, self.mx)
            formatted_response = "\n".join([f"{self.mn + index + 1}. {username}: {count}" for index, (username, count) in enumerate(response)])
            if self.message:
                await self.message.edit(content=formatted_response)
        await interaction.response.defer()

    @discord.ui.button(label="next", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return

        conn = sqlite3.connect('discord_bot.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users')
        total_count = c.fetchone()[0]
        conn.close()

        if total_count >= self.mx + 1:
            self.mn += 10
            self.mx += 10
            response = get_top_users_from_db(self.mn, self.mx)
            formatted_response = "\n".join([f"{self.mn + index + 1}. {username}: {count}" for index, (username, count) in enumerate(response)])
            if self.message:
                await self.message.edit(content=formatted_response)
        await interaction.response.defer()

def setup_database():
    conn = sqlite3.connect('discord_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY, username TEXT, first_count INTEGER)''')
    conn.commit()
    conn.close()

def update_user(user_id, username):
    conn = sqlite3.connect('discord_bot.db')
    c = conn.cursor()

    # Verifica se o usuário já existe no banco de dados
    c.execute('SELECT first_count FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()

    if result:
        # Se o usuário já existe, incrementa o contador
        new_count = result[0] + 1
        c.execute('UPDATE users SET first_count = ?, username = ? WHERE user_id = ?', (new_count, username, user_id))
    else:
        # Se o usuário não existe, insere um novo registro
        c.execute('INSERT INTO users (user_id, username, first_count) VALUES (?, ?, ?)', (user_id, username, 1))

    print(f"Contagem de 'first' atualizada para o usuário {username} ({user_id}), agora ele possui {new_count} firsts")
    conn.commit()
    conn.close()

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
        print("Conectado ao Discord")
        setup_database()
        self.reset_flag.start()  # Inicia o loop pra resetar a flag

    @tasks.loop(hours=24)
    async def reset_flag(self):
        # Roda meia-noite 00:00
        print("Meia-noite, resetando variável flagFirst e tirando o cargo do membro que tiver o cargo 'first'")
        global flagFirst
        flagFirst = False
        guild = self.get_guild(int(MENES_SUECOS))  
        if guild is not None:
            role = discord.utils.get(guild.roles, name="first") 
            if role is not None:
                # Tira o cargo 'first' de todos os membros que possuem (idealmente só 1)
                for member in guild.members:  
                    if role in member.roles:  
                        print(f"Someone has the {role.name} role. Removing the role from {member.name}")
                        await member.remove_roles(role)  
                        break

    @reset_flag.before_loop
    async def before_reset_flag(self):
        # Espera até meia-noite
        now = datetime.now()
        midnight = datetime.combine(now + timedelta(days=1), time(0, 0))
        print("Loop pronto, esperando até meia-noite")
        await discord.utils.sleep_until(midnight)

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
# Default: recebe uma mensagem e True no bloqueiachat, mas funciona também com uma interação (comando)
async def sendAd(message, bloqueiachat, escolha = None, interaction = False):
    global propaganda, mensagem_block, opcoes_propaganda, permissoesOriginais, ignorar_omd
    if interaction:
        if mensagem_block:
            ignorar_omd = True
            await mensagem_block.delete()
            ignorar_omd = False
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
            await sent_message.add_reaction("✅")  # "✅" reaction
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)  # Remove everyone's permissions to send messages in the channel
            await interaction.response.send_message("Propaganda enviada, bloqueando o chat", ephemeral=True)
        else:
            await interaction.response.send_message("Propaganda enviada", ephemeral=True)
    else:
        if mensagem_block:
            ignorar_omd = True                
            await mensagem_block.channel.set_permissions(mensagem_block.guild.default_role, overwrite=permissoesOriginais)
            await mensagem_block.delete()
            ignorar_omd = False
            permissoesOriginais = None 
            mensagem_block = False

        random_message, random_file = random.choice(list(opcoes_propaganda.items()))
        sent_message = await message.channel.send(f"{random_message}", file=discord.File(random_file))
        propaganda = 0
        print(f"Propaganda enviada, bloqueando chat")
        mensagem_block = sent_message
        permissoesOriginais = message.channel.overwrites_for(message.guild.default_role)
        await sent_message.add_reaction("✅")  # "✅" reaction
        await message.channel.set_permissions(message.guild.default_role, send_messages=False)  # Remove everyone's permissions to send messages in the channel

@tree.command(name = "reset", description="[ADM] Reseta todas variaveis do bot")
async def reset(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global palavraMute, contador, propaganda, mensagem_block, permissoesOriginais, flagFirst, trocaPalavra
        palavraMute = None
        mensagem_block = False
        permissoesOriginais = None
        flagFirst = True
        trocaPalavra = True
        print("Variáveis resetadas")
        await interaction.response.send_message("Variáveis resetadas", ephemeral=True)
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

##################################
# COMANDOS DA PALAVRA ALEATÓRIA
##################################

@tree.command(name = "novapalavra", description="[ADM] Torna uma nova palavra aleatória a palavra proibida")
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

##################################
# COMANDOS DE PROPAGANDA
##################################

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

@tree.command(name = "enviapropaganda", description="[ADM] Envia uma propaganda no chat")
async def enviapropaganda(interaction: discord.Interaction, bloqueiachat: bool, escolha: int = None):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        await sendAd(None, bloqueiachat, escolha, interaction)

@tree.command(name = "desbloqueiachat", description="[ADM] Desbloqueia o chat e reseta propaganda")
async def desbloqueiachat(interaction: discord.Interaction):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        global mensagem_block, permissoesOriginais, ignorar_omd
        if mensagem_block:
            ignorar_omd = True
            await mensagem_block.delete()
            ignorar_omd = False
            if permissoesOriginais != None:
                await mensagem_block.channel.set_permissions(mensagem_block.guild.default_role, overwrite=permissoesOriginais)
                permissoesOriginais = None 
            print(f"Chat desbloqueado")
            mensagem_block = False
            await interaction.response.send_message("Chat desbloqueado com sucesso", ephemeral=True)
        elif interaction.channel.permissions_for(interaction.guild.default_role).send_messages == False:
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
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

###############################
# códigos do artur vitor
###############################

MUTE_ROLE_ID = 1194719392085332038  # ID do cargo melhores membros
LOG_CHANNEL_ID = 1194708101652303882  # ID do canal punições
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
from discord.utils import get
import re

def parse_duration(duration: str) -> int:
    match = re.match(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', duration)
    if not match:
        return 0
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds

def format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    duration_parts = []
    if hours > 0:
        duration_parts.append(f"{hours} horas")
    if minutes > 0:
        duration_parts.append(f"{minutes} minutos")
    if seconds > 0:
        duration_parts.append(f"{seconds} segundos")
    return ", ".join(duration_parts)

@tree.command(name = "enviarmsg", description= "[ADM] Faz o Yung Bot enviar uma mensagem no chat")
async def enviarmsg(interaction: discord.Interaction, mensagemescrita: str):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        print(f"Comando enviarmsg utilizado")
        await interaction.response.send_message("Mensagem enviada", ephemeral=True)
        await interaction.channel.send(mensagemescrita)
    else: 
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name="respondermsg", description="[ADM] Faz o Yung Bot responder uma mensagem específica")
async def respondermsg(interaction: discord.Interaction, mensagem_id: str, resposta: str):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        try:
            mensagem = await interaction.channel.fetch_message(int(mensagem_id))
            await interaction.response.send_message("Resposta enviada", ephemeral=True)
            await mensagem.reply(resposta)
            print(f"Comando respondermsg utilizado {mensagem_id}")
        except ValueError:
            await interaction.response.send_message("ID da mensagem deve ser um número inteiro válido", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("Mensagem não encontrada", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Permissões insuficientes para responder a esta mensagem", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Ocorreu um erro ao tentar responder a mensagem: {e}", ephemeral=True)
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name="mutar", description="[ADM] Muta um membro por um tempo específico")
async def mutar(interaction: discord.Interaction, membro: discord.Member, duracao: str, motivo: str):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        mute_role = get(interaction.guild.roles, id=MUTE_ROLE_ID)
        if mute_role:
            duracao_segundos = parse_duration(duracao)
            if duracao_segundos == 0:
                await interaction.response.send_message("Duração inválida. Use o formato '1h30m20s'.", ephemeral=True)
                return

            await membro.add_roles(mute_role)
            duracao_formatada = format_duration(duracao_segundos)
            print(f"{membro} foi mutado por {duracao_formatada}. Motivo: {motivo}")
            
            log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"{membro.mention} foi mutado por {duracao_formatada}. Motivo: {motivo}")
            
            await interaction.channel.send(f"{membro.mention} foi mutado por {duracao_formatada}. Motivo: {motivo}")
            
            await asyncio.sleep(duracao_segundos)
            await membro.remove_roles(mute_role)
            print(f"{membro} foi desmutado após {duracao_formatada}.")
            
            if log_channel:
                await log_channel.send(f"{membro.mention} foi desmutado após {duracao_formatada}.")
        else:
            await interaction.response.send_message("Cargo de mute não encontrado.", ephemeral=True)
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

@tree.command(name="desmutar", description="[ADM] Desmuta um membro")
async def desmutar(interaction: discord.Interaction, membro: discord.Member):
    if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
        mute_role = get(interaction.guild.roles, id=MUTE_ROLE_ID)
        if mute_role:
            await membro.remove_roles(mute_role)
            print(f"{membro} foi desmutado.")
            
            log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"{membro.mention} foi desmutado.")
            
            await interaction.response.send_message(f"{membro.mention} foi desmutado.", ephemeral=True)
        else:
            await interaction.response.send_message("Cargo de mute não encontrado.", ephemeral=True)
    else:
        await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

###############################
# fim dos códigos do artur vitor
###############################

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

@tree.command(name="adicionafirst", description="[ADM] Adiciona manualmente uma contagem de 'first' a um usuário.")
async def adicionafirst(interaction: discord.Interaction, user_id: str, count: int):
    if interaction.user.id == 93086555094159360:
        user = await client.fetch_user(user_id)
        conn = sqlite3.connect('discord_bot.db')
        c = conn.cursor()

        # Verifica se o usuário já existe no banco de dados
        c.execute('SELECT first_count FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()

        if result:
            # Se o usuário já existe, incrementa o contador
            new_count = result[0] + count
            c.execute('UPDATE users SET first_count = ? WHERE user_id = ?', (new_count, user_id))
            await interaction.response.send_message(f"Contagem atualizada! Novo total para o usuário {user_id}: {new_count}", ephemeral=True)
        else:
            # Se o usuário não existe, insere um novo registro
            c.execute('INSERT INTO users (user_id, username, first_count) VALUES (?, ?, ?)', (user_id, user.name, count))
            await interaction.response.send_message(f"Usuário {user_id} adicionado com {count} 'first'.", ephemeral=True)

        conn.commit()
        conn.close()

@tree.command(name="removefirst", description="[ADM] Remove manualmente uma contagem de 'first' de um usuário.")
async def removefirst(interaction: discord.Interaction, user_id: str, count: int):
    if interaction.user.id == 93086555094159360:
        user = await client.fetch_user(user_id)
        conn = sqlite3.connect('discord_bot.db')
        c = conn.cursor()

        # Verifica se o usuário já existe no banco de dados
        c.execute('SELECT first_count FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()

        if result:
            # Se o usuário já existe, decrementa o contador
            new_count = max(result[0] - count, 0)  # Garante que o contador não fique negativo
            c.execute('UPDATE users SET first_count = ? WHERE user_id = ?', (new_count, user_id))
            await interaction.response.send_message(f"Contagem atualizada! Novo total para o usuário {user_id}: {new_count}", ephemeral=True)
        else:
            # Se o usuário não existe, informa que não foi encontrado
            await interaction.response.send_message(f"Usuário {user_id} não encontrado no banco de dados.", ephemeral=True)

        conn.commit()
        conn.close()


@tree.command(name="top10first", description="Mostra o top 10 pessoas que já foram first.")
async def top10first(interaction: discord.Interaction):
    if interaction.guild_id == int(MENES_SUECOS):
        view = SimpleView(user_id=interaction.user.id, timeout=10)
        mn, mx = 0, 10
        response = get_top_users_from_db(mn, mx)
        formatted_response = "\n".join([f"{index + 1}. {username}: {count}" for index, (username, count) in enumerate(response)])

        await interaction.response.send_message(f"# HALL DA FAMA\n**Top 10 usuários com mais first:**\n{formatted_response}", view=view)
        message = await interaction.original_response()
        view.message = message
        view.mn = mn
        view.mx = mx
    elif interaction.guild_id == int(MENES_SUECOS):
        view = SimpleView(user_id=interaction.user.id, timeout=10)
        mn, mx = 0, 10
        response = get_top_users_from_db(mn, mx)
        formatted_response = "\n".join([f"{index + 1}. {username}: {count}" for index, (username, count) in enumerate(response)])

        await interaction.response.send_message(f"# HALL DA FAMA\n**Top 10 usuários com mais first:**\n{formatted_response}", view=view, ephemeral=True)
        message = await interaction.original_response()
        view.message = message
        view.mn = mn
        view.mx = mx

@tree.command(name="buscafirsts", description="Usando o nome do usuário ou apelido, busca a quantidade de firsts dele.")
async def buscausuario(interaction: discord.Interaction, username: str):
    if interaction.guild_id == int(MENES_SUECOS):
        guild = interaction.guild
        member = discord.utils.find(lambda m: m.display_name == username or m.name == username, guild.members)
        
        if member:
            conn = sqlite3.connect('discord_bot.db')
            c = conn.cursor()
            
            # Consulta o banco de dados pelo nome de usuário
            c.execute('SELECT username, first_count FROM users WHERE username = ?', (member.name,))
            result = c.fetchone()
            
            if result:
                # Se o usuário for encontrado, retorna o nome e a quantidade de 'firsts'
                found_username, first_count = result
                await interaction.response.send_message(f"Usuário: {found_username}\nQuantidade de 'firsts': {first_count}", ephemeral=True)
            else:
                # Se o usuário não for encontrado, informa que não foi encontrado
                await interaction.response.send_message(f"Usuário {username} não encontrado no banco de dados.", ephemeral=True)
            
            conn.close()
        else:
            await interaction.response.send_message(f"Usuário {username} não encontrado no servidor.", ephemeral=True)
    else:
        await interaction.response.send_message("Server não permitido", ephemeral=True)

@client.event
async def on_message(message):
    global palavrasMax, propaganda, mensagem_block, propaganda_max, opcoes_propaganda, permissoesOriginais, flagFirst, trocaPalavra, contador
    if client.user.id != message.author.id and message.channel.permissions_for(message.guild.default_role).send_messages == True:
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
                await member.timeout(duration, reason="Falou a palavra proibida")
                contador = 0
                if trocaPalavra == True:
                    await message.channel.send(f"Parabéns! Você falou a palavra proibida! A palavra é: {palavraMute}\nSeu prêmio é {duration} de Timeout!\nA palavra foi redefinida")
                    await getNewWord()
                    print(f"Motivo: Falaram a palavra proibida")
                else:
                    await message.channel.send(f"Parabéns! Você falou a palavra proibida! A palavra é: {palavraMute}\nSeu prêmio é {duration} de Timeout!")
        else:
            contador += 1
            propaganda += 1
            if contador >= palavrasMax and trocaPalavra == True:
                await getNewWord()
                print(f"Motivo: atingiu {palavrasMax} mensagens sem a palavra")
                contador = 0
            if propaganda >= propaganda_max:
                async with lock:
                    if isinstance(message.channel, discord.Thread):
                        return
                    if message.channel.id != 1194712146005737533:
                        await sendAd(message, True, None, False)
        
        # Define o fuso horário
        timezone = pytz.timezone('America/Sao_Paulo')

        # Obtém a data e hora atual no fuso horário especificado
        now = datetime.now(timezone)

        # Calcula a data de um dia atrás
        one_day_ago = now - timedelta(days=1)

        # Obtém apenas a data (sem a hora) de um dia atrás
        one_day_ago_date = one_day_ago.date()

        # Obtém apenas a data (sem a hora) da mensagem
        message_date = message.created_at.astimezone(timezone).date()

        async with lock:
            if flagFirst == False and "first" in str.lower(message.content) and message.channel.id == 1194706897345978450:
                if message_date != one_day_ago_date:
                    # Get the role
                    role = discord.utils.get(message.guild.roles, name="first")  # Replace with your role name
                    # Give the role to the user who sent the message
                    if role is not None:
                        await message.author.add_roles(role)
                        await message.channel.send(f"Parabéns {message.author.mention}, você foi o primeiro a falar 'first' hoje!")
                        flagFirst = True
                        user_id = str(message.author.id)
                        username = str(message.author.name)
                        update_user(user_id, username)
                        print(f"Ninguém tem o cargo {role.name}.\nO cargo {role.name} foi dado para {message.author}.")
        
        if message.mentions:
            for member in message.mentions:
                if member.id == int(TOJAO) and member.guild_permissions.moderate_members == False:
                    duration = timedelta(days = 0, hours = 0, minutes = 1, seconds = 0)
                    await member.timeout(duration, reason="Pingou o Tojão...")
                    await message.channel.send("NÃO. PINGUE. O. TOJÃO.")

@client.event
async def on_reaction_add(reaction, user):
    global mensagem_block, reaction_max, permissoesOriginais, ignorar_omd
    react_message = reaction.message
    async with lock:
        if react_message == mensagem_block:
            mensagem_block = await react_message.channel.fetch_message(react_message.id)
            for reaction in mensagem_block.reactions:
                if reaction.count >= reaction_max:
                    print(f'Reaction: {reaction.emoji} | Count: {reaction.count} | Deletando mensagem de propaganda e liberando chat')
                    ignorar_omd = True
                    await mensagem_block.delete()
                    ignorar_omd = False
                    await mensagem_block.channel.set_permissions(mensagem_block.guild.default_role, overwrite=permissoesOriginais)
                    permissoesOriginais = None 
                    mensagem_block = False
                    break

@client.event
async def on_message_delete(message):
    global mensagem_block, permissoesOriginais, ignorar_omd
    if ignorar_omd:
        return
    if mensagem_block:
        if message.author == client.user and message == mensagem_block:
            if permissoesOriginais != None:
                await mensagem_block.channel.set_permissions(mensagem_block.guild.default_role, overwrite=permissoesOriginais)
                permissoesOriginais = None 
                print(f"Chat desbloqueado")
            mensagem_block = False
            print("A mensagem que bloqueia o canal foi deletada, resetando permissões")

client.run(TOKEN)