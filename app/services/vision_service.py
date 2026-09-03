from __future__ import annotations

import asyncio
import base64
import mimetypes
import os

import requests


class VisionService:
    MODEL = "moonshotai/kimi-k3"
    MAX_INLINE_IMAGE_BYTES = 8 * 1024 * 1024

    def __init__(self, nvidia_client):
        self.nvidia = nvidia_client

    @staticmethod
    def _run_blocking(function, *args, **kwargs):
        return asyncio.to_thread(function, *args, **kwargs)

    def _to_data_uri(self, source: str) -> str:
        try:
            if source.startswith("data:image/"):
                return source
            local_path = source
            if not os.path.isabs(local_path):
                local_path = os.path.join(os.path.dirname(__file__), "..", "..", local_path)
            if os.path.isfile(local_path):
                with open(local_path, "rb") as file:
                    image_bytes = file.read()
                content_type = mimetypes.guess_type(local_path)[0] or "image/png"
            else:
                response = requests.get(source, timeout=30)
                response.raise_for_status()
                image_bytes = response.content
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if content_type == "image/jpg":
                content_type = "image/jpeg"
            if content_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise RuntimeError(f"content-type nao suportado: {content_type or 'desconhecido'}")
            if len(image_bytes) > self.MAX_INLINE_IMAGE_BYTES:
                raise RuntimeError("imagem maior que 8 MB")
            encoded = base64.b64encode(image_bytes).decode("ascii")
            print(f"[vision] imagem convertida para base64: {len(image_bytes) / 1024:.1f} KB ({content_type})")
            return f"data:image/{content_type.split('/', 1)[1]};base64,{encoded}"
        except Exception as error:
            print(f"[vision] falha ao preparar imagem, usando URL direta: {error}")
            return source

    async def describe(self, image_sources: list[str], user_prompt: str = "") -> str | None:
        if not image_sources:
            return None
        prepared_images = await asyncio.gather(
            *(self._run_blocking(self._to_data_uri, source) for source in image_sources)
        )
        prompt = (
            "Descreva em portugues, de forma objetiva, as imagens abaixo. "
            "Inclua objetos, pessoas, texto visivel, contexto provavel e detalhes importantes "
            "para que outro modelo responda a mensagem do usuario.\n\n"
            f"Mensagem do usuario: {user_prompt or '(sem texto)'}"
        )
        content: list[dict] = [{"type": "text", "text": prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": image}}
            for image in prepared_images
        )
        print(f"[vision] enviando {len(image_sources)} imagem(ns) para {self.MODEL}")
        raw, _ = await self.nvidia.chat(
            self.MODEL,
            [{"role": "user", "content": content}],
            temperature=0.2,
            max_tokens=2048,
        )
        return raw.strip() or None

