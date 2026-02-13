from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.cogs.common import EconomyCog
from gamba_bot.services.games import roulette
from gamba_bot.utils.currency import parse_credits_to_cents


class RouletteCog(EconomyCog):
    @app_commands.command(name="roulette", description="Bet on red, black, or green.")
    @app_commands.describe(stake="Credits to bet", pick="Color to bet on")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def roulette_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[float, 0.01, 50_000_000.0],
        pick: Literal["red", "black", "green"],
    ) -> None:
        stake_cents = parse_credits_to_cents(stake)
        await self.play(
            interaction,
            stake=stake_cents,
            title="Roulette",
            game_fn=lambda: roulette(stake_cents, pick),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RouletteCog(bot))
