import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.cogs.common import EconomyCog
from gamba_bot.services.games import wordlinks


class WordlinksCog(EconomyCog):
    @app_commands.command(name="wordlinks", description="Guess a hidden word length.")
    @app_commands.describe(stake="Credits to bet", guess="Your guess for the word length")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def wordlinks_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[int, 1, 1_000_000],
        guess: app_commands.Range[int, 1, 20],
    ) -> None:
        await self.play(
            interaction,
            stake=stake,
            title="Word Links",
            game_fn=lambda: wordlinks(stake, guess),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WordlinksCog(bot))
