from __future__ import annotations


class ReactionEventHandler:
    def __init__(self, context):
        self.context = context

    async def on_reaction_add(self, reaction, user) -> None:
        if user.bot:
            return
        await self.context.propaganda.handle_reaction_unlock(reaction)

    async def on_message_delete(self, message) -> None:
        await self.context.propaganda.handle_deleted_message(message)
