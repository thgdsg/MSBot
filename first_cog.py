import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
from datetime import datetime
import pytz

MENES_SUECOS = os.getenv('MENES_SUECOS')
DAFONZ_ID = os.getenv('DAFONZ_ID')

def get_top_users_from_db(mn, mx):
    conn = sqlite3.connect('discord_bot.db')
    c = conn.cursor()
    c.execute('SELECT username, first_count FROM users ORDER BY first_count DESC LIMIT ? OFFSET ?', (mx - mn, mn))
    result = c.fetchall()
    conn.close()
    return result

def get_top_users_for_month(year, month, limit=10):
    conn = sqlite3.connect('discord_bot.db')
    c = conn.cursor()
    month_str = f"{year}-{month:02d}"
    query = """
        SELECT
            u.username,
            COUNT(fl.log_id) as monthly_first_count
        FROM
            first_logs fl
        JOIN
            users u ON fl.user_id = u.user_id
        WHERE
            strftime('%Y-%m', fl.timestamp) = ?
        GROUP BY
            fl.user_id
        ORDER BY
            monthly_first_count DESC
        LIMIT ?
    """
    c.execute(query, (month_str, limit))
    result = c.fetchall()
    conn.close()
    return result

class SimpleView(discord.ui.View):
    def __init__(self, user_id, timeout=10):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.message = None
        self.mn = 0
        self.mx = 10

    async def on_timeout(self) -> None:
        if self.message:
            for i in self.children:
                i.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                print("A mensagem do placar não foi encontrada para editar no timeout (pode ter sido deletada).")

    @discord.ui.button(label="previous", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return

        if self.mx > 10:
            self.mn -= 10
            self.mx -= 10
            response = get_top_users_from_db(self.mn, self.mx)
            formatted_response = "\n".join([f"{self.mn + index + 1}. {username}: {count}" for index, (username, count) in enumerate(response)])
            if self.message:
                await interaction.response.edit_message(content=f"# HALL DA FAMA\n**Top 10 usuários com mais first:**\n{formatted_response}")
        else:
            await interaction.response.defer()


    @discord.ui.button(label="next", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return

        conn = sqlite3.connect('discord_bot.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users')
        total_count = c.fetchone()[0]
        conn.close()

        if total_count > self.mx:
            self.mn += 10
            self.mx += 10
            response = get_top_users_from_db(self.mn, self.mx)
            formatted_response = "\n".join([f"{self.mn + index + 1}. {username}: {count}" for index, (username, count) in enumerate(response)])
            if self.message:
                await interaction.response.edit_message(content=f"# HALL DA FAMA\n**Top 10 usuários com mais first:**\n{formatted_response}")
        else:
            await interaction.response.defer()

class MonthlyLeaderboardView(discord.ui.View):
    def __init__(self, user_id, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.message = None
        self.current_date = datetime.now(pytz.timezone('America/Sao_Paulo'))

    async def on_timeout(self) -> None:
        if self.message:
            for i in self.children:
                i.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                print("A mensagem do placar mensal não foi encontrada para editar no timeout.")

    def format_leaderboard_message(self, year, month):
        response = get_top_users_for_month(year, month)
        if not response:
            formatted_response = "Nenhum 'first' registrado para este mês."
        else:
            formatted_response = "\n".join([f"{index + 1}. {username}: {count}" for index, (username, count) in enumerate(response)])
        
        meses_pt = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
            5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
            9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
        }
        month_name = meses_pt.get(month, f"Mês {month}")
        
        return f"# HALL DA FAMA (MENSAL)\n**Top 10 para {month_name} de {year}:**\n{formatted_response}"

    @discord.ui.button(label="Mês Anterior", style=discord.ButtonStyle.blurple)
    async def previous_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return

        if self.current_date.month == 1:
            self.current_date = self.current_date.replace(year=self.current_date.year - 1, month=12)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month - 1)

        content = self.format_leaderboard_message(self.current_date.year, self.current_date.month)
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="Próximo Mês", style=discord.ButtonStyle.blurple)
    async def next_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Você não tem permissão para usar este botão.", ephemeral=True)
            return

        now = datetime.now(pytz.timezone('America/Sao_Paulo'))
        
        next_month_date = self.current_date
        if self.current_date.month == 12:
            next_month_date = self.current_date.replace(year=self.current_date.year + 1, month=1)
        else:
            next_month_date = self.current_date.replace(month=self.current_date.month + 1)

        if next_month_date.year > now.year or (next_month_date.year == now.year and next_month_date.month > now.month):
            await interaction.response.send_message("Não é possível ver o placar de meses futuros.", ephemeral=True)
            return
        
        self.current_date = next_month_date
        content = self.format_leaderboard_message(self.current_date.year, self.current_date.month)
        await interaction.response.edit_message(content=content, view=self)

class FirstAdminCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @app_commands.command(name="adicionafirst", description="[ADM] Adiciona manualmente uma contagem de 'first' a um usuário.")
    async def adicionafirst(self, interaction: discord.Interaction, user_id: str, count: int):
        if str(interaction.user.id) == DAFONZ_ID:
            try:
                user = await self.client.fetch_user(user_id)
                conn = sqlite3.connect('discord_bot.db')
                c = conn.cursor()

                c.execute('SELECT first_count FROM users WHERE user_id = ?', (user_id,))
                result = c.fetchone()

                if result:
                    new_count = result[0] + count
                    c.execute('UPDATE users SET first_count = ? WHERE user_id = ?', (new_count, user_id))
                    await interaction.response.send_message(f"Contagem atualizada! Novo total para {user.name}: {new_count}", ephemeral=True)
                else:
                    c.execute('INSERT INTO users (user_id, username, first_count) VALUES (?, ?, ?)', (user_id, user.name, count))
                    await interaction.response.send_message(f"Usuário {user.name} adicionado com {count} 'first'.", ephemeral=True)

                conn.commit()
                conn.close()
            except discord.NotFound:
                await interaction.response.send_message("ID de usuário inválido.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Ocorreu um erro: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)

    @app_commands.command(name="removefirst", description="[ADM] Remove manualmente uma contagem de 'first' de um usuário.")
    async def removefirst(self, interaction: discord.Interaction, user_id: str, count: int):
        if str(interaction.user.id) == DAFONZ_ID:
            try:
                user = await self.client.fetch_user(user_id)
                conn = sqlite3.connect('discord_bot.db')
                c = conn.cursor()

                c.execute('SELECT first_count FROM users WHERE user_id = ?', (user_id,))
                result = c.fetchone()

                if result:
                    new_count = max(result[0] - count, 0)
                    c.execute('UPDATE users SET first_count = ? WHERE user_id = ?', (new_count, user_id))
                    await interaction.response.send_message(f"Contagem atualizada! Novo total para {user.name}: {new_count}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Usuário {user.name} não encontrado no banco de dados.", ephemeral=True)

                conn.commit()
                conn.close()
            except discord.NotFound:
                await interaction.response.send_message("ID de usuário inválido.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Ocorreu um erro: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)

    @app_commands.command(name="top10first", description="Mostra o top 10 pessoas que já foram first (geral ou mensal).")
    @app_commands.describe(mensal="Deseja ver o placar mensal? (Padrão: Não)")
    async def top10first(self, interaction: discord.Interaction, mensal: bool = False):
        if interaction.guild_id == int(MENES_SUECOS):
            if mensal:
                view = MonthlyLeaderboardView(user_id=interaction.user.id, timeout=60)
                initial_content = view.format_leaderboard_message(view.current_date.year, view.current_date.month)
                
                await interaction.response.send_message(initial_content, view=view)
                message = await interaction.original_response()
                view.message = message
            else:
                view = SimpleView(user_id=interaction.user.id, timeout=60)
                mn, mx = 0, 10
                response = get_top_users_from_db(mn, mx)
                formatted_response = "\n".join([f"{index + 1}. {username}: {count}" for index, (username, count) in enumerate(response)])

                await interaction.response.send_message(f"# HALL DA FAMA\n**Top 10 usuários com mais first:**\n{formatted_response}", view=view)
                message = await interaction.original_response()
                view.message = message
                view.mn = mn
                view.mx = mx
        else:
            await interaction.response.send_message("Este comando só pode ser usado no servidor Menes Suecos.", ephemeral=True)

    @app_commands.command(name="buscafirsts", description="Busca a quantidade de firsts de um usuário pelo nome ou apelido.")
    async def buscafirsts(self, interaction: discord.Interaction, username: str):
        if interaction.guild_id == int(MENES_SUECOS):
            guild = interaction.guild
            member = discord.utils.find(lambda m: m.display_name.lower() == username.lower() or m.name.lower() == username.lower(), guild.members)
            
            if member:
                conn = sqlite3.connect('discord_bot.db')
                c = conn.cursor()
                
                c.execute('SELECT username, first_count FROM users WHERE user_id = ?', (str(member.id),))
                result = c.fetchone()
                
                if result:
                    found_username, first_count = result
                    await interaction.response.send_message(f"Usuário: {found_username}\nQuantidade de 'firsts': {first_count}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Usuário {username} não encontrado no banco de dados.", ephemeral=True)
                
                conn.close()
            else:
                await interaction.response.send_message(f"Usuário {username} não encontrado no servidor.", ephemeral=True)
        else:
            await interaction.response.send_message("Server não permitido", ephemeral=True)

async def setup(client):
    await client.add_cog(FirstAdminCog(client))
