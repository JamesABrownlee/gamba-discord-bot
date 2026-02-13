import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.cogs.common import EconomyCog
from gamba_bot.services.games import minesweeper


class MinesweeperCog(EconomyCog):
    @app_commands.command(name="minesweeper", description="Pick a tile, avoid the mine.")
    @app_commands.describe(stake="Credits to bet", tile="Tile number (1-6)")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def minesweeper_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[int, 1, 1_000_000],
        tile: app_commands.Range[int, 1, 6],
    ) -> None:
        await self.play(
            interaction,
            stake=stake,
            title="Minesweeper",
            game_fn=lambda: minesweeper(stake, tile),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MinesweeperCog(bot))
