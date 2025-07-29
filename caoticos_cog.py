import discord
from discord.ext import commands
from discord import app_commands
import os
import re
import asyncio
import random
from python_pt_dictionary import dictionary

MENES_SUECOS = os.getenv('MENES_SUECOS')
LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID')
MUTE_ROLE_ID = os.getenv('MUTE_ROLE_ID')

class CaoticosCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    def parse_duration(self, duration: str) -> int:
        match = re.match(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', duration)
        if not match:
            return 0
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = int(match.group(3)) if match.group(3) else 0
        return hours * 3600 + minutes * 60 + seconds

    def format_duration(self, seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_parts = []
        if hours > 0:
            duration_parts.append(f"{hours} horas")
        if minutes > 0:
            duration_parts.append(f"{minutes} minutos")
        if seconds > 0:
            duration_parts.append(f"{seconds} segundos")
        return ", ".join(duration_parts) if duration_parts else "0 segundos"

    @app_commands.command(name="enviarmsg", description="[ADM] Faz o Yung Bot enviar uma mensagem no chat")
    async def enviarmsg(self, interaction: discord.Interaction, mensagemescrita: str):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            print(f"Comando enviarmsg utilizado")
            await interaction.response.send_message("Mensagem enviada", ephemeral=True)
            await interaction.channel.send(mensagemescrita)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name="respondermsg", description="[ADM] Faz o Yung Bot responder uma mensagem específica")
    async def respondermsg(self, interaction: discord.Interaction, mensagem_id: str, resposta: str):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            try:
                mensagem = await interaction.channel.fetch_message(int(mensagem_id))
                await interaction.response.send_message("Resposta enviada", ephemeral=True)
                await mensagem.reply(resposta)
                print(f"Comando respondermsg utilizado para a mensagem {mensagem_id}")
            except ValueError:
                await interaction.response.send_message("ID da mensagem deve ser um número inteiro válido", ephemeral=True)
            except discord.NotFound:
                await interaction.response.send_message("Mensagem não encontrada", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("Permissões insuficientes para responder a esta mensagem", ephemeral=True)
            except discord.HTTPException as e:
                await interaction.response.send_message(f"Ocorreu um erro ao tentar responder a mensagem: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name="mutar", description="[ADM] Muta um membro por um tempo específico")
    async def mutar(self, interaction: discord.Interaction, membro: discord.Member, duracao: str, motivo: str):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            mute_role = discord.utils.get(interaction.guild.roles, id=int(MUTE_ROLE_ID))
            if mute_role:
                duracao_segundos = self.parse_duration(duracao)
                if duracao_segundos == 0:
                    await interaction.response.send_message("Duração inválida. Use o formato '1h30m20s'.", ephemeral=True)
                    return

                await membro.add_roles(mute_role)
                duracao_formatada = self.format_duration(duracao_segundos)
                print(f"{membro} foi mutado por {duracao_formatada}. Motivo: {motivo}")
                
                log_channel = self.client.get_channel(int(LOG_CHANNEL_ID))
                if log_channel:
                    await log_channel.send(f"{membro.mention} foi mutado por {duracao_formatada}. Motivo: {motivo}")
                
                await interaction.response.send_message(f"{membro.mention} foi mutado por {duracao_formatada}. Motivo: {motivo}", ephemeral=True)
                
                await asyncio.sleep(duracao_segundos)
                
                # Re-fetch member object to ensure it's up to date
                member_after_wait = interaction.guild.get_member(membro.id)
                if member_after_wait and mute_role in member_after_wait.roles:
                    await member_after_wait.remove_roles(mute_role)
                    print(f"{membro.display_name} foi desmutado após {duracao_formatada}.")
                    if log_channel:
                        await log_channel.send(f"{membro.mention} foi desmutado após {duracao_formatada}.")
            else:
                await interaction.response.send_message("Cargo de mute não encontrado.", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name="desmutar", description="[ADM] Desmuta um membro")
    async def desmutar(self, interaction: discord.Interaction, membro: discord.Member):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            mute_role = discord.utils.get(interaction.guild.roles, id=int(MUTE_ROLE_ID))
            if mute_role and mute_role in membro.roles:
                await membro.remove_roles(mute_role)
                print(f"{membro.display_name} foi desmutado.")
                
                log_channel = self.client.get_channel(int(LOG_CHANNEL_ID))
                if log_channel:
                    await log_channel.send(f"{membro.mention} foi desmutado.")
                
                await interaction.response.send_message(f"{membro.mention} foi desmutado.", ephemeral=True)
            elif not mute_role:
                 await interaction.response.send_message("Cargo de mute não encontrado.", ephemeral=True)
            else:
                await interaction.response.send_message(f"{membro.mention} não está mutado.", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name="mensagemdivina", description="[ADM] Mensagem dos deuses inspirada no TempleOS")
    async def mensagemdivina(self, interaction: discord.Interaction, numeropalavras: int):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            fraseAleatoria = ""
            a = random.randint(0, 10000)
            for i in range(numeropalavras):
                a += 1
                random.seed(a)
                novaPalavra = None
                newWord = None
                while newWord is None or not newWord:
                    novaPalavra = ''.join(random.choices(self.client.alfabeto, k=5))
                    for _ in range(4):
                        novaPalavra = novaPalavra.replace(random.choice(self.client.alfabeto), "", 1)
                    if novaPalavra:
                        newWord = dictionary.select(novaPalavra, dictionary.Selector.PREFIX)
                indexAleatorio = random.randrange(len(newWord))
                fraseAleatoria = fraseAleatoria + " " + str.lower(newWord[indexAleatorio].text)
            print(f"Comando mensagemdivina utilizado")
            await interaction.response.send_message(f"{fraseAleatoria.strip()}", ephemeral=False)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

async def setup(client):
    await client.add_cog(CaoticosCog(client))
