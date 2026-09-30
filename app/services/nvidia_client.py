from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import requests


NVIDIA_ERROR_LOGGER = logging.getLogger("app.nvidia.errors")


class NvidiaAPIError(RuntimeError):
    def __init__(self, status_code: int, body_preview: str):
        super().__init__(
            f"nvidia api error (status code: {status_code}): {body_preview}"
        )
        self.status_code = status_code
        self.body_preview = body_preview
        try:
            payload = json.loads(body_preview)
        except (TypeError, ValueError):
            payload = {}
        detail = str(payload.get("detail", "")).lower() if isinstance(payload, dict) else ""
        self.deprecated_model = status_code == 410 and (
            "end of life" in detail or "deprecated" in detail or "deprecat" in detail
        )


class NvidiaPendingResult(RuntimeError):
    def __init__(self, request_id: str):
        super().__init__(f"nvidia request pendente: {request_id}")
        self.request_id = request_id


@dataclass
class NvidiaCompletion:
    """Resposta estruturada da API, preservando dados necessarios para tools."""

    content: str
    reasoning_content: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str | None = None
    message: dict = field(default_factory=dict)
    model: str | None = None

    @property
    def assistant_message(self) -> dict:
        if self.message:
            return self.message
        message = {"role": "assistant", "content": self.content}
        if self.reasoning_content:
            message["reasoning_content"] = self.reasoning_content
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        return message


def _parse_content(content: Any) -> str:
    if content is None:
        return ""
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
        self.fallback_models: list[str] = []
        self.deprecated_models: set[str] = set()
        self._deprecation_notifier: Callable | None = None

    def configure_model_fallbacks(self, models, notifier=None) -> None:
        self.fallback_models = list(dict.fromkeys(models))
        self._deprecation_notifier = notifier

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
        return False

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
                NVIDIA_ERROR_LOGGER.error(
                    "NVIDIA retornou HTTP 202 sem requestId durante %s; corpo=%s",
                    request_context, str(body)[:500],
                )
                raise RuntimeError("nvidia api error: resposta 202 sem requestId.")
            raise NvidiaPendingResult(request_id)
        if response.status_code >= 400:
            preview = json.dumps(body, ensure_ascii=False)[:500] if body is not None else response.text[:500]
            NVIDIA_ERROR_LOGGER.error(
                "NVIDIA API retornou HTTP %s durante %s; corpo=%s",
                response.status_code, request_context, preview,
            )
            raise NvidiaAPIError(response.status_code, preview)
        if body is None:
            NVIDIA_ERROR_LOGGER.error(
                "NVIDIA API retornou HTTP %s sem JSON durante %s; corpo=%s",
                response.status_code, request_context, response.text[:500],
            )
            raise RuntimeError("nvidia api error: resposta nao veio em json.")
        if not isinstance(body, dict):
            preview = str(body)[:500]
            NVIDIA_ERROR_LOGGER.error(
                "NVIDIA retornou JSON sem objeto de chat durante %s; corpo=%s",
                request_context, preview,
            )
            raise NvidiaAPIError(502, preview)
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            preview = json.dumps(body, ensure_ascii=False)[:500]
            NVIDIA_ERROR_LOGGER.error(
                "NVIDIA retornou payload sem choices de chat durante %s; corpo=%s",
                request_context, preview,
            )
            raise NvidiaAPIError(502, preview)
        message = choices[0].get("message", {})
        if not isinstance(message, dict):
            preview = json.dumps(body, ensure_ascii=False)[:500]
            NVIDIA_ERROR_LOGGER.error(
                "NVIDIA retornou message invalida durante %s; corpo=%s",
                request_context, preview,
            )
            raise NvidiaAPIError(502, preview)
        content = _parse_content(message.get("content", ""))
        reasoning_content = message.get("reasoning_content")
        tool_calls = message.get("tool_calls") or []
        if not isinstance(tool_calls, list) or any(not isinstance(item, dict) for item in tool_calls):
            preview = json.dumps(body, ensure_ascii=False)[:500]
            NVIDIA_ERROR_LOGGER.error(
                "NVIDIA retornou tool_calls em formato invalido durante %s; corpo=%s",
                request_context, preview,
            )
            raise NvidiaAPIError(502, preview)
        if not content.strip() and not tool_calls:
            preview = json.dumps(body, ensure_ascii=False)[:500]
            NVIDIA_ERROR_LOGGER.error(
                "NVIDIA retornou resposta vazia sem tool_calls durante %s; corpo=%s",
                request_context, preview,
            )
            raise NvidiaAPIError(502, preview)
        return NvidiaCompletion(
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
            finish_reason=choices[0].get("finish_reason"),
            message=message,
        )

    def _chat_once(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.5,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
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
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
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
        completion = await self.chat_completion(
            model,
            messages,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
        )
        return completion.content, completion.reasoning_content

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> NvidiaCompletion:
        """Try another supported model if NVIDIA has retired the requested one."""
        candidates = [model] + [item for item in self.fallback_models if item != model]
        last_deprecation = None
        for index, candidate in enumerate(candidates):
            if candidate in self.deprecated_models:
                continue
            try:
                return await self._chat_completion_once(
                    candidate, messages, temperature=temperature,
                    reasoning_effort=reasoning_effort, max_tokens=max_tokens,
                    tools=tools, tool_choice=tool_choice,
                )
            except NvidiaAPIError as error:
                if not error.deprecated_model:
                    raise
                already_notified = candidate in self.deprecated_models
                self.deprecated_models.add(candidate)
                last_deprecation = error
                replacement = next(
                    (item for item in candidates[index + 1:]
                     if item not in self.deprecated_models), None
                )
                if not already_notified and self._deprecation_notifier is not None:
                    try:
                       await self._deprecation_notifier(candidate, replacement)
                    except Exception as notify_error:
                        print(f"[nvidia] falha na notificacao de deprecacao: {notify_error}")
                print(f"[nvidia] modelo {candidate} depreciado; tentando {replacement}.")
        if last_deprecation is not None:
            raise last_deprecation
        raise RuntimeError("Nenhum modelo disponivel na lista de fallback.")

    async def _chat_completion_once(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> NvidiaCompletion:
        """Executa uma chamada preservando tool_calls e a mensagem do assistente."""
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
                    tools=tools,
                    tool_choice=tool_choice,
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
