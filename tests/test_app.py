from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from app.commands.helpers import is_moderator
from app.commands.registry import register_all_commands
from app.config import AppConfig
from app.events.message_events import MessageEventHandler
from app.events.reaction_events import ReactionEventHandler
from app.persistence.first_repository import FirstRepository
from app.persistence.json_store import JsonStore
from app.services.ai_service import AIService, DEFAULT_MODEL
from app.services.memory_service import MemoryService
from app.services.moderation_service import ModerationService
from app.services.nvidia_client import NvidiaCompletion
from app.services.vision_service import VisionService
from app.services.web_search_service import WebSearchService
from app.services.word_service import WordService
from app.state import BotState
from app.tools.registry import ToolRegistry


class AppConfigTests(unittest.TestCase):
    def test_paths_are_rooted_and_runtime_validation_checks_required_values(self):
        with tempfile.TemporaryDirectory() as directory:
            config = AppConfig(
                root_dir=Path(directory),
                token="token",
                server_id="123",
                tojao_id=None,
                log_channel_id=None,
                mute_role_id=None,
                owner_id=None,
                nvidia_api_key=None,
            )
            self.assertEqual(config.path("logs.json"), Path(directory) / "logs.json")
            config.validate_runtime()

            with self.assertRaises(RuntimeError):
                AppConfig(
                    root_dir=Path(directory), token=None, server_id="123",
                    tojao_id=None, log_channel_id=None, mute_role_id=None,
                    owner_id=None, nvidia_api_key=None,
                ).validate_runtime()


class StateAndWordTests(unittest.TestCase):
    def test_state_defaults_and_word_transitions(self):
        state = BotState()
        self.assertEqual((state.contador, state.propaganda), (0, 0))
        context = SimpleNamespace(state=state)
        service = WordService(context)
        service.set_word("CaFe")
        self.assertTrue(service.contains_forbidden_word("um cafe aqui"))
        service.set_message_limit(2)
        self.assertFalse(service.increment_message_counter())
        self.assertTrue(service.increment_message_counter())
        service.clear()
        self.assertIsNone(state.palavra_mute)


class FirstRepositoryTests(unittest.TestCase):
    def test_setup_count_adjust_and_monthly_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = FirstRepository(Path(directory) / "discord_bot.db")
            repository.setup()
            self.assertEqual(repository.update_user_first_count("1", "Alice"), 1)
            self.assertEqual(repository.update_user_first_count("1", "Alice"), 2)
            self.assertEqual(repository.adjust_first_count("1", "Alice", -5), 0)
            self.assertEqual(repository.get_user("1"), ("Alice", 0))
            repository.adjust_first_count("2", "Bob", 3)
            self.assertEqual(repository.count_users(), 2)
            self.assertEqual(repository.get_top_users(0, 10)[0], ("Bob", 3))
            repository.log_first_event("1", "Alice", datetime(2026, 9, 1, tzinfo=timezone.utc))
            repository.log_first_event("1", "Alice", datetime(2026, 9, 2, tzinfo=timezone.utc))
            repository.log_first_event("2", "Bob", datetime(2026, 9, 3, tzinfo=timezone.utc))
            self.assertEqual(repository.get_top_users_with_ids(25)[0], ("2", "Bob", 3))
            self.assertEqual(
                repository.get_monthly_firsts(2026, 9),
                [("1", "Alice", 2), ("2", "Bob", 1)],
            )


