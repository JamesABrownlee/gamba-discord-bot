import asyncio
import logging

import discord
from discord.ext import commands

from gamba_bot.config import Settings
from gamba_bot.database import Database
from gamba_bot.utils.respond import ResponseCoordinator


COGS = (
    "gamba_bot.cogs.core",
    "gamba_bot.cogs.roulette",
    "gamba_bot.cogs.slots",
    "gamba_bot.cogs.blackjack",
    "gamba_bot.cogs.poker",
    "gamba_bot.cogs.minesweeper",
    "gamba_bot.cogs.wordlinks",
)


class GambaBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.db = Database(settings.database_path, settings.starting_balance)
        self.responses = ResponseCoordinator(min_gap_seconds=0.4)

    async def setup_hook(self) -> None:
        await self.db.initialize()
        for cog in COGS:
            await self.load_extension(cog)
        await self.tree.sync()
        logging.info("Slash commands synced.")

    async def close(self) -> None:
        await self.db.close()
        await super().close()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    bot = GambaBot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
