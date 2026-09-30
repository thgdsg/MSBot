import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai_service import MODEL_LIST
from app.services.nvidia_client import NvidiaAPIError, NvidiaClient, NvidiaCompletion


class NvidiaFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_retired_model_retries_and_notifies(self):
        client = NvidiaClient("key")
        notify = AsyncMock()
        client.configure_model_fallbacks(MODEL_LIST, notify)
        error = NvidiaAPIError(410, json.dumps({
            "type": "about:blank", "title": "Gone", "status": 410,
            "detail": "The model 'retired-model' has reached its end of life.",
        }))
        client._chat_completion_once = AsyncMock(side_effect=[error, NvidiaCompletion("ok")])

        result = await client.chat_completion("retired-model", [{"role": "user", "content": "oi"}])

        self.assertEqual(result.content, "ok")
        calls = client._chat_completion_once.await_args_list
        self.assertEqual(calls[0].args[0], "retired-model")
        self.assertEqual(calls[1].args[0], MODEL_LIST[0])
        notify.assert_awaited_once_with("retired-model", MODEL_LIST[0])
        self.assertNotIn("deepseek-ai/deepseek-v4-flash-0731", MODEL_LIST)

    async def test_retired_model_is_skipped_on_future_calls(self):
        client = NvidiaClient("key")
        client.configure_model_fallbacks(MODEL_LIST)
        client.deprecated_models.add("retired-model")
        client._chat_completion_once = AsyncMock(return_value=NvidiaCompletion("ok"))

        await client.chat_completion("retired-model", [])

        self.assertEqual(client._chat_completion_once.await_args.args[0], MODEL_LIST[0])

    def test_only_model_end_of_life_410_is_marked_deprecated(self):
        deprecated = NvidiaAPIError(410, '{"title":"Gone","detail":"model reached its end of life"}')
        unrelated = NvidiaAPIError(410, '{"title":"Gone","detail":"resource removed"}')
        self.assertTrue(deprecated.deprecated_model)
        self.assertFalse(unrelated.deprecated_model)

    def test_api_errors_and_non_chat_payloads_are_logged(self):
        client = NvidiaClient("key")
        http_error = SimpleNamespace(
            status_code=500, text="server error", headers={},
            json=lambda: {"title": "Server error", "detail": "failed"},
        )
        with self.assertLogs("app.nvidia.errors", level="ERROR") as logged:
            with self.assertRaises(NvidiaAPIError):
                client._parse_response(http_error, "modelo de teste")
        self.assertIn("HTTP 500", logged.output[0])

        non_chat = SimpleNamespace(
            status_code=200, text="{}", headers={}, json=lambda: {"status": "ok"},
        )
        with self.assertLogs("app.nvidia.errors", level="ERROR") as logged:
            with self.assertRaises(NvidiaAPIError):
                client._parse_response(non_chat, "modelo de teste")
        self.assertIn("sem choices", logged.output[0])
