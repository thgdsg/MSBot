from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime

import discord
import requests
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

MENES_SUECOS = os.getenv("MENES_SUECOS")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "minimaxai/minimax-m2.7"
DEFAULT_FALLBACK_MODEL = "moonshotai/kimi-k2-thinking"
MODEL_LIST = [
    "minimaxai/minimax-m2.7",
    "z-ai/glm4.7",
    "deepseek-ai/deepseek-v3_2",
    "moonshotai/kimi-k2-thinking",
]
API_RETRY_WINDOW_SECONDS = 30 * 60
CONVERSATION_HISTORY_FILE = "conversation_history.json"
MEMORY_FILE = "MEMORY.md"
MEMORY_STATE_FILE = "memory_state.json"
MEMORY_SUMMARY_MODEL = "minimaxai/minimax-m2.7"
MEMORY_SUMMARY_BATCH_SIZE = 10
MEMORY_THRESHOLD_MESSAGES = 20

SYSTEM_PROMPT = """
Voce e o 'Yung Bot', um assistente de IA no servidor de Discord 'Menes Suecos'. 
Evite pensar muito e responda o usuario a seguir sempre utilizando apenas letras minusculas em respostas curtas, podendo utilizar letras maiusculas para enfase se necessario. 
Voce deve possuir um tom ironico. JAMAIS ESCREVA "@everyone e JAMAIS escreva em chinês. Sempre escreva em português."
"""


async def _run_blocking(func, *args, **kwargs):
    """Executa funcao bloqueante fora do event loop."""
    to_thread = getattr(asyncio, "to_thread", None)
    if to_thread is not None:
        return await to_thread(func, *args, **kwargs)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


def _load_json_file(path: str, default_value):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_value


