import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai_service import AIService, MODEL_LIST
from app.services.nvidia_client import NvidiaCompletion


class ModelRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_starts_alternate_after_timeout_and_returns_first_success(self):
        service = AIService.__new__(AIService)
        service.MODEL_HEDGE_DELAY_SECONDS = 0.01
        primary_cancelled = asyncio.Event()
        primary_model = next(model for model in MODEL_LIST if model != MODEL_LIST[0])
        alternate_model = MODEL_LIST[0]

        async def complete(model, messages, **kwargs):
            if model == primary_model:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    primary_cancelled.set()
                    raise
            return NvidiaCompletion("alternate answer")

        service._complete_model = AsyncMock(side_effect=complete)
        answer, model = await service._race_completion(
            primary_model, [{"role": "user", "content": "hi"}],
            fallback_model=alternate_model, use_tools=False,
        )

        self.assertEqual(answer.content, "alternate answer")
        self.assertEqual(answer.model, alternate_model)
        self.assertEqual(model, alternate_model)
        self.assertTrue(primary_cancelled.is_set())
        self.assertEqual(service._complete_model.await_count, 2)

    async def test_fast_primary_does_not_start_second_request(self):
        service = AIService.__new__(AIService)
        service.MODEL_HEDGE_DELAY_SECONDS = 1
        service._complete_model = AsyncMock(return_value=NvidiaCompletion("fast answer"))
        primary_model = MODEL_LIST[-1]

        answer, model = await service._race_completion(
            primary_model, [], fallback_model=MODEL_LIST[0],
            use_tools=False,
        )

        self.assertEqual(answer.content, "fast answer")
        self.assertEqual(model, primary_model)
        service._complete_model.assert_awaited_once()

    async def test_only_winning_model_can_trigger_tools(self):
        service = AIService.__new__(AIService)
        service.MODEL_HEDGE_DELAY_SECONDS = 0.01
        service.max_tool_rounds = 1
        primary_model = MODEL_LIST[-1]
        alternate_model = MODEL_LIST[0]
        tool_call = {"id": "call-1", "function": {"name": "mutate", "arguments": "{}"}}
        tools = SimpleNamespace(
            definitions=lambda: [], execute_call=AsyncMock(return_value={"ok": True})
        )

        async def complete(model, messages, **kwargs):
            if model == primary_model:
                await asyncio.Event().wait()
            if kwargs.get("use_tools"):
                return NvidiaCompletion("", tool_calls=[tool_call])
            return NvidiaCompletion("winning response")

        service._complete_model = AsyncMock(side_effect=complete)
        service.nvidia = SimpleNamespace(chat_completion=object())
        service.tools = tools
        completion = await service._complete_with_tools(
            primary_model, [], tools, fallback_model=alternate_model,
        )

        self.assertEqual(completion.content, "winning response")
        self.assertEqual(completion.model, alternate_model)
        tools.execute_call.assert_awaited_once_with(tool_call)
