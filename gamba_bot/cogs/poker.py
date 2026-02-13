import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.cogs.common import EconomyCog
from gamba_bot.services.games import poker


class PokerCog(EconomyCog):
    @app_commands.command(name="poker", description="Draw against the house.")
    @app_commands.describe(stake="Credits to bet")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def poker_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[int, 1, 1_000_000],
    ) -> None:
        await self.play(
            interaction,
            stake=stake,
            title="Poker",
            game_fn=lambda: poker(stake),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PokerCog(bot))
