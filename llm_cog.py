import discord
from discord.ext import commands, tasks
from discord import app_commands
import ollama
import os
import asyncio
import json
from collections import deque
from datetime import datetime, timedelta
import time

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
MAX_HISTORY_SIZE = 5

# resumo separado do histórico "normal"
SUMMARY_FILE = 'conversation_summaries.json'
SUMMARY_WINDOW_SIZE = 25
SUMMARY_INTERVAL_SECONDS = 2 * 60 * 60  # 2 horas


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
        self.history_lock = asyncio.Lock()
        self.summary_lock = asyncio.Lock()

        # buffer em memória (por canal) com as últimas 25 mensagens (user+assistant)
        self.summary_windows: dict[str, deque] = {}
        # "memória resumida" por canal (string)
        self.summaries: dict[str, str] = {}
        # controle pra não resumir o tempo todo
        self.last_summarized_at: dict[str, float] = {}

        # carrega resumos persistidos (se existir)
        self._summary_loaded = False

        # loop em background a cada X tempo
        self.summarize_loop.start()

    def cog_unload(self):
        # garante que o loop para ao descarregar o cog
        self.summarize_loop.cancel()

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

    async def _load_summaries(self) -> dict:
        async with self.summary_lock:
            try:
                with open(SUMMARY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    async def _save_summaries(self, summaries: dict):
        async with self.summary_lock:
            with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
                json.dump(summaries, f, indent=4, ensure_ascii=False)

    async def _ensure_summaries_loaded(self):
        if self._summary_loaded:
            return
        loaded = await self._load_summaries()
        # arquivo é {channel_id: summary_text}
        self.summaries = {str(k): str(v) for k, v in loaded.items()}
        self._summary_loaded = True

    def _get_summary_window(self, channel_id: str) -> deque:
        if channel_id not in self.summary_windows:
            self.summary_windows[channel_id] = deque(maxlen=SUMMARY_WINDOW_SIZE)
        return self.summary_windows[channel_id]

    async def _maybe_summarize_channel(self, channel_id: str) -> None:
        """Sumariza (se necessário) a janela do canal e persiste em SUMMARY_FILE."""
        await self._ensure_summaries_loaded()

        window = self._get_summary_window(channel_id)
        if not window:
            return

        now = time.time()
        last = self.last_summarized_at.get(channel_id, 0.0)
        if now - last < SUMMARY_INTERVAL_SECONDS:
            return

        # monta texto compactado da janela
        # exemplo: "user: ...\nassistant: ...\n..."
        convo_text = "\n".join([f"{m['role']}: {m['content']}" for m in list(window)])

        previous_summary = self.summaries.get(channel_id, "").strip()

        summary_prompt = (
            "faça um resumo curto e útil da conversa a seguir, em português.\n"
            "regras:\n"
            "- mantenha fatos, decisões, preferências do usuário, nomes e contexto.\n"
            "- não inclua detalhes supérfluos.\n"
            "- use no máximo ~1200 caracteres.\n"
            "- se já existir um resumo anterior, atualize-o incorporando as novidades.\n"
        )

        # mensagens pra LLM (resumo é separado do histórico normal)
        messages = [
            {"role": "system", "content": summary_prompt},
        ]
        if previous_summary:
            messages.append(
                {"role": "user", "content": f"resumo anterior:\n{previous_summary}"}
            )
        messages.append(
            {"role": "user", "content": f"janela (últimas mensagens):\n{convo_text}"}
        )

        try:
            # usa thread pra não bloquear o loop do discord
            resp = await _run_blocking(
                ollama.chat,
                model="gemma3:1b",
                messages=messages,
            )
            new_summary = resp["message"]["content"].strip()
            if new_summary:
                self.summaries[channel_id] = new_summary
                await self._save_summaries(self.summaries)
                self.last_summarized_at[channel_id] = now
        except Exception as e:
            # não quebra o bot por falha de resumo; só loga
            print(f"Erro ao sumarizar canal {channel_id}: {e}")

    @tasks.loop(seconds=SUMMARY_INTERVAL_SECONDS)
    async def summarize_loop(self):
        """Roda em paralelo a cada 2 horas e tenta resumir os canais ativos."""
        await self._ensure_summaries_loaded()

        # copia chaves pra não dar problema se mudarem durante iteração
        channel_ids = list(set(list(self.summary_windows.keys()) + list(self.summaries.keys())))
        for channel_id in channel_ids:
            await self._maybe_summarize_channel(channel_id)

    @summarize_loop.before_loop
    async def before_summarize_loop(self):
        await self.client.wait_until_ready()
        await self._ensure_summaries_loaded()

    async def get_ai_response(self, channel_id: str, author_name: str, message_text: str):
        """Obtém uma resposta da LLM, gerenciando o histórico da conversa + resumo separado."""
        await self._ensure_summaries_loaded()

        all_history = await self._load_history()

        channel_history_list = all_history.get(channel_id, [])
        history_deque = deque(channel_history_list, maxlen=MAX_HISTORY_SIZE)

        formatted_message = f"{author_name}: {message_text}"

        # adiciona "memória resumida" como contexto separado do histórico (sem misturar)
        summary_text = self.summaries.get(channel_id, "").strip()
        summary_context = ""
        if summary_text:
            summary_context = (
                "contexto resumido de conversas anteriores (pode estar incompleto):\n"
                f"{summary_text}"
            )

        messages = [{"role": "system", "content": system_prompt}]
        if summary_context:
            # injeta o resumo antes do histórico curto, como "memória"
            messages.append({"role": "system", "content": summary_context})

        messages.extend(list(history_deque))
        messages.append({"role": "user", "content": formatted_message})

        try:
            response = await _run_blocking(
                ollama.chat,
                model="llama3.2:3b",
                messages=messages,
            )

            raw_answer = response["message"]["content"]
            final_answer = raw_answer.strip()

            # histórico curto (o que já existia)
            history_deque.append({"role": "user", "content": formatted_message})
            history_deque.append({"role": "assistant", "content": final_answer})

            all_history[channel_id] = list(history_deque)
            await self._save_history(all_history)

            # janela de resumo (últimas 25 mensagens user+assistant no total)
            window = self._get_summary_window(channel_id)
            window.append({"role": "user", "content": formatted_message})
            window.append({"role": "assistant", "content": final_answer})

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