class MemoryTests(unittest.TestCase):
    def make_service(self, directory, nvidia=None):
        config = SimpleNamespace(path=lambda name: Path(directory) / name)
        context = SimpleNamespace(config=config, nvidia=nvidia)
        return MemoryService(context)

    def test_structured_operations_include_scope_confidence_and_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(directory)
            state = {"__memory_entries__": []}
            counts = service._apply_operations(
                state,
                {
                    "add": [
                        {
                            "scope": "user", "scope_id": "7", "category": "preference",
                            "key": "language", "value": "portugues", "confidence": 0.9,
                            "ttl_days": 10,
                        },
                        {
                            "scope": "channel", "scope_id": "55", "category": "context",
                            "key": "topic", "value": "jogos", "confidence": 0.8,
                        },
                    ],
                    "update": [], "delete": [], "ignore": [],
                },
                channel_id="55", channel_name="geral", users={"7": "Alice"},
            )
            self.assertEqual(counts["add"], 2)
            entry = state["__memory_entries__"][0]
            self.assertEqual(entry["scope"], "user")
            self.assertEqual(entry["scope_id"], "7")
            self.assertIn("created_at", entry)
            self.assertIn("expires_at", entry)
            self.assertIn("Alice", service._render(state, channel_id="55", user_ids={"7"}))

            conflict = service._apply_operations(
                state,
                {"add": [{
                    "scope": "user", "scope_id": "7", "category": "preference",
                    "key": "language", "value": "ingles", "confidence": 0.9,
                }], "update": [], "delete": [], "ignore": []},
                channel_id="55", channel_name="geral", users={"7": "Alice"},
            )
            self.assertEqual(conflict["conflict"], 1)
            self.assertEqual(len(entry["conflicts"]), 1)

            deleted = service._apply_operations(
                state,
                {"add": [], "update": [], "delete": [{
                    "scope": "channel", "scope_id": "55", "key": "topic",
                }], "ignore": []},
                channel_id="55", channel_name="geral", users={"7": "Alice"},
            )
            self.assertEqual(deleted["delete"], 1)

    def test_markdown_changes_create_versioned_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(directory)
            service.memory_path.write_text("old memory\n", encoding="utf-8")
            service._write_markdown("new memory")
            backups = list((Path(directory) / "memory_backups").glob("MEMORY-*.md"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "old memory\n")

    def test_custom_memory_is_persisted_and_delimited(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(directory)
            entry = service.add_custom_memory(
                "sempre responder com contexto adicional",
                user_id=7,
                user_name="Alice",
            )
            self.assertEqual(entry["created_by_id"], "7")
            markdown = service.all_text()
            self.assertIn("<!-- Custom -->", markdown)
            self.assertIn("## Custom", markdown)
            self.assertIn("sempre responder com contexto adicional", markdown)
            self.assertIn("<!-- /Custom -->", markdown)
            state = service.memory_store.load({})
            self.assertEqual(len(state["__custom_memory__"]), 1)


class FakeNvidia:
    def __init__(self, response='{"add":[],"update":[],"delete":[],"ignore":[]}'):
        self.response = response
        self.calls = []

    async def chat(self, model, messages, **kwargs):
        self.calls.append((model, messages, kwargs))
        return self.response, None

    @staticmethod
    def is_rate_limit_error(error):
        return False

    @staticmethod
    def supports_reasoning(model):
        return model.startswith("deepseek")


class AITests(unittest.IsolatedAsyncioTestCase):
    async def test_ai_service_uses_fake_nvidia_and_writes_history(self):
        with tempfile.TemporaryDirectory() as directory:
            nvidia = FakeNvidia("resposta do modelo")
            config = SimpleNamespace(path=lambda name: Path(directory) / name)
            context = SimpleNamespace(
                config=config,
                nvidia=nvidia,
                history_store=JsonStore(Path(directory) / "conversation_history.json"),
            )
            service = AIService(context)
            service.memory.record_turn = AsyncMock()
            answer = await service.get_response(
                channel_id="12", author_name="Alice", user_id=7,
                message_text="ola", channel_name="geral",
            )
            self.assertEqual(answer, "resposta do modelo")
            self.assertEqual(nvidia.calls[0][0], service.current_model)
            history = json.loads((Path(directory) / "conversation_history.json").read_text())
            self.assertEqual(history["__ai_logs__"][0]["user_name"], "Alice")
            service.memory.record_turn.assert_awaited_once()

    async def test_ai_service_accepts_a_one_call_model_override(self):
        with tempfile.TemporaryDirectory() as directory:
            nvidia = FakeNvidia("resposta especifica")
            config = SimpleNamespace(path=lambda name: Path(directory) / name)
            context = SimpleNamespace(
                config=config,
                nvidia=nvidia,
                history_store=JsonStore(Path(directory) / "history.json"),
            )
            service = AIService(context)
            service.memory.record_turn = AsyncMock()
            answer = await service.get_response(
                channel_id="12", author_name="Alice", user_id=7,
                message_text="teste", model_override="moonshotai/kimi-k3",
            )
            self.assertEqual(answer, "resposta especifica")
            self.assertEqual(nvidia.calls[0][0], "moonshotai/kimi-k3")
            self.assertEqual(service.current_model, DEFAULT_MODEL)

    async def test_memory_summary_parses_json_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            response = json.dumps({"add": [{
                "scope": "user", "scope_id": "7", "category": "fact",
                "key": "name", "value": "Alice", "confidence": 0.95,
            }], "update": [], "delete": [], "ignore": []})
            nvidia = FakeNvidia(response)
            service = MemoryTests().make_service(directory, nvidia)
            service.SUMMARY_BATCH_SIZE = 1
            service.context.nvidia = nvidia
            state = {"__memory_buffers__": {"55": [
                {"role": "user", "content": "meu nome e Alice", "user_name": "Alice", "user_id": "7"},
                {"role": "assistant", "content": "entendido"},
            ]}, "__memory_entries__": []}
            service.memory_store.save(state)
            await service._summarize("55", "geral")
            saved = service.memory_store.load({})
            self.assertEqual(saved["__memory_buffers__"]["55"], [])
            self.assertEqual(saved["__memory_entries__"][0]["scope"], "user")

    async def test_ai_service_executes_web_search_tool_and_continues_conversation(self):
        class FakeSearch:
            def __init__(self):
                self.calls = []

            async def search(self, query, max_results):
                self.calls.append((query, max_results))
                return {
                    "provider": "fake",
                    "query": query,
                    "results": [{
                        "title": "resultado de teste",
                        "url": "https://example.com",
                        "snippet": "informacao encontrada",
                    }],
                }

        class ToolNvidia:
            def __init__(self, responses):
                self.responses = list(responses)
                self.calls = []

            async def chat_completion(self, model, messages, **kwargs):
                self.calls.append({
                    "model": model,
                    "messages": [dict(message) for message in messages],
                    "kwargs": kwargs,
                })
                return self.responses.pop(0)

            @staticmethod
            def is_rate_limit_error(error):
                return False

            @staticmethod
            def is_context_length_error(error):
                return False

        tool_call = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "web_search",
                "arguments": json.dumps({
                    "query": "noticia de teste",
                    "max_results": 2,
                }),
            },
        }
        nvidia = ToolNvidia([
            NvidiaCompletion(
                content="",
                reasoning_content="vou pesquisar",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                message={
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": "vou pesquisar",
                    "tool_calls": [tool_call],
                },
            ),
            NvidiaCompletion(
                content="encontrei a informacao.",
                reasoning_content=None,
                finish_reason="stop",
                message={"role": "assistant", "content": "encontrei a informacao."},
            ),
        ])
        search = FakeSearch()
        with tempfile.TemporaryDirectory() as directory:
            config = SimpleNamespace(path=lambda name: Path(directory) / name)
            context = SimpleNamespace(
                config=config,
                nvidia=nvidia,
                tools=ToolRegistry(search),
                history_store=JsonStore(Path(directory) / "history.json"),
            )
            service = AIService(context)
            service.memory.record_turn = AsyncMock()

            answer = await service.get_response(
                channel_id="12",
                author_name="Alice",
                user_id=7,
                message_text="qual e a noticia?",
            )

        self.assertEqual(answer, "encontrei a informacao.")
        self.assertEqual(search.calls, [("noticia de teste", 2)])
        self.assertEqual(len(nvidia.calls), 2)
        self.assertEqual(nvidia.calls[0]["kwargs"]["tools"][0]["function"]["name"], "web_search")
        self.assertEqual(nvidia.calls[1]["messages"][-1]["role"], "tool")
        self.assertEqual(
            nvidia.calls[1]["messages"][-1]["tool_call_id"],
            "call-1",
        )


class WebSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_duckduckgo_response_is_reduced_to_search_context(self):
        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "Heading": "titulo",
                    "AbstractText": "descricao",
                    "AbstractURL": "https://example.com",
                    "RelatedTopics": [],
                }

        with patch(
            "app.services.web_search_service.requests.get",
            return_value=Response(),
        ) as request:
            result = await WebSearchService().search("teste", 1)

        self.assertEqual(result["provider"], "duckduckgo_instant_answer")
        self.assertEqual(result["results"][0]["url"], "https://example.com")
        self.assertEqual(request.call_args.kwargs["params"]["q"], "teste")

    async def test_tool_registry_rejects_unknown_tools(self):
        registry = ToolRegistry(SimpleNamespace())
        result = await registry.execute_call({
            "function": {
                "name": "executar_codigo",
                "arguments": "{}",
            }
        })
        self.assertIn("nao permitida", result["error"])


class VisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_image_is_sent_as_multimodal_data_to_kimi(self):
        nvidia = FakeNvidia("a caveira esta visivel")
        service = VisionService(nvidia)
        data_uri = service._to_data_uri("images/acorda.png")
        self.assertTrue(data_uri.startswith("data:image/png;base64,"))
        await service.describe(["images/acorda.png"], "o que aparece?")
        model, messages, _ = nvidia.calls[0]
        self.assertEqual(model, "moonshotai/kimi-k3")
        content = messages[0]["content"]
        self.assertIsInstance(content, list)
        self.assertTrue(any(item["type"] == "image_url" for item in content))


