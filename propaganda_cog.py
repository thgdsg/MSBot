import discord
from discord.ext import commands
from discord import app_commands
import os
import random

MENES_SUECOS = os.getenv('MENES_SUECOS')

class PropagandaCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def sendAd(self, interaction, bloqueiachat, escolha=None):
        """Envia uma propaganda no chat, com opção de bloquear."""
        propaganda_selecionada = None
        if escolha is not None:
            propaganda_selecionada = next((p for p in self.client.opcoes_propaganda if p.get('numero') == escolha), None)

        if propaganda_selecionada is None:
            propaganda_selecionada = random.choice(self.client.opcoes_propaganda)

        random_message = propaganda_selecionada["texto"]
        random_file_path = propaganda_selecionada.get("imagem")

        # Limpa o estado de bloqueio anterior, se houver
        if self.client.mensagem_block:
            try:
                await self.client.mensagem_block.channel.set_permissions(self.client.mensagem_block.guild.default_role, overwrite=self.client.permissoesOriginais)
                await self.client.mensagem_block.delete()
            except (discord.NotFound, discord.Forbidden) as e:
                print(f"Não foi possível limpar o bloqueio anterior: {e}")
            finally:
                self.client.mensagem_block = None
                self.client.permissoesOriginais = None

        # Envia a nova propaganda
        sent_message = await interaction.channel.send(f"{random_message}", file=discord.File(random_file_path) if random_file_path else None)
        
        if bloqueiachat:
            self.client.propaganda = 0
            print(f"Propaganda enviada, bloqueando chat")
            self.client.mensagem_block = sent_message
            self.client.permissoesOriginais = interaction.channel.overwrites_for(interaction.guild.default_role)
            await sent_message.add_reaction("✅")
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
            await interaction.response.send_message("Propaganda enviada e chat bloqueado.", ephemeral=True)
        else:
            await interaction.response.send_message("Propaganda enviada.", ephemeral=True)

    @app_commands.command(name="mudaconfigpropaganda", description="[ADM] Muda configurações da propaganda")
    async def mudaconfigpropaganda(self, interaction: discord.Interaction, numeromsgslidas: int, numeroreacoes: int):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            self.client.propaganda_max = numeromsgslidas
            self.client.reaction_max = numeroreacoes
            await interaction.response.send_message(f"Configurações de propaganda alteradas para {self.client.propaganda_max} mensagens lidas e {self.client.reaction_max} reações", ephemeral=True)
            print(f"Configurações de propaganda alteradas para {self.client.propaganda_max} mensagens lidas e {self.client.reaction_max} reações")
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name="enviapropaganda", description="[ADM] Envia uma propaganda no chat")
    async def enviapropaganda(self, interaction: discord.Interaction, bloqueiachat: bool, escolha: int = None):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            await self.sendAd(interaction, bloqueiachat, escolha)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name="desbloqueiachat", description="[ADM] Desbloqueia o chat e reseta propaganda")
    async def desbloqueiachat(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            if self.client.mensagem_block:
                try:
                    self.client.ignorar_omd = True
                    await self.client.mensagem_block.delete()
                except discord.NotFound:
                    print("Mensagem de bloqueio já havia sido deletada.")
                finally:
                    self.client.ignorar_omd = False

                if self.client.permissoesOriginais is not None:
                    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=self.client.permissoesOriginais)
                
                print("Chat desbloqueado pelo comando.")
                self.client.mensagem_block = None
                self.client.permissoesOriginais = None
                await interaction.response.send_message("Chat desbloqueado com sucesso", ephemeral=True)
            elif not interaction.channel.permissions_for(interaction.guild.default_role).send_messages:
                await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
                await interaction.response.send_message("Permissões do canal resetadas.", ephemeral=True)
            else:
                await interaction.response.send_message("O chat já está desbloqueado", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

    @app_commands.command(name="bloqueiachat", description="[ADM] Bloqueia o chat")
    async def bloqueiachat(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.moderate_members and interaction.guild_id == int(MENES_SUECOS):
            if interaction.channel.permissions_for(interaction.guild.default_role).send_messages:
                await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
                print("Chat bloqueado pelo comando.")
                await interaction.response.send_message("Chat bloqueado com sucesso", ephemeral=True)
            else:
                await interaction.response.send_message("O chat já está bloqueado", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissões suficientes", ephemeral=True)

async def setup(client):
    await client.add_cog(PropagandaCog(client))
