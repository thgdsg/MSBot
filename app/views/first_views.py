from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord


try:
    SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:  # Windows without an installed IANA tz database.
    SAO_PAULO_TZ = timezone(timedelta(hours=-3))


class SimpleLeaderboardView(discord.ui.View):
    def __init__(self, first_service, user_id: int, timeout: int = 10):
        super().__init__(timeout=timeout)
        self.first_service = first_service
        self.user_id = user_id
        self.message = None
        self.mn = 0
        self.mx = 10

    async def on_timeout(self) -> None:
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                print("A mensagem do placar nao foi encontrada para editar no timeout.")

    @discord.ui.button(label="previous", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Voce nao tem permissao para usar este botao.", ephemeral=True
            )
            return
        if self.mx <= 10:
            await interaction.response.defer()
            return
        self.mn -= 10
        self.mx -= 10
        await interaction.response.edit_message(content=self.content())

    @discord.ui.button(label="next", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Voce nao tem permissao para usar este botao.", ephemeral=True
            )
            return
        if self.first_service.count_users() <= self.mx:
            await interaction.response.defer()
            return
        self.mn += 10
        self.mx += 10
        await interaction.response.edit_message(content=self.content())

    def content(self) -> str:
        response = self.first_service.top_users(self.mn, self.mx)
        formatted = "\n".join(
            f"{self.mn + index + 1}. {username}: {count}"
            for index, (username, count) in enumerate(response)
        )
        return f"# HALL DA FAMA\n**Top 10 usuarios com mais first:**\n{formatted}"


class MonthlyLeaderboardView(discord.ui.View):
    def __init__(self, first_service, user_id: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.first_service = first_service
        self.user_id = user_id
        self.message = None
        self.current_date = datetime.now(SAO_PAULO_TZ)

    async def on_timeout(self) -> None:
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                print("A mensagem do placar mensal nao foi encontrada para editar no timeout.")

    def content(self) -> str:
        response = self.first_service.top_users_for_month(
            self.current_date.year,
            self.current_date.month,
        )
        formatted = (
            "Nenhum 'first' registrado para este mes."
            if not response
            else "\n".join(
                f"{index + 1}. {username}: {count}"
                for index, (username, count) in enumerate(response)
            )
        )
        months = {
            1: "Janeiro", 2: "Fevereiro", 3: "Marco", 4: "Abril",
            5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
            9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
        }
        month_name = months.get(self.current_date.month, str(self.current_date.month))
        return (
            f"# HALL DA FAMA (MENSAL)\n**Top 10 para {month_name} de "
            f"{self.current_date.year}:**\n{formatted}"
        )

    @discord.ui.button(label="Mes Anterior", style=discord.ButtonStyle.blurple)
    async def previous_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Voce nao tem permissao para usar este botao.", ephemeral=True
            )
            return
        if self.current_date.month == 1:
            self.current_date = self.current_date.replace(
                year=self.current_date.year - 1,
                month=12,
            )
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month - 1)
        await interaction.response.edit_message(content=self.content(), view=self)

    @discord.ui.button(label="Proximo Mes", style=discord.ButtonStyle.blurple)
    async def next_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Voce nao tem permissao para usar este botao.", ephemeral=True
            )
            return
        now = datetime.now(SAO_PAULO_TZ)
        if self.current_date.month == 12:
            next_date = self.current_date.replace(year=self.current_date.year + 1, month=1)
        else:
            next_date = self.current_date.replace(month=self.current_date.month + 1)
        if next_date > now:
            await interaction.response.send_message(
                "Nao e possivel ver o placar de meses futuros.", ephemeral=True
            )
            return
        self.current_date = next_date
        await interaction.response.edit_message(content=self.content(), view=self)
