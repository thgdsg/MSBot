from __future__ import annotations

from datetime import datetime


class FirstService:
    def __init__(self, context):
        self.context = context
        self.repository = context.first_repository

    def setup(self) -> None:
        self.repository.setup()

    async def reset_daily(self, guild) -> None:
        print("00:00 (SP), resetando flag 'first' e removendo cargos.")
        self.context.state.flag_first = False
        self.context.history_store.save({})
        print("conversation_history.json foi limpo no reset diario.")

        if not guild:
            return
        import discord

        role = discord.utils.get(guild.roles, name="first")
        if not role:
            return
        for member in list(role.members):
            try:
                await member.remove_roles(role)
                print(f"Cargo 'first' removido de {member.name}")
            except discord.Forbidden:
                print(f"Sem permissao para remover cargo de {member.name}")
            except discord.HTTPException as error:
                print(f"Falha ao remover cargo de {member.name}: {error}")

    async def claim_first(self, message, now: datetime) -> bool:
        if self.context.state.flag_first or "first" not in message.content.lower():
            return False

        async with self.context.state.lock:
            if self.context.state.flag_first:
                return False
            self.context.state.flag_first = True
            import discord

            role = discord.utils.get(message.guild.roles, name="first")
            if role:
                await message.author.add_roles(role)
                print(f"Usuario {message.author.name} recebeu o cargo 'first'.")
            await message.channel.send(
                f"Parabens {message.author.mention}, voce foi o primeiro a falar 'first' hoje!"
            )
            user_id = str(message.author.id)
            self.repository.update_user_first_count(user_id, message.author.name)
            self.repository.log_first_event(user_id, message.author.name, now)
            return True

    def top_users(self, offset: int, limit_end: int):
        return self.repository.get_top_users(offset, limit_end)

    def count_users(self) -> int:
        return self.repository.count_users()

    def top_users_for_month(self, year: int, month: int):
        return self.repository.get_top_users_for_month(year, month)

    async def fetch_user(self, user_id: str):
        return await self.context.bot.fetch_user(int(user_id))

    def adjust_first_count(self, user_id: str, username: str, amount: int) -> int:
        return self.repository.adjust_first_count(user_id, username, amount)

    def get_user(self, user_id: str):
        return self.repository.get_user(user_id)