def _write_json_file(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return ""


def _write_text_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def _normalize_json_object(data, *, default_key: str) -> dict:
    if isinstance(data, dict):
        return data
    return {default_key: data}


def _ensure_memory_buffers(state: dict) -> dict[str, list[dict[str, str]]]:
    buffers = state.get("__memory_buffers__")
    if not isinstance(buffers, dict):
        buffers = {}
    state["__memory_buffers__"] = buffers
    return buffers


def _is_rate_limit_error(err: Exception) -> bool:
    err_text = str(err).lower()
    return (
        "rate limit" in err_text
        or "too many requests" in err_text
        or "status code: 429" in err_text
        or "status 429" in err_text
    )


def _is_retryable_error(err: Exception) -> bool:
    if isinstance(err, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True

    err_text = str(err).lower()
    return (
        "status code: 504" in err_text
        or "gateway timeout" in err_text
        or "upstream request timeout" in err_text
        or "timed out" in err_text
    )


def _extract_thinking_and_answer(text: str) -> tuple[str | None, str]:
    think_blocks = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned_answer = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    thinking_text = "\n\n".join(block.strip() for block in think_blocks if block.strip())
    return (thinking_text or None), cleaned_answer


def _parse_nvidia_content(content) -> str:
    if not isinstance(content, list):
        return str(content)

    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
        else:
            parts.append(str(item))
    return "".join(parts)


def _nvidia_chat_once(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
) -> tuple[str, str | None]:
    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY nao configurada no .env.")

    response = requests.post(
        f"{NVIDIA_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        },
        timeout=120,
    )

    try:
        parsed_body = response.json()
    except ValueError:
        parsed_body = None

    print(f"[nvidia] status_code: {response.status_code}")
    print("[nvidia] resposta bruta da API:")
    if parsed_body is not None:
        print(json.dumps(parsed_body, ensure_ascii=False, indent=2))
    else:
        print(response.text)

    if response.status_code >= 400:
        body_preview = (
            json.dumps(parsed_body, ensure_ascii=False)[:500]
            if parsed_body is not None
            else response.text[:500]
        )
        raise RuntimeError(
            f"nvidia api error (status code: {response.status_code}): {body_preview}"
        )

    if parsed_body is None:
        raise RuntimeError("nvidia api error: resposta nao veio em json.")

    choices = parsed_body.get("choices") or []
    if not choices:
        return "", None

    message_data = choices[0].get("message", {})
    content = _parse_nvidia_content(message_data.get("content", ""))
    reasoning = message_data.get("reasoning_content")
    return content, (str(reasoning) if reasoning else None)


async def _chat_with_retry(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
) -> tuple[str, str | None]:
    loop = asyncio.get_running_loop()
    started_at = loop.time()
    delay_seconds = 5
    attempt = 0

    while True:
        attempt += 1
        try:
            return await _run_blocking(
                _nvidia_chat_once,
                model,
                messages,
                temperature=temperature,
            )
        except Exception as err:
            if not _is_retryable_error(err):
                raise

            remaining = API_RETRY_WINDOW_SECONDS - (loop.time() - started_at)
            if remaining <= 0:
                raise TimeoutError(
                    f"Timeout persistiu por 30 minutos no modelo {model}."
                ) from err

            sleep_for = min(delay_seconds, max(1, int(remaining)))
            print(
                f"[nvidia] timeout no modelo {model} (tentativa {attempt}). "
                f"nova tentativa em {sleep_for}s..."
            )
            await asyncio.sleep(sleep_for)
            delay_seconds = min(delay_seconds * 2, 60)


class LLMCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.current_model = DEFAULT_MODEL
        self.current_fallback_model = DEFAULT_FALLBACK_MODEL
        self.memory_lock = asyncio.Lock()

    def _append_ai_history_log(
        self,
        *,
        channel_id: str,
        user_name: str,
        prompt: str,
        thinking: str | None,
        response: str,
    ) -> None:
        history_data = _normalize_json_object(
            _load_json_file(CONVERSATION_HISTORY_FILE, {}),
            default_key="legacy_data",
        )
        ai_logs = history_data.get("__ai_logs__")
        if not isinstance(ai_logs, list):
            ai_logs = []

        ai_logs.append(
            {
                "timestamp": datetime.now().isoformat(),
                "channel_id": channel_id,
                "user_name": user_name,
                "prompt": prompt,
                "thinking": thinking,
                "response": response,
            }
        )

        history_data["__ai_logs__"] = ai_logs
        _write_json_file(CONVERSATION_HISTORY_FILE, history_data)

    def _load_memory_markdown(self) -> str:
        return _read_text_file(MEMORY_FILE)

    def _write_memory_markdown(self, content: str) -> None:
        _write_text_file(MEMORY_FILE, content.strip() + "\n")

    def _load_memory_state(self) -> dict:
        state = _normalize_json_object(
            _load_json_file(MEMORY_STATE_FILE, {"__memory_buffers__": {}}),
            default_key="legacy_data",
        )
        _ensure_memory_buffers(state)
        return state

    def _save_memory_state(self, state: dict) -> None:
        buffers = state.get("__memory_buffers__", {})
        total_items = sum(len(items) for items in buffers.values()) if isinstance(buffers, dict) else 0
        print(f"[memory] salvando {MEMORY_STATE_FILE} com {total_items} itens em buffer")
        _write_json_file(MEMORY_STATE_FILE, state)

    def _build_system_prompt(self) -> str:
        memory_text = self._load_memory_markdown().strip()
        if not memory_text:
            return SYSTEM_PROMPT

        return (
            f"{SYSTEM_PROMPT}\n\n"
            "Considere tambem a memoria persistente abaixo antes de responder.\n"
            f"MEMORY.md:\n{memory_text}"
        )

    def _format_memory_window(self, messages: list[dict[str, str]]) -> str:
        lines: list[str] = []
        for item in messages:
            role = item.get("role", "")
            content = item.get("content", "")
            if role == "user":
                lines.append(f"usuario: {content}")
            elif role == "assistant":
                lines.append(f"bot: {content}")
            else:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _build_memory_summary_messages(
        self,
        *,
        current_memory: str,
        channel_id: str,
        channel_name: str | None,
        conversation_excerpt: str,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "Voce e um resumidor de memoria para um bot de Discord. "
                    "Atualize o MEMORY.md com fatos uteis, preferencias, contexto recorrente e decisoes. "
                    "Escreva em markdown curto e objetivo, sem inventar informacoes. "
                    "Preserve o que ja existe e incorpore apenas o que e novo."
                    "Caso as seções Estado atual e Preferencias do usuário estejam com mais de 2000 caracteres, delete a linha superior/mais antiga e comece a escrever em uma nova linha no fim da seção."
                    "JAMAIS escreva em chinês. Sempre escreva em português."
                    ),
            },
            {
                "role": "system",
                "content": f"MEMORY.md atual:\n{current_memory or '(vazio)'}",
            },
            {
                "role": "user",
                "content": (
                    f"Canal: {channel_name or channel_id}\n"
                    f"Conversa recente (20 mensagens):\n{conversation_excerpt}\n\n"
                    "Retorne apenas o novo conteudo completo de MEMORY.md."
                ),
            },
        ]

    def _upsert_memory_section(
        self,
        current_memory: str,
        channel_id: str,
        channel_name: str | None,
        summary_text: str,
    ) -> str:
        channel_label = channel_name or channel_id
        start_marker = f"<!-- channel:{channel_id} -->"
        end_marker = f"<!-- /channel:{channel_id} -->"
        section = (
            f"{start_marker}\n"
            f"## canal {channel_label}\n\n"
            f"{summary_text.strip()}\n"
            f"{end_marker}"
        )

        if start_marker in current_memory and end_marker in current_memory:
            pattern = re.compile(
                rf"<!-- channel:{re.escape(channel_id)} -->.*?<!-- /channel:{re.escape(channel_id)} -->",
                flags=re.DOTALL,
            )
            return pattern.sub(section, current_memory).strip() + "\n"

        base = current_memory.strip()
        if not base:
            return f"# MEMORY.md\n\n{section}\n"
        return f"{base}\n\n{section}\n"

    async def _generate_memory_summary(
        self,
        *,
        current_memory: str,
        channel_id: str,
        channel_name: str | None,
        conversation_excerpt: str,
    ) -> str:
        summary_raw, _ = await _chat_with_retry(
            MEMORY_SUMMARY_MODEL,
            self._build_memory_summary_messages(
                current_memory=current_memory,
                channel_id=channel_id,
                channel_name=channel_name,
                conversation_excerpt=conversation_excerpt,
            ),
            temperature=0.4,
        )
        return summary_raw.strip()

    async def _summarize_memory_window(
        self,
        channel_id: str,
        channel_name: str | None = None,
    ) -> None:
        async with self.memory_lock:
            state = self._load_memory_state()
            buffers = _ensure_memory_buffers(state)
            channel_buffer = buffers.get(channel_id, [])
            batch_size = MEMORY_SUMMARY_BATCH_SIZE * 2

            if len(channel_buffer) < batch_size:
                return

            window = channel_buffer[:batch_size]
            remaining = channel_buffer[batch_size:]
            current_memory = self._load_memory_markdown()

            try:
                updated_memory = current_memory

                while True:
                    summary_text = await self._generate_memory_summary(
                        current_memory=updated_memory,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        conversation_excerpt=self._format_memory_window(window),
                    )
                    if not summary_text:
                        return

                    updated_memory = self._upsert_memory_section(
                        updated_memory,
                        channel_id,
                        channel_name,
                        summary_text,
                    )
                    self._write_memory_markdown(updated_memory)

                    buffers[channel_id] = remaining
                    self._save_memory_state(state)
                    print(f"[memory] memoria atualizada para canal {channel_id}")

                    if len(remaining) < batch_size:
                        return

                    window = remaining[:batch_size]
                    remaining = remaining[batch_size:]
            except Exception as err:
                print(f"[memory] falha ao resumir memoria para canal {channel_id}: {err}")

    async def _record_memory_turn(
        self,
        *,
        channel_id: str,
        channel_name: str | None,
        user_name: str,
        prompt: str,
        response: str,
    ) -> None:
        async with self.memory_lock:
            state = self._load_memory_state()
            buffers = _ensure_memory_buffers(state)
            channel_buffer = buffers.get(channel_id, [])
            timestamp = datetime.now().isoformat()

            channel_buffer.extend(
                [
                    {
                        "role": "user",
                        "content": prompt,
                        "user_name": user_name,
                        "channel_name": channel_name,
                        "timestamp": timestamp,
                    },
                    {
                        "role": "assistant",
                        "content": response,
                        "user_name": "Yung Bot",
                        "channel_name": channel_name,
                        "timestamp": timestamp,
                    },
                ]
            )

            buffers[channel_id] = channel_buffer
            self._save_memory_state(state)
            should_summarize = len(channel_buffer) >= MEMORY_THRESHOLD_MESSAGES

        if should_summarize:
            asyncio.create_task(self._summarize_memory_window(channel_id, channel_name))

    async def get_ai_response(
        self,
        channel_id: str,
        author_name: str,
        message_text: str,
        referenced_bot_message: str | None = None,
        channel_name: str | None = None,
        model_override: str | None = None,
        fallback_model_override: str | None = None,
    ) -> str:
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        if channel_name:
            messages.append({"role": "system", "content": f"O usuario esta no canal: #{channel_name}"})
        if referenced_bot_message:
            messages.append({"role": "assistant", "content": referenced_bot_message})
        messages.append({"role": "user", "content": f"{author_name}: {message_text}"})

        primary_model = model_override or self.current_model
        fallback_model = fallback_model_override or self.current_fallback_model

        try:
            used_model = primary_model

            try:
                raw_answer, raw_thinking = await _chat_with_retry(primary_model, messages)
            except Exception as primary_error:
                should_fallback = (
                    _is_rate_limit_error(primary_error)
                    and fallback_model
                    and fallback_model != primary_model
                )
                if not should_fallback:
                    raise

                print(
                    f"[nvidia] rate limit detectado no modelo {primary_model}. "
                    f"alternando para fallback {fallback_model}."
                )
                raw_answer, raw_thinking = await _chat_with_retry(fallback_model, messages)
                used_model = fallback_model

            parsed_thinking, final_answer = _extract_thinking_and_answer(raw_answer)
            thinking_text = raw_thinking or parsed_thinking

            if not final_answer and fallback_model and used_model != fallback_model:
                fallback_raw_answer, fallback_raw_thinking = await _chat_with_retry(
                    fallback_model,
                    messages,
                )
                parsed_fallback_thinking, fallback_final_answer = _extract_thinking_and_answer(
                    fallback_raw_answer
                )
                if fallback_final_answer:
                    final_answer = fallback_final_answer
                    thinking_text = fallback_raw_thinking or parsed_fallback_thinking
                    used_model = fallback_model

            if not final_answer:
                final_answer = "desculpe, nao consegui gerar uma resposta no momento."

            self._append_ai_history_log(
                channel_id=channel_id,
                user_name=author_name,
                prompt=message_text,
                thinking=thinking_text,
                response=final_answer,
            )
            await self._record_memory_turn(
                channel_id=channel_id,
                channel_name=channel_name,
                user_name=author_name,
                prompt=message_text,
                response=final_answer,
            )

            print(f"[nvidia] modelo utilizado: {used_model}")
            print("[nvidia] resposta:")
            print(final_answer)
            return final_answer
        except Exception as err:
            print(f"Erro ao contatar a API da NVIDIA: {err}")
            if "30 minutos" in str(err):
                return "desculpe, a api ficou em timeout por 30 minutos e nao consegui gerar resposta."
            return "Desculpe, nao consegui me conectar a API no momento."

    @app_commands.command(name="conversar", description="Converse com o Yung Bot.")
    @app_commands.describe(mensagem="Sobre o que voce quer falar?")
    async def conversar(self, interaction: discord.Interaction, mensagem: str):
        if interaction.guild_id != int(MENES_SUECOS):
            await interaction.response.send_message(
                "Este comando so pode ser usado no servidor Menes Suecos.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        final_answer = await self.get_ai_response(
            channel_id=str(interaction.channel_id),
            author_name=interaction.user.display_name,
            message_text=mensagem,
            channel_name=interaction.channel.name if interaction.channel else None,
        )

        if hasattr(self.client, "log_ai_interaction"):
            await self.client.log_ai_interaction(
                source="slash_conversar",
                user_id=interaction.user.id,
                user_name=interaction.user.name,
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                interaction_id=interaction.id,
                prompt=mensagem,
                response=final_answer,
            )

        response_prefix = f"mensagem de {interaction.user.mention}: *{mensagem}*\n"
        if len(response_prefix) + len(final_answer) <= 2000:
            await interaction.followup.send(f"{response_prefix}{final_answer}")
            return

        first_chunk_limit = 2000 - len(response_prefix)
        await interaction.followup.send(f"{response_prefix}{final_answer[:first_chunk_limit]}")

        remaining_answer = final_answer[first_chunk_limit:]
        for index in range(0, len(remaining_answer), 2000):
            await interaction.followup.send(remaining_answer[index : index + 2000])

    @app_commands.command(
        name="alterarmodelo",
        description="Altera o modelo atual usado nas respostas do bot.",
    )
    @app_commands.describe(modelo="Modelo a ser usado (da lista permitida)")
    @app_commands.choices(modelo=[app_commands.Choice(name=model, value=model) for model in MODEL_LIST])
    async def alterar_modelo(
        self,
        interaction: discord.Interaction,
        modelo: app_commands.Choice[str],
    ):
        if interaction.guild_id != int(MENES_SUECOS):
            await interaction.response.send_message(
                "Este comando so pode ser usado no servidor Menes Suecos.",
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "Voce nao tem permissao para usar este comando.",
                ephemeral=True,
            )
            return

        self.current_model = modelo.value
        self.current_fallback_model = DEFAULT_FALLBACK_MODEL
        await interaction.response.send_message(
            f"modelo alterado para {self.current_model}.",
            ephemeral=True,
        )

    @app_commands.command(name="vermemoria", description="Mostra a memoria atual do bot.")
    async def ver_memoria(self, interaction: discord.Interaction):
        if interaction.guild_id != int(MENES_SUECOS):
            await interaction.response.send_message(
                "Este comando so pode ser usado no servidor Menes Suecos.",
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "Voce nao tem permissao para usar este comando.",
                ephemeral=True,
            )
            return

        memory_text = self._load_memory_markdown().strip()
        if not memory_text:
            await interaction.response.send_message("MEMORY.md esta vazio.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        for index in range(0, len(memory_text), 1800):
            chunk = memory_text[index : index + 1800]
            await interaction.followup.send(f"```md\n{chunk}\n```", ephemeral=True)


async def setup(client):
    await client.add_cog(LLMCog(client))
