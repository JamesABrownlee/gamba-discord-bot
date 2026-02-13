import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.cogs.common import EconomyCog
from gamba_bot.services.games import blackjack


class BlackjackCog(EconomyCog):
    @app_commands.command(name="blackjack", description="Play a quick blackjack hand.")
    @app_commands.describe(stake="Credits to bet")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def blackjack_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[int, 1, 1_000_000],
    ) -> None:
        await self.play(
            interaction,
            stake=stake,
            title="Blackjack",
            game_fn=lambda: blackjack(stake),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BlackjackCog(bot))
