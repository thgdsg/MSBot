from __future__ import annotations

from app.commands.ai_commands import register_commands as register_ai_commands
from app.commands.first_commands import register_commands as register_first_commands
from app.commands.moderation_commands import register_commands as register_moderation_commands
from app.commands.propaganda_commands import register_commands as register_propaganda_commands
from app.commands.word_commands import register_commands as register_word_commands


def register_all_commands(tree, context) -> list:
    """Register every application command explicitly and return the registered list."""
    registered = []
    for register in (
        register_ai_commands,
        register_word_commands,
        register_propaganda_commands,
        register_first_commands,
        register_moderation_commands,
    ):
        for command in register(tree, context):
            tree.add_command(command)
            registered.append(command)
    return registered
