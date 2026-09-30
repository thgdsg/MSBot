import json
import socket
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from app.events.message_events import MessageEventHandler
from app.persistence.first_repository import FirstRepository
from app.services.ai_service import AIService
from app.tools.context_tools import ContextTools
from app.tools.public_tools import public_address, fetch_url, weather, dictionary_lookup
from app.tools.registry import ToolRegistry


def message(number, text="texto"):
    return NS(id=number, content=text, author=NS(id=7, display_name="alice", name="alice", bot=False),
              created_at=datetime.now(timezone.utc), attachments=[], embeds=[], reference=None,
              mentions=[], reply=AsyncMock())


class ToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.member = NS(id=7)
        self.guild = NS(id=123, me=NS(id=99), default_role=NS(id=123),
                        get_member=lambda uid: self.member)
        self.channel = NS(id=55, guild=self.guild,
                          permissions_for=lambda actor: NS(view_channel=True, read_message_history=True))
        self.context = NS(config=NS(server_id="123"), bot=NS(get_channel=lambda cid: self.channel))
        self.tools = ContextTools(self.context, "55", "7")

    async def test_recent_and_specific_message(self):
        async def history(*, limit):
            self.assertEqual(limit, 5)
            for n in range(5, 0, -1):
                yield message(n)
        self.channel.history = history
        self.channel.fetch_message = AsyncMock(return_value=message(3))
        self.assertEqual([m["message_id"] for m in (await self.tools.recent_messages())["messages"]],
                         ["1", "2", "3", "4", "5"])
        self.assertEqual((await self.tools.get_message("3"))["message_id"], "3")
        self.channel.fetch_message.assert_awaited_once_with(3)

    async def test_denied_channel_and_foreign_guild(self):
        self.channel.permissions_for = lambda actor: NS(view_channel=False, read_message_history=True)
        with self.assertRaises(ValueError):
            await self.tools.recent_messages()
        self.guild.id = 456
        with self.assertRaises(ValueError):
            await self.tools.get_message("3")

    async def test_private_channel_not_exported(self):
        self.channel.id = 56
        self.channel.permissions_for = lambda actor: NS(
            view_channel=actor is not self.guild.default_role, read_message_history=True)
        with self.assertRaises(ValueError):
            await self.tools.channel("56")

    async def test_firsts_and_memory_filters(self):
        import asyncio
        from app.services.memory_service import MemoryService
        with tempfile.TemporaryDirectory() as directory:
            repository = FirstRepository(Path(directory) / "first.db")
            repository.setup()
            repository.adjust_first_count("7", "alice", 4)
            self.context.first_repository = repository
            self.assertEqual((await self.tools.first_count())["first_count"], 4)
            self.assertEqual((await self.tools.first_count("8"))["first_count"], 0)
            entries = [
                {"scope": "user", "scope_id": "7", "key": "jogo", "value": "xadrez"},
                {"scope": "user", "scope_id": "8", "key": "jogo", "value": "outro"},
                {"scope": "user", "scope_id": "7", "key": "jogo", "value": "antigo",
                 "expires_at": "2000-01-01T00:00:00+00:00"},
                {"scope": "global", "scope_id": "server", "value": "regra"},
            ]
            self.context.ai = NS(memory=NS(lock=asyncio.Lock(), _expired=MemoryService._expired,
                _load_state=lambda: {"__memory_entries__": entries, "__custom_memory__": [{"content": "custom"}]}))
            found = await self.tools.memory_search("user", "xadrez")
            self.assertEqual(found["total"], 1)
            self.assertEqual((await self.tools.memory_search("server"))["total"], 2)

    async def test_first_rankings_include_position_username_nickname_and_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = FirstRepository(Path(directory) / "first.db")
            repository.setup()
            repository.adjust_first_count("7", "old-alice", 9)
            repository.adjust_first_count("8", "bob", 4)
            repository.log_first_event("7", "old-alice", datetime(2026, 9, 1, tzinfo=timezone.utc))
            repository.log_first_event("7", "old-alice", datetime(2026, 9, 2, tzinfo=timezone.utc))
            repository.log_first_event("8", "bob", datetime(2026, 9, 3, tzinfo=timezone.utc))
            self.context.first_repository = repository
            self.member = NS(id=7, name="alice", nick="Alice no servidor")
            self.guild.get_member = lambda uid: self.member if uid == 7 else None
            self.guild.fetch_member = AsyncMock(side_effect=ValueError("ausente"))
            top = await self.tools.top_firsts()
            monthly = await self.tools.monthly_firsts(2026, 9)
            self.assertEqual(top["ranking"][0], {
                "position": 1, "user_id": "7", "username": "alice",
                "nickname": "Alice no servidor", "first_count": 9,
            })
            self.assertEqual(monthly["total_unique_users"], 2)
            self.assertEqual(monthly["ranking"][0]["first_count"], 2)
            self.assertEqual(monthly["ranking"][1]["user_id"], "8")
            self.assertEqual(monthly["ranking"][1]["username"], "bob")
            self.assertIsNone(monthly["ranking"][1]["nickname"])

    async def test_monthly_firsts_validates_date(self):
        with self.assertRaises(ValueError):
            await self.tools.monthly_firsts(2026, 13)

    async def test_user_profile_returns_discord_fields_and_bounded_activity(self):
        role = NS(name="membro")
        permissions = NS(administrator=False, manage_guild=False, manage_messages=True,
                         moderate_members=False, kick_members=False, ban_members=False,
                         mention_everyone=True, attach_files=True)
        self.member = NS(
            id=7, name="alice", nick="Alice", display_name="Alice", roles=[role],
            joined_at=datetime(2025, 1, 2, tzinfo=timezone.utc), pending=False,
            premium_since=None, communication_disabled_until=None,
            guild_permissions=permissions,
        )
        self.guild.get_member = lambda uid: self.member if uid == 7 else None
        self.guild.name = "Menes Suecos"
        self.channel.name = "geral"

        async def history(*, limit):
            self.assertEqual(limit, 20)
            yield message(10, "mensagem da alice")
            yield NS(id=11, content="de outra pessoa", author=NS(id=8),
                     created_at=datetime.now(timezone.utc), attachments=[])

        self.channel.history = history
        self.guild.text_channels = [self.channel]
        self.context.bot.get_user = Mock(return_value=None)
        self.context.bot.fetch_user = AsyncMock(return_value=NS(
            id=7, name="alice", global_name="Alice Global", display_name="Alice",
            mention="<@7>", discriminator="0", bot=False, system=False,
            created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            avatar=NS(url="https://cdn.example/avatar.png"),
            banner=NS(url="https://cdn.example/banner.png"),
            accent_color=None, public_flags=NS(value=0),
        ))

        profile = await self.tools.user_profile()
        self.assertEqual(profile["username"], "alice")
        self.assertEqual(profile["membership"]["joined_at"], "2025-01-02T00:00:00+00:00")
        self.assertEqual(profile["message_activity"]["messages"][0]["content"], "mensagem da alice")
        self.assertIn("bio", profile["unavailable_fields"])
        self.context.bot.fetch_user.assert_awaited_once_with(7)

    async def test_registry_validation_and_request_isolation(self):
        search = NS(search=AsyncMock(return_value={"results": []}))
        registry = ToolRegistry(search, self.context)
        self.assertEqual([d["function"]["name"] for d in registry.definitions()][:10],
                         ["memory_search", "recent_messages", "fetch_url", "weather", "first_count",
                          "top_firsts", "monthly_firsts", "user_profile", "get_message", "dictionary"])
        a, b = registry.bind("55", "7"), registry.bind("56", "8")
        self.assertEqual(a.local.user_id, "7")
        self.assertEqual(b.local.user_id, "8")
        for args in ({"query": "x", "max_results": True}, {"query": "x", "extra": 1}):
            result = await registry.execute_call({"function": {"name": "web_search", "arguments": json.dumps(args)}})
            self.assertIn("error", result)
        search.search.assert_not_awaited()

    async def test_dictionary_modes(self):
        search = NS(search=AsyncMock(return_value={"results": []}))
        with patch("app.tools.public_tools.local_definition", return_value={"definition": "sentido"}):
            result = await dictionary_lookup(search, "casa")
            self.assertEqual(result["definition"], "sentido")
            search.search.assert_not_awaited()
            await dictionary_lookup(search, "casa", "synonyms")
            await dictionary_lookup(search, "casa", "translation", "ingles")
            self.assertEqual(search.search.await_count, 2)
            with self.assertRaises(ValueError):
                await dictionary_lookup(search, "casa", "translation")


