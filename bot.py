from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import string
from datetime import datetime, time, timedelta

import discord
import pytz
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
TOJAO = os.getenv("TOJAO")
MENES_SUECOS = os.getenv("MENES_SUECOS")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

LOG_FILE = "logs.json"
CONVERSATION_HISTORY_FILE = "conversation_history.json"
DATABASE_FILE = "discord_bot.db"
SAO_PAULO_TZ = pytz.timezone("America/Sao_Paulo")


def _load_json_file(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, type(default)) else default
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json_file(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def _append_json_log(path, entry):
    logs = _load_json_file(path, [])
    logs.append(entry)
    _write_json_file(path, logs)


def _open_database():
    return sqlite3.connect(DATABASE_FILE)


def setup_database():
    """Configura o banco de dados inicial."""
    with _open_database() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                first_count INTEGER
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS first_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                username TEXT,
                timestamp TEXT
            )
            """
        )


def update_user_first_count(user_id, username):
    """Atualiza a contagem de 'first' para um usuario no banco de dados."""
    with _open_database() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT first_count FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            new_count = result[0] + 1
            cursor.execute(
                "UPDATE users SET first_count = ?, username = ? WHERE user_id = ?",
                (new_count, username, user_id),
            )
        else:
            new_count = 1
            cursor.execute(
                "INSERT INTO users (user_id, username, first_count) VALUES (?, ?, ?)",
                (user_id, username, new_count),
            )

    print(f"Contagem de 'first' atualizada para {username} ({user_id}), total: {new_count}")


def log_first_event(user_id, username, timestamp):
    """Registra o evento 'first' no log do banco de dados."""
    with _open_database() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO first_logs (user_id, username, timestamp) VALUES (?, ?, ?)",
            (user_id, username, timestamp.isoformat()),
        )
    print(f"Log de 'first' registrado para {username} ({user_id}) em {timestamp.isoformat()}")


async def _resolve_referenced_bot_message(
    message: discord.Message,
    bot_user_id: int,
) -> str | None:
    if not message.reference or not message.reference.message_id:
        return None

    referenced_message = message.reference.resolved
    if not isinstance(referenced_message, discord.Message):
        try:
            referenced_message = await message.channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    if (
        isinstance(referenced_message, discord.Message)
        and referenced_message.author
        and referenced_message.author.id == bot_user_id
    ):
        return referenced_message.content

    return None


async def _send_chunked_reply(message: discord.Message, response: str) -> None:
    chunks = [response[index : index + 2000] for index in range(0, len(response), 2000)] or ["(sem conteudo)"]

    try:
        await message.reply(chunks[0])
    except discord.HTTPException as err:
        if err.code != 10008:
            raise
        print(
            f"Falha ao responder a mensagem {message.id} "
            "(provavelmente foi deletada). Enviando como nova mensagem."
        )
        await message.channel.send(f"{message.author.mention}, aqui esta sua resposta:\n{chunks[0]}")

    for chunk in chunks[1:]:
        await message.channel.send(chunk)


class MSBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.synced = False
        self.loaded_extensions = []

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
        self._first_reset_task: asyncio.Task | None = None

        self.opcoes_propaganda = _load_json_file("propagandas.json", [])

    @staticmethod
    def _extract_interaction_options(interaction: discord.Interaction) -> dict[str, str]:
        if not interaction.data or "options" not in interaction.data:
            return {}
        return {
            option["name"]: str(option["value"])
            for option in interaction.data.get("options", [])
        }

    def _seconds_until_next_midnight_sp(self) -> float:
        now = datetime.now(SAO_PAULO_TZ)
        next_day = (now + timedelta(days=1)).date()
        next_midnight = SAO_PAULO_TZ.localize(
            datetime.combine(next_day, time(0, 0, 0)),
            is_dst=None,
        )
        return max(0.0, (next_midnight - now).total_seconds())

    async def _do_first_reset(self) -> None:
        """Remove o cargo 'first' de todos e libera para o proximo 'first' do dia."""
        print("00:00 (SP), resetando flag 'first' e removendo cargos.")
        self.flagFirst = False

        try:
            _write_json_file(CONVERSATION_HISTORY_FILE, {})
            print("conversation_history.json foi limpo no reset diario.")
        except OSError as err:
            print(f"Falha ao limpar conversation_history.json no reset: {err}")

        guild = self.get_guild(int(MENES_SUECOS))
        if not guild:
            return

        role = discord.utils.get(guild.roles, name="first")
        if not role:
            return

        for member in list(role.members):
            try:
                await member.remove_roles(role)
                print(f"Cargo 'first' removido de {member.name}")
            except discord.Forbidden:
                print(f"Sem permissao para remover cargo de {member.name}")
            except discord.HTTPException as err:
                print(f"Falha ao remover cargo de {member.name}: {err}")

    async def _first_reset_scheduler(self) -> None:
        """Scheduler alinhado ao timezone: dorme ate o proximo 00:00 (SP), executa, repete."""
        await self.wait_until_ready()

        while not self.is_closed():
            delay = self._seconds_until_next_midnight_sp()
            print(f"Proximo reset do 'first' em ~{int(delay)}s (00:00 SP).")
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

            try:
                await self._do_first_reset()
            except Exception as err:
                print(f"Erro no reset do 'first': {err}")

    async def on_ready(self):
        await self.wait_until_ready()
        print(f"Conectado ao Discord como {self.user}!")
        setup_database()

        if self._first_reset_task is None or self._first_reset_task.done():
            self._first_reset_task = asyncio.create_task(self._first_reset_scheduler())

    async def log_command(self, interaction: discord.Interaction):
        """Registra o uso de um comando em um arquivo JSON."""
        async with self.log_lock:
            _append_json_log(
                LOG_FILE,
                {
                    "timestamp": datetime.now().isoformat(),
                    "user_id": interaction.user.id,
                    "user_name": interaction.user.name,
                    "command": interaction.command.name if interaction.command else "unknown",
                    "options": self._extract_interaction_options(interaction),
                },
            )

    async def log_ai_interaction(
        self,
        *,
        source: str,
        user_id: int,
        user_name: str,
        guild_id: int | None,
        channel_id: int | None,
        prompt: str,
        response: str,
        message_id: int | None = None,
        interaction_id: int | None = None,
    ):
        """Registra interacoes de IA."""
        async with self.log_lock:
            _append_json_log(
                LOG_FILE,
                {
                    "timestamp": datetime.now().isoformat(),
                    "type": "ai_interaction",
                    "source": source,
                    "user_id": user_id,
                    "user_name": user_name,
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "interaction_id": interaction_id,
                    "prompt": prompt,
                    "response": response,
                },
            )

    async def setup_hook(self):
        """Carrega as extensoes (cogs) e sincroniza os comandos."""
        self.tree.interaction_check = self.global_interaction_check

        extensions_to_load = [
            "llm_cog",
            "palavra_cog",
            "first_cog",
            "caoticos_cog",
            "propaganda_cog",
        ]

        for extension in extensions_to_load:
            if extension in self.loaded_extensions:
                continue
            try:
                await self.load_extension(extension)
                self.loaded_extensions.append(extension)
                print(f"Extensao {extension} carregada com sucesso.")
            except Exception:
                print(f"Falha ao carregar a extensao {extension}.")
                import traceback

                traceback.print_exc()

        if not self.synced:
            try:
                await self.tree.sync()
                self.synced = True
                print("Arvore de comandos sincronizada.")
            except Exception as err:
                print(f"Falha ao sincronizar a arvore de comandos: {err}")

    async def global_interaction_check(self, interaction: discord.Interaction) -> bool:
        await self.log_command(interaction)
        return True


client = MSBot()


@client.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None or str(message.guild.id) != MENES_SUECOS:
        return

    if client.user.mentioned_in(message):
        content = message.content.replace(f"<@{client.user.id}>", "").strip()
        if not content:
            return

        llm_cog = client.get_cog("LLMCog")
        if llm_cog:
            async with message.channel.typing():
                referenced_bot_message = await _resolve_referenced_bot_message(message, client.user.id)
                response = await llm_cog.get_ai_response(
                    channel_id=str(message.channel.id),
                    author_name=message.author.display_name,
                    message_text=content,
                    referenced_bot_message=referenced_bot_message,
                    channel_name=getattr(message.channel, "name", None),
                )

                await client.log_ai_interaction(
                    source="mention",
                    user_id=message.author.id,
                    user_name=message.author.name,
                    guild_id=message.guild.id if message.guild else None,
                    channel_id=message.channel.id if message.channel else None,
                    message_id=message.id,
                    prompt=content,
                    response=response,
                )

                await _send_chunked_reply(message, response)
            return

    await client.process_commands(message)

    if client.palavraMute and client.palavraMute in message.content.lower():
        duration = timedelta(minutes=5)
        if not message.author.guild_permissions.moderate_members:
            await message.author.timeout(duration, reason="Falou a palavra proibida.")
            await message.channel.send(
                f"Parabens, {message.author.mention}! "
                "Voce falou a palavra proibida e ganhou um timeout de 5 minutos!"
            )

            if client.trocaPalavra:
                palavra_cog = client.get_cog("PalavraCog")
                if palavra_cog:
                    await palavra_cog.getNewWord()
                    await message.channel.send("A palavra foi trocada.")
        else:
            await message.channel.send("O ADM sem graca falou a palavra proibida...")
            if client.trocaPalavra:
                palavra_cog = client.get_cog("PalavraCog")
                if palavra_cog:
                    await palavra_cog.getNewWord()

    if not client.mensagem_block:
        client.contador += 1
        client.propaganda += 1

        if client.trocaPalavra and client.contador >= client.palavrasMax:
            palavra_cog = client.get_cog("PalavraCog")
            if palavra_cog:
                await palavra_cog.getNewWord()
                client.contador = 0
                print(f"Palavra trocada por atingir {client.palavrasMax} mensagens.")

        if client.propaganda >= client.propaganda_max:
            propaganda_cog = client.get_cog("PropagandaCog")
            if propaganda_cog and not isinstance(message.channel, discord.Thread):
                await propaganda_cog.sendAd(message.channel, message.guild, bloqueiachat=True)
                client.propaganda = 0

    now = datetime.now(SAO_PAULO_TZ)
    if not client.flagFirst and "first" in message.content.lower():
        async with client.lock:
            if not client.flagFirst:
                client.flagFirst = True
                role = discord.utils.get(message.guild.roles, name="first")
                if role:
                    await message.author.add_roles(role)
                    print(f"Usuario {message.author.name} recebeu o cargo 'first'.")
                await message.channel.send(
                    f"Parabens {message.author.mention}, voce foi o primeiro a falar 'first' hoje!"
                )
                update_user_first_count(str(message.author.id), message.author.name)
                log_first_event(str(message.author.id), message.author.name, now)

    if int(TOJAO) in [member.id for member in message.mentions]:
        member = message.guild.get_member(int(TOJAO))
        if member and not member.guild_permissions.moderate_members:
            await message.author.timeout(timedelta(minutes=1), reason="Pingou o Tojao.")
            await message.channel.send("NAO. PINGUE. O. TOJAO.")


@client.event
async def on_reaction_add(reaction, user):
    if user.bot or not client.mensagem_block or reaction.message.id != client.mensagem_block.id:
        return

    if reaction.emoji == "✅" and reaction.count >= client.reaction_max:
        async with client.lock:
            if client.mensagem_block:
                print("Contagem de reacoes atingida. Desbloqueando chat.")
                channel = client.mensagem_block.channel
                try:
                    client.ignorar_omd = True
                    await client.mensagem_block.delete()
                except discord.NotFound:
                    pass
                finally:
                    client.ignorar_omd = False

                if client.permissoesOriginais is not None:
                    await channel.set_permissions(
                        reaction.message.guild.default_role,
                        overwrite=client.permissoesOriginais,
                    )

                client.mensagem_block = None
                client.permissoesOriginais = None


@client.event
async def on_message_delete(message):
    if client.ignorar_omd or not client.mensagem_block or message.id != client.mensagem_block.id:
        return

    print("Mensagem de bloqueio foi deletada, restaurando permissoes.")
    if client.permissoesOriginais is not None:
        await message.channel.set_permissions(
            message.guild.default_role,
            overwrite=client.permissoesOriginais,
        )

    client.mensagem_block = None
    client.permissoesOriginais = None


client.run(TOKEN)
