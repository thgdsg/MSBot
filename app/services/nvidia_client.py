from __future__ import annotations

import asyncio
import json
from typing import Any

import requests


class NvidiaAPIError(RuntimeError):
    def __init__(self, status_code: int, body_preview: str):
        super().__init__(
            f"nvidia api error (status code: {status_code}): {body_preview}"
        )
        self.status_code = status_code
        self.body_preview = body_preview


class NvidiaPendingResult(RuntimeError):
    def __init__(self, request_id: str):
        super().__init__(f"nvidia request pendente: {request_id}")
        self.request_id = request_id


def _parse_content(content: Any) -> str:
    if not isinstance(content, list):
        return str(content)
    parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
        else:
            parts.append(str(item))
    return "".join(parts)


class NvidiaClient:
    BASE_URL = "https://integrate.api.nvidia.com/v1"
    RETRY_WINDOW_SECONDS = 30 * 60

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    @staticmethod
    def is_rate_limit_error(error: Exception) -> bool:
        text = str(error).lower()
        return any(
            marker in text
            for marker in ("rate limit", "too many requests", "status code: 429", "status 429")
        )

    @staticmethod
    def is_context_length_error(error: Exception) -> bool:
        text = str(error).lower()
        return any(
            marker in text
            for marker in (
                "maximum context length",
                "input_tokens",
                "reduce the length of the input prompt",
                "context length",
            )
        )

    @staticmethod
    def supports_reasoning(model: str) -> bool:
        return model in {
            "deepseek-ai/deepseek-v4-flash-0731",
            "deepseek-ai/deepseek-v4-pro-0813",
        }

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(error, NvidiaAPIError):
            return error.status_code in {408, 409, 425, 429} or 500 <= error.status_code <= 599
        text = str(error).lower()
        return any(
            marker in text
            for marker in (
                "status code: 504",
                "status code: 429",
                "gateway timeout",
                "upstream request timeout",
                "timed out",
                "resposta nao veio em json",
                "resposta sem choices",
            )
        )

    @staticmethod
    def _request_id(body: dict | None, response: requests.Response) -> str | None:
        if isinstance(body, dict):
            for key in ("requestId", "request_id", "id"):
                if body.get(key):
                    return str(body[key])
        for header in ("NVCF-REQID", "NVCF-REQUEST-ID", "x-request-id"):
            if response.headers.get(header):
                return str(response.headers[header])
        return None

    def _parse_response(self, response: requests.Response, request_context: str):
        try:
            body = response.json()
        except ValueError:
            body = None

        print(f"[nvidia] {request_context} status_code: {response.status_code}")
        if body is not None:
            print("[nvidia] resposta bruta da API:")
            print(json.dumps(body, ensure_ascii=False, indent=2))

        if response.status_code == 202:
            request_id = self._request_id(body, response)
            if not request_id:
                raise RuntimeError("nvidia api error: resposta 202 sem requestId.")
            raise NvidiaPendingResult(request_id)
        if response.status_code >= 400:
            preview = json.dumps(body, ensure_ascii=False)[:500] if body is not None else response.text[:500]
            raise NvidiaAPIError(response.status_code, preview)
        if body is None:
            raise RuntimeError("nvidia api error: resposta nao veio em json.")
        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("nvidia api error: resposta sem choices.")
        message = choices[0].get("message", {})
        return _parse_content(message.get("content", "")), message.get("reasoning_content")

    def _chat_once(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
    ):
        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY nao configurada no .env.")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if reasoning_effort and self.supports_reasoning(model):
            payload["reasoning_effort"] = reasoning_effort
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        response = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        return self._parse_response(response, f"modelo {model}")

    def _poll_once(self, request_id: str):
        response = requests.get(
            f"{self.BASE_URL}/status/{request_id}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=120,
        )
        return self._parse_response(response, f"poll {request_id}")

    async def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
    ):
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        delay_seconds = 5
        attempt = 0

        while True:
            attempt += 1
            try:
                return await asyncio.to_thread(
                    self._chat_once,
                    model,
                    messages,
                    temperature=temperature,
                    reasoning_effort=reasoning_effort,
                    max_tokens=max_tokens,
                )
            except NvidiaPendingResult as pending:
                poll_delay = 2
                while True:
                    remaining = self.RETRY_WINDOW_SECONDS - (loop.time() - started_at)
                    if remaining <= 0:
                        raise TimeoutError(f"Resultado pendente por 30 minutos no modelo {model}") from pending
                    sleep_for = min(poll_delay, max(1, int(remaining)))
                    print(f"[nvidia] resultado pendente {pending.request_id}. poll em {sleep_for}s...")
                    await asyncio.sleep(sleep_for)
                    try:
                        return await asyncio.to_thread(self._poll_once, pending.request_id)
                    except NvidiaPendingResult:
                        poll_delay = min(poll_delay * 2, 15)
            except Exception as error:
                if not self._is_retryable(error):
                    raise
                remaining = self.RETRY_WINDOW_SECONDS - (loop.time() - started_at)
                if remaining <= 0:
                    raise TimeoutError(f"Timeout persistiu por 30 minutos no modelo {model}") from error
                sleep_for = min(delay_seconds, max(1, int(remaining)))
                print(f"[nvidia] timeout no modelo {model} (tentativa {attempt}). nova tentativa em {sleep_for}s...")
                await asyncio.sleep(sleep_for)
                delay_seconds = min(delay_seconds * 2, 60)