class PublicTests(unittest.TestCase):
    def test_private_dns_addresses_are_blocked(self):
        for ip in ("127.0.0.1", "10.0.0.2", "169.254.169.254", "::1"):
            with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 80))]):
                with self.assertRaises(ValueError):
                    public_address("example.com", 80)

    def test_fetch_strips_scripts_and_caps_text(self):
        with patch("app.tools.public_tools.download", return_value=(
            "https://example.com", "text/html", "<p>contexto</p><script>malicioso</script><p>" + "x" * 9000 + "</p>")):
            result = fetch_url("https://example.com")
            self.assertNotIn("malicioso", result["text"])
            self.assertTrue(result["truncated"])
            self.assertEqual(len(result["text"]), 8000)

    def test_weather_location_and_units(self):
        with patch("app.tools.public_tools.download", side_effect=[
            ("", "", json.dumps({"results": [{"name": "Recife", "country": "Brasil", "latitude": -8, "longitude": -34}]})),
            ("", "", json.dumps({"current": {"temperature_2m": 28}, "current_units": {"temperature_2m": "C"}})),
        ]):
            result = weather("Recife", "BR")
            self.assertEqual(result["location"]["name"], "Recife")
            self.assertEqual(result["current"]["temperature_2m"], 28)


class Typing:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class SpontaneousTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self, mentioned=False, image=False):
        msg = message(100, "" if image else "uma conversa")
        msg.guild = NS(id=123)
        msg.channel = NS(id=55, name="geral", typing=Typing)
        if image:
            msg.attachments = [NS(content_type="image/png", filename="a.png", url="https://example.com/a.png")]
        context = NS(config=NS(server_id="123", tojao_id=None),
            state=NS(mensagem_block=True),
            ai=NS(get_response=AsyncMock(return_value="minha opiniao")),
            logging=NS(log_ai_interaction=AsyncMock()),
            word=NS(contains_forbidden_word=lambda text: False),
            first=NS(claim_first=AsyncMock()))
        bot = NS(user=NS(id=99, mentioned_in=lambda message: mentioned), process_commands=AsyncMock())
        return MessageEventHandler(bot, context), msg, context

    async def test_lottery_winner_with_image(self):
        handler, msg, context = self.fixture(image=True)
        with patch("app.events.message_events.random.randrange", return_value=0) as draw:
            await handler.on_message(msg)
        draw.assert_called_once_with(100)
        kwargs = context.ai.get_response.call_args.kwargs
        self.assertTrue(kwargs["spontaneous"])
        self.assertEqual(kwargs["image_urls"], ["https://example.com/a.png"])
        msg.reply.assert_awaited_once()
        context.first.claim_first.assert_awaited_once()

    async def test_lottery_loser_and_mentions(self):
        handler, msg, context = self.fixture()
        with patch("app.events.message_events.random.randrange", return_value=1):
            await handler.on_message(msg)
        context.ai.get_response.assert_not_awaited()
        handler, msg, context = self.fixture(mentioned=True)
        with patch("app.events.message_events.random.randrange") as draw:
            await handler.on_message(msg)
        draw.assert_not_called()
        context.ai.get_response.assert_awaited_once()

    async def test_spontaneous_prompt_and_vision(self):
        service = AIService.__new__(AIService)
        service.tools = None
        service.current_model = "fake"
        service.current_fallback_model = None
        service._system_prompt = Mock(return_value="system")
        service._append_history = Mock()
        service.vision = NS(describe=AsyncMock(return_value="uma caveira"))
        service.memory = NS(review_writing_style=AsyncMock(side_effect=lambda s: s), record_turn=AsyncMock())
        service._complete_with_tools = AsyncMock(return_value=NS(content="que caveira", reasoning_content=None))
        await service.get_response(channel_id="55", author_name="alice", user_id=7,
                                   message_text="", image_urls=["image"], spontaneous=True)
        messages = service._complete_with_tools.call_args.args[1]
        self.assertIn("NAO foi chamado", messages[0]["content"])
        self.assertIn("caveira", messages[-1]["content"])
        service.vision.describe.assert_awaited_once()
