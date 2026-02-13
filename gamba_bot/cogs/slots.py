import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.cogs.common import EconomyCog
from gamba_bot.services.games import slots


class SlotsCog(EconomyCog):
    @app_commands.command(name="slots", description="Spin a 3-reel slot machine.")
    @app_commands.describe(stake="Credits to bet")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def slots_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[int, 1, 1_000_000],
    ) -> None:
        await self.play(
            interaction,
            stake=stake,
            title="Slots",
            game_fn=lambda: slots(stake),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SlotsCog(bot))
