from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.cogs.common import EconomyCog
from gamba_bot.services.games import roulette


class RouletteCog(EconomyCog):
    @app_commands.command(name="roulette", description="Bet on red, black, or green.")
    @app_commands.describe(stake="Credits to bet", pick="Color to bet on")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def roulette_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[int, 1, 1_000_000],
        pick: Literal["red", "black", "green"],
    ) -> None:
        await self.play(
            interaction,
            stake=stake,
            title="Roulette",
            game_fn=lambda: roulette(stake, pick),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RouletteCog(bot))
