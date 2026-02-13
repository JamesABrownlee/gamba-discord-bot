import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.cogs.common import EconomyCog
from gamba_bot.services.games import poker
from gamba_bot.utils.currency import parse_credits_to_cents


class PokerCog(EconomyCog):
    @app_commands.command(name="poker", description="Draw against the house.")
    @app_commands.describe(stake="Credits to bet")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def poker_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[float, 0.01, 50_000_000.0],
    ) -> None:
        stake_cents = parse_credits_to_cents(stake)
        await self.play(
            interaction,
            stake=stake_cents,
            title="Poker",
            game_fn=lambda: poker(stake_cents),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PokerCog(bot))