class ModerationAndPermissionTests(unittest.TestCase):
    def test_duration_parser_and_permission_guard(self):
        service = ModerationService(SimpleNamespace())
        self.assertEqual(service.parse_duration("1h30m20s"), 5420)
        self.assertEqual(service.parse_duration("invalido"), 0)
        interaction = SimpleNamespace(
            guild_id=123,
            user=SimpleNamespace(guild_permissions=SimpleNamespace(moderate_members=True)),
        )
        context = SimpleNamespace(config=SimpleNamespace(server_int=123))
        self.assertTrue(is_moderator(interaction, context))


class FakeTyping:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class EventTests(unittest.IsolatedAsyncioTestCase):
    async def test_mention_event_delegates_to_ai(self):
        class BotUser:
            id = 99

            def mentioned_in(self, message):
                return True

        class Channel:
            id = 55
            name = "geral"

            def typing(self):
                return FakeTyping()

        author = SimpleNamespace(
            bot=False, id=7, name="Alice", display_name="Alice", mention="<@7>"
        )
        message = SimpleNamespace(
            author=author, guild=SimpleNamespace(id=123), channel=Channel(),
            content="<@99> ola", attachments=[], embeds=[], reference=None, id=1,
            reply=AsyncMock(),
        )
        context = SimpleNamespace(
            config=SimpleNamespace(server_id="123"),
            ai=SimpleNamespace(get_response=AsyncMock(return_value="resposta")),
            logging=SimpleNamespace(log_ai_interaction=AsyncMock()),
            state=BotState(),
        )
        bot = SimpleNamespace(user=BotUser(), process_commands=AsyncMock())
        await MessageEventHandler(bot, context).on_message(message)
        context.ai.get_response.assert_awaited_once()
        message.reply.assert_awaited_once_with("resposta")

    async def test_reaction_and_delete_events_delegate(self):
        propaganda = SimpleNamespace(
            handle_reaction_unlock=AsyncMock(), handle_deleted_message=AsyncMock()
        )
        context = SimpleNamespace(propaganda=propaganda)
        handler = ReactionEventHandler(context)
        await handler.on_reaction_add(SimpleNamespace(), SimpleNamespace(bot=False))
        await handler.on_message_delete(SimpleNamespace())
        propaganda.handle_reaction_unlock.assert_awaited_once()
        propaganda.handle_deleted_message.assert_awaited_once()


class RegistryTests(unittest.TestCase):
    def test_all_commands_are_registered_explicitly(self):
        from bot import MSBot

        bot = MSBot()
        commands = register_all_commands(bot.tree, bot.context)
        names = {command.name for command in commands}
        expected = {
            "conversar", "adicionamemoria", "enviarmsgllm", "respondermsgllm", "alterarmodelo", "alterarthinking",
            "vermemoria", "resetamemoria", "novapalavra", "redefinepalavra",
            "mostrapalavra", "escolhepalavra", "escolhenummensagens", "mantempalavra",
            "significado", "mudaconfigpropaganda", "enviapropaganda", "desbloqueiachat",
            "bloqueiachat", "adicionafirst", "removefirst", "top10first", "buscafirsts",
            "enviarmsg", "baixarvideo", "respondermsg", "mutar", "desmutar", "mensagemdivina",
        }
        self.assertEqual(names, expected)
        self.assertEqual(len(names), len(commands))
        adicionamemoria = next(command for command in commands if command.name == "adicionamemoria")
        self.assertTrue(adicionamemoria._params["memoria"].required)
        enviarmsgllm = next(command for command in commands if command.name == "enviarmsgllm")
        options = {option.name: option for option in enviarmsgllm._params.values()}
        self.assertTrue(options["prompt"].required)
        self.assertFalse(options["modelo"].required)


if __name__ == "__main__":
    unittest.main()
