# bot.py
import os
import discord
import random
import string
import sqlite3
import pytz
import asyncio
import json

from datetime import datetime, time, timedelta
from dotenv import load_dotenv
from discord.ext import commands, tasks

load_dotenv()

# Carregando variáveis de ambiente
TOKEN = os.getenv('DISCORD_TOKEN')
TOJAO = os.getenv('TOJAO')
MENES_SUECOS = os.getenv('MENES_SUECOS')
LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID')

LOG_FILE = 'logs.json'

def setup_database():
    """Configura o banco de dados inicial."""
    conn = sqlite3.connect('discord_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (user_id TEXT PRIMARY KEY, username TEXT, first_count INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS first_logs
                (log_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, username TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

def update_user_first_count(user_id, username):
    """Atualiza a contagem de 'first' para um usuário no banco de dados."""
    conn = sqlite3.connect('discord_bot.db')
    c = conn.cursor()
    c.execute('SELECT first_count FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result:
        new_count = result[0] + 1
        c.execute('UPDATE users SET first_count = ?, username = ? WHERE user_id = ?', (new_count, username, user_id))
    else:
        new_count = 1
        c.execute('INSERT INTO users (user_id, username, first_count) VALUES (?, ?, ?)', (user_id, username, new_count))
    print(f"Contagem de 'first' atualizada para {username} ({user_id}), total: {new_count}")
    conn.commit()
    conn.close()

def log_first_event(user_id, username, timestamp):
    """Registra o evento 'first' no log do banco de dados."""
    conn = sqlite3.connect('discord_bot.db')
    c = conn.cursor()
    c.execute('INSERT INTO first_logs (user_id, username, timestamp) VALUES (?, ?, ?)', (user_id, username, timestamp.isoformat()))
    conn.commit()
    conn.close()
    print(f"Log de 'first' registrado para {username} ({user_id}) em {timestamp.isoformat()}")

class YungBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.synced = False
        self.loaded_extensions = []

        # variáveis de estado do Bot
        self.alfabeto = list(string.ascii_lowercase)
        self.palavraMute = None
        self.contador = 0
        self.propaganda = 0
        self.propaganda_max = 50
        self.reaction_max = 3
        self.palavrasMax = 50
        self.mensagem_block = None
        self.trocaPalavra = True
        self.permissoesOriginais = None
        self.flagFirst = True
        self.ignorar_omd = False
        self.lock = asyncio.Lock()
        self.log_lock = asyncio.Lock()

        with open('propagandas.json', 'r', encoding='utf-8') as f:
            self.opcoes_propaganda = json.load(f)

    async def log_command(self, interaction: discord.Interaction):
        """Registra o uso de um comando em um arquivo JSON."""
        async with self.log_lock:
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                    if not isinstance(logs, list):
                        logs = []
            except (FileNotFoundError, json.JSONDecodeError):
                logs = []

            # Converte as opções do comando para um dicionário de strings
            options_dict = {}
            if interaction.data and 'options' in interaction.data:
                 for option in interaction.data.get('options', []):
                    options_dict[option['name']] = str(option['value'])

            new_log = {
                'timestamp': datetime.now().isoformat(),
                'user_id': interaction.user.id,
                'user_name': interaction.user.name,
                'command': interaction.command.name if interaction.command else 'unknown',
                'options': options_dict
            }

            logs.append(new_log)
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=4, ensure_ascii=False)

    async def setup_hook(self):
        """Carrega as extensões (cogs) e sincroniza os comandos."""
        # Adiciona o middleware de log
        self.tree.interaction_check = self.global_interaction_check

        extensions_to_load = [
            'llm_cog', 'palavra_cog', 'first_cog', 
            'caoticos_cog', 'propaganda_cog'
        ]
        
        for extension in extensions_to_load:
            if extension not in self.loaded_extensions:
                try:
                    await self.load_extension(extension)
                    self.loaded_extensions.append(extension)
                    print(f'Extensão {extension} carregada com sucesso.')
                except Exception as e:
                    print(f'Falha ao carregar a extensão {extension}.')
                    import traceback
                    traceback.print_exc()
        
        if not self.synced:
            try:
                await self.tree.sync()
                self.synced = True
                print("Árvore de comandos sincronizada.")
            except Exception as e:
                print(f"Falha ao sincronizar a árvore de comandos: {e}")

    async def global_interaction_check(self, interaction: discord.Interaction) -> bool:
        """Middleware global que é chamado antes de cada comando de app."""
        # Registra o comando
        await self.log_command(interaction)
        # Retorna True para permitir que o comando continue a ser executado
        return True

    async def on_ready(self):
        await self.wait_until_ready()
        print(f"Conectado ao Discord como {self.user}!")
        setup_database()
        self.reset_first_flag.start()

    @tasks.loop(time=time(0, 0, tzinfo=pytz.timezone('America/Sao_Paulo')))
    async def reset_first_flag(self):
        """Reseta a flag do 'first' e remove o cargo diariamente à meia-noite."""
        print("Meia-noite, resetando flag 'first' e removendo cargos.")
        self.flagFirst = False
        guild = self.get_guild(int(MENES_SUECOS))
        if guild:
            role = discord.utils.get(guild.roles, name="first")
            if role:
                for member in role.members:
                    await member.remove_roles(role)
                    print(f"Cargo 'first' removido de {member.name}")

client = YungBot()

@client.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None or str(message.guild.id) != MENES_SUECOS:
        return

    # processa comandos de texto (não tem nenhum)
    await client.process_commands(message)

    # Lógica da palavra proibida
    if client.palavraMute and client.palavraMute in message.content.lower():
        duration = timedelta(minutes=5)
        if not message.author.guild_permissions.moderate_members:
            await message.author.timeout(duration, reason="Falou a palavra proibida.")
            await message.channel.send(f"Parabéns, {message.author.mention}! Você falou a palavra proibida e ganhou um timeout de 5 minutos!")
            
            if client.trocaPalavra:
                palavra_cog = client.get_cog('PalavraCog')
                if palavra_cog:
                    await palavra_cog.getNewWord()
                    await message.channel.send("A palavra foi trocada.")
        else:
            await message.channel.send("O ADM sem graça falou a palavra proibida...")
            if client.trocaPalavra:
                palavra_cog = client.get_cog('PalavraCog')
                if palavra_cog:
                    await palavra_cog.getNewWord()

    # lógica de troca de palavra por contagem e propaganda
    if not client.mensagem_block:
        client.contador += 1
        client.propaganda += 1

        if client.trocaPalavra and client.contador >= client.palavrasMax:
            palavra_cog = client.get_cog('PalavraCog')
            if palavra_cog:
                await palavra_cog.getNewWord()
                client.contador = 0
                print(f"Palavra trocada por atingir {client.palavrasMax} mensagens.")

        if client.propaganda >= client.propaganda_max:
            propaganda_cog = client.get_cog('PropagandaCog')
            if propaganda_cog and not isinstance(message.channel, discord.Thread):
                # simula uma interação para reutilizar a função do cog
                mock_interaction = type('Interaction', (), {'channel': message.channel, 'guild': message.guild, 'user': client.user})
                await propaganda_cog.sendAd(mock_interaction, bloqueiachat=True)
                client.propaganda = 0

    # Lógica do first
    timezone = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(timezone)
    if not client.flagFirst and "first" in message.content.lower():
        async with client.lock:
            if not client.flagFirst: # checagem dupla pra evitar race condition
                client.flagFirst = True
                role = discord.utils.get(message.guild.roles, name="first")
                if role:
                    await message.author.add_roles(role)
                await message.channel.send(f"Parabéns {message.author.mention}, você foi o primeiro a falar 'first' hoje!")
                update_user_first_count(str(message.author.id), message.author.name)
                log_first_event(str(message.author.id), message.author.name, now)

    # Lógica de pingar o Tojão
    if int(TOJAO) in [m.id for m in message.mentions]:
        member = message.guild.get_member(int(TOJAO))
        if member and not member.guild_permissions.moderate_members:
            await message.author.timeout(timedelta(minutes=1), reason="Pingou o Tojão.")
            await message.channel.send("NÃO. PINGUE. O. TOJÃO.")

@client.event
async def on_reaction_add(reaction, user):
    if user.bot or not client.mensagem_block or reaction.message.id != client.mensagem_block.id:
        return

    if reaction.emoji == "✅" and reaction.count >= client.reaction_max:
        async with client.lock:
            if client.mensagem_block: # Verifica novamente após adquirir o lock
                print(f"Contagem de reações atingida. Desbloqueando chat.")
                channel = client.mensagem_block.channel
                try:
                    client.ignorar_omd = True
                    await client.mensagem_block.delete()
                except discord.NotFound:
                    pass # Mensagem já foi deletada
                finally:
                    client.ignorar_omd = False
                
                if client.permissoesOriginais is not None:
                    await channel.set_permissions(reaction.message.guild.default_role, overwrite=client.permissoesOriginais)
                
                client.mensagem_block = None
                client.permissoesOriginais = None

@client.event
async def on_message_delete(message):
    if client.ignorar_omd or not client.mensagem_block or message.id != client.mensagem_block.id:
        return

    print("Mensagem de bloqueio foi deletada, restaurando permissões.")
    if client.permissoesOriginais is not None:
        await message.channel.set_permissions(message.guild.default_role, overwrite=client.permissoesOriginais)
    
    client.mensagem_block = None
    client.permissoesOriginais = None

client.run(TOKEN)