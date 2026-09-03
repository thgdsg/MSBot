from __future__ import annotations

import re
from datetime import datetime

from app.services.memory_service import MemoryService
from app.services.nvidia_client import NvidiaClient
from app.services.vision_service import VisionService


DEFAULT_MODEL = "deepseek-ai/deepseek-v4-flash-0731"
DEFAULT_FALLBACK_MODEL = "minimaxai/minimax-m3"
MODEL_LIST = [
    "minimaxai/minimax-m3",
    "deepseek-ai/deepseek-v4-flash-0731",
    "deepseek-ai/deepseek-v4-pro-0813",
    "moonshotai/kimi-k3",
]
DEEPSEEK_MODELS = {
    "deepseek-ai/deepseek-v4-flash-0731",
    "deepseek-ai/deepseek-v4-pro-0813",
}
THINKING_MODES = ["none", "high", "max"]
SYSTEM_PROMPT = """
Voce e o 'Yung Bot', um assistente de IA no servidor de Discord 'Menes Suecos'.
Responda o usuario a seguir sempre utilizando apenas letras minusculas em respostas curtas, podendo utilizar letras maiusculas para enfase se necessario.
Voce deve possuir um tom ironico. JAMAIS ESCREVA @everyone e JAMAIS escreva qualquer caractere chines. SEMPRE escreva em portugues.
Evite considerar o nome do usuario para escrever sua resposta, ao menos que esteja referenciando ele diretamente.
"""


def extract_thinking_and_answer(text: str) -> tuple[str | None, str]:
    blocks = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL | re.IGNORECASE)
    answer = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    thinking = "\n\n".join(block.strip() for block in blocks if block.strip())
    return (thinking or None), answer


def message_text_for_prompt(message) -> str:
    parts = []
    if (message.content or "").strip():
        parts.append(message.content.strip())
    if message.attachments:
        parts.append("anexos: " + ", ".join(attachment.url for attachment in message.attachments))
    if message.embeds:
        parts.append(f"embeds: {len(message.embeds)}")
    return "\n".join(parts).strip()


def extract_image_urls(message) -> list[str]:
    urls = []
    for attachment in message.attachments:
        content_type = (attachment.content_type or "").lower()
        filename = attachment.filename.lower()
        if content_type.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
            urls.append(attachment.url)
    for embed in message.embeds:
        for image in (embed.image, embed.thumbnail):
            url = getattr(image, "url", None)
            if url:
                urls.append(url)
    return list(dict.fromkeys(urls))


async def reply_in_chunks(message, response: str) -> None:
    chunks = [response[index : index + 2000] for index in range(0, len(response), 2000)] or ["(sem conteudo)"]
    try:
        await message.reply(chunks[0])
    except Exception as error:
        if getattr(error, "code", None) != 10008:
            raise
        await message.channel.send(f"{message.author.mention}, aqui esta sua resposta:\n{chunks[0]}")
    for chunk in chunks[1:]:
        await message.channel.send(chunk)


class AIService:
    def __init__(self, context):
        self.context = context
        self.nvidia = context.nvidia
        self.vision = VisionService(self.nvidia)
        self.memory = MemoryService(context)
        self.current_model = DEFAULT_MODEL
        self.current_fallback_model = DEFAULT_FALLBACK_MODEL
        self.current_reasoning_effort = "high"

    def _system_prompt(self, channel_id: str, user_id: str | None) -> str:
        memory = self.memory.text_for_prompt(channel_id=channel_id, user_id=user_id)
        return f"{SYSTEM_PROMPT}\n\nConsidere tambem a memoria persistente abaixo antes de responder.\nMEMORY.md:\n{memory}" if memory else SYSTEM_PROMPT

    def _append_history(self, channel_id: str, user_name: str, prompt: str, thinking: str | None, response: str) -> None:
        history = self.context.history_store.load({})
        if not isinstance(history, dict):
            history = {"legacy_data": history}
        logs = history.setdefault("__ai_logs__", [])
        if not isinstance(logs, list):
            logs = []
            history["__ai_logs__"] = logs
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "channel_id": channel_id,
            "user_name": user_name,
            "prompt": prompt,
            "thinking": thinking,
            "response": response,
        })
        self.context.history_store.save(history)

    async def get_response(
        self,
        *,
        channel_id: str,
        author_name: str,
        user_id: str | int | None,
        message_text: str,
        referenced_bot_message: str | None = None,
        channel_name: str | None = None,
        image_urls: list[str] | None = None,
        model_override: str | None = None,
    ) -> str:
        messages = [{"role": "system", "content": self._system_prompt(channel_id, str(user_id) if user_id is not None else None)}]
        if channel_name:
            messages.append({"role": "system", "content": f"O usuario esta no canal: #{channel_name}"})
        if referenced_bot_message:
            messages.append({"role": "assistant", "content": referenced_bot_message})
        try:
            if image_urls:
                try:
                    description = await self.vision.describe(image_urls, message_text)
                except Exception as error:
                    print(f"[vision] falha no reconhecimento; continuando sem descricao: {error}")
                    description = None
                if description:
                    message_text = f"{message_text or '(mensagem sem texto)'}\n\ndescricao da imagem enviada pelo usuario:\n{description}"
            messages.append({"role": "user", "content": f"{author_name}: {message_text}"})
            primary_model = model_override or self.current_model
            fallback_model = self.current_fallback_model
            used_model = primary_model
            try:
                raw, thinking = await self.nvidia.chat(
                    primary_model,
                    messages,
                    reasoning_effort=self.current_reasoning_effort,
                )
            except Exception as primary_error:
                if not (
                    self.nvidia.is_rate_limit_error(primary_error)
                    and fallback_model
                    and fallback_model != primary_model
                ):
                    raise
                print(
                    f"[nvidia] rate limit detectado no modelo {primary_model}. "
                    f"alternando para fallback {fallback_model}."
                )
                raw, thinking = await self.nvidia.chat(
                    fallback_model,
                    messages,
                    reasoning_effort=self.current_reasoning_effort,
                )
                used_model = fallback_model
            parsed_thinking, answer = extract_thinking_and_answer(raw)
            thinking = thinking or parsed_thinking
            if not answer and fallback_model and used_model != fallback_model:
                fallback_raw, fallback_thinking = await self.nvidia.chat(
                    fallback_model,
                    messages,
                    reasoning_effort=self.current_reasoning_effort,
                )
                parsed_fallback_thinking, fallback_answer = extract_thinking_and_answer(
                    fallback_raw
                )
                if fallback_answer:
                    answer = fallback_answer
                    thinking = fallback_thinking or parsed_fallback_thinking
                    used_model = fallback_model
            if not answer:
                answer = "desculpe, nao consegui gerar uma resposta no momento."
            self._append_history(channel_id, author_name, message_text, thinking, answer)
            await self.memory.record_turn(channel_id=channel_id, channel_name=channel_name, user_name=author_name, user_id=user_id, prompt=message_text, response=answer)
            print(f"[nvidia] modelo utilizado: {used_model}")
            print("[nvidia] resposta:")
            print(answer)
            return answer
        except Exception as error:
            print(f"Erro ao contatar a API da NVIDIA: {error}")
            if image_urls and self.nvidia.is_context_length_error(error):
                return "imagem de tamanho muito grande!"
            if "30 minutos" in str(error):
                return "desculpe, a api ficou em timeout por 30 minutos e nao consegui gerar resposta."
            return "desculpe, nao consegui me conectar a API no momento."
