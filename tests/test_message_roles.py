import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from app.persistence.message_repository import MessageRepository
from app.tools.context_tools import ContextTools


class MessageCountTests(unittest.TestCase):
    def test_persistence_deduplication_and_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "messages.db"
            repository = MessageRepository(path)
            for item in [(1, 10, 20), (1, 10, 20), (2, 10, 20), (3, 11, 20), (4, 10, 21)]:
                repository.record(*item)
            restored = MessageRepository(path)
            self.assertEqual(restored.count(10, 20)["message_count"], 2)
            self.assertEqual(restored.count(10, 99)["message_count"], 0)
            self.assertFalse(restored.count(10, 20)["is_lifetime_total"])
            self.assertEqual(repository.count(10, 20)["tracking_since"], restored.count(10, 20)["tracking_since"])


class Role:
    def __init__(self, role_id, position):
        self.id, self.position = role_id, position
        self.name, self.managed = "cargo", False

    def is_default(self):
        return False

    def __ge__(self, other):
        return self.position >= other.position


class RoleTests(unittest.IsolatedAsyncioTestCase):
    async def test_removal_targets_noop_and_denials(self):
        role = Role(1194700649301020763, 1)
        member = NS(roles=[role, Role(999, 2)], remove_roles=AsyncMock())
        guild = NS(fetch_member=AsyncMock(return_value=member), get_role=lambda rid: role if rid == role.id else None,
                   me=NS(guild_permissions=NS(manage_roles=True), top_role=Role(1, 5)))
        tools = ContextTools(NS(), 55, 7)
        tools.channel = AsyncMock(return_value=NS(guild=guild))
        for name, role_id in [("remove_platelminto", 1194700649301020763),
                              ("remove_homunco", 1194723205022232637),
                              ("remove_quarentena", 1194720159416467527)]:
            role.id = role_id
            result = await getattr(tools, name)("motivo")
            self.assertEqual(result["status"], "removed")
            self.assertEqual(result["role_id"], str(role_id))
            member.remove_roles.assert_awaited_with(role, reason="LLM: motivo", atomic=True)
        guild.fetch_member.assert_awaited_with(7)
        member.remove_roles.reset_mock()
        member.roles = []
        self.assertEqual((await tools.remove_quarentena("motivo"))["status"], "already_absent")
        member.roles = [role]
        guild.me.guild_permissions.manage_roles = False
        with self.assertRaises(ValueError):
            await tools.remove_quarentena("motivo")
        guild.me.guild_permissions.manage_roles = True
        role.position = 6
        with self.assertRaises(ValueError):
            await tools.remove_quarentena("motivo")
        role.position, role.managed = 1, True
        with self.assertRaises(ValueError):
            await tools.remove_quarentena("motivo")
        guild.get_role = lambda rid: None
        with self.assertRaises(ValueError):
            await tools.remove_quarentena("motivo")
        member.remove_roles.assert_not_awaited()

    async def test_fixed_roles_current_author_and_permission_checks(self):
        member = NS(roles=[], add_roles=AsyncMock())
        role = Role(1194700649301020763, 1)
        guild = NS(fetch_member=AsyncMock(return_value=member), get_role=lambda _: role,
                   me=NS(guild_permissions=NS(manage_roles=True), top_role=Role(1, 5)))
        tools = ContextTools(NS(), 55, 7)
        tools.channel = AsyncMock(return_value=NS(guild=guild))
        for name, role_id in [("give_platelminto", 1194700649301020763),
                              ("give_homunco", 1194723205022232637),
                              ("give_quarentena", 1194720159416467527)]:
            role.id = role_id
            result = await getattr(tools, name)("motivo")
            self.assertEqual(result["role_id"], str(role_id))
            self.assertEqual(result["user_id"], "7")
        guild.fetch_member.assert_awaited_with(7)
        member.add_roles.reset_mock()
        member.roles = [role]
        self.assertEqual((await tools.give_quarentena("motivo"))["status"], "already_assigned")
        member.roles = []
        guild.me.guild_permissions.manage_roles = False
        with self.assertRaises(ValueError):
            await tools.give_quarentena("motivo")
        guild.me.guild_permissions.manage_roles = True
        role.position = 6
        with self.assertRaises(ValueError):
            await tools.give_quarentena("motivo")
        member.add_roles.assert_not_awaited()
