from __future__ import annotations

import discord
from discord.ext import commands

from app.commands.registry import register_all_commands
from app.config import AppConfig
from app.context import AppContext
from app.events.lifecycle_events import register_all_events
from app.logging_config import configure_logging


class MSBot(commands.Bot):
    """Discord bootstrap: owns the client, tree and application context only."""

    def __init__(self, config: AppConfig | None = None):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.synced = False
        self.config = config or AppConfig.from_environment()
        self.context = AppContext.create(self, self.config)
        self._application_registered = False

    async def setup_hook(self) -> None:
        if not self._application_registered:
            register_all_commands(self.tree, self.context)
            register_all_events(self, self.context)
            self._application_registered = True

        try:
            if self.config.server_id:
                local_command_names = sorted(
                    command.name for command in self.tree.get_commands()
                )
                print(
                    "Comandos locais antes do sync: "
                    f"{', '.join(local_command_names)}"
                )

                guild = discord.Object(id=self.config.server_int)
                self.tree.clear_commands(guild=guild)
                self.tree.copy_global_to(guild=guild)
                guild_commands = await self.tree.sync(guild=guild)
                guild_command_names = sorted(command.name for command in guild_commands)

                # Commands are published to the configured server immediately.
                self.tree.clear_commands(guild=None)
                global_commands = await self.tree.sync()
                self.synced = True
                print(
                    "Arvore de comandos sincronizada no servidor "
                    f"{self.config.server_id} com {len(guild_commands)} comandos. "
                    f"Comandos globais: {len(global_commands)}. "
                    f"Comandos do servidor: {', '.join(guild_command_names)}"
                )
            elif not self.synced:
                synced_commands = await self.tree.sync()
                self.synced = True
                print(
                    "Arvore de comandos global sincronizada "
                    f"com {len(synced_commands)} comandos."
                )
        except Exception as error:
            print(f"Falha ao sincronizar a arvore de comandos: {error}")


client = MSBot()


def main() -> None:
    configure_logging(client.config.path("logs"))
    client.config.validate_runtime()
    client.run(client.config.token)


if __name__ == "__main__":
    main()
