import asyncio
from typing import Callable

import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.database import InsufficientBalanceError
from gamba_bot.services.games import GameResult


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def play(
        self,
        interaction: discord.Interaction,
        *,
        stake: int,
        title: str,
        game_fn: Callable[[], GameResult],
    ) -> None:
        if stake <= 0:
            raise app_commands.AppCommandError("Stake must be greater than zero.")

        await self.bot.db.ensure_user(interaction.user)
        await self.bot.responses.defer(interaction)
        await asyncio.sleep(0.45)
        result = game_fn()
        try:
            record = await self.bot.db.settle_bet(
                interaction.user,
                stake=stake,
                delta=result.delta,
            )
        except InsufficientBalanceError:
            await self.bot.responses.edit_original(
                interaction,
                content="Insufficient balance for that stake.",
            )
            return

        if result.won:
            outcome = f"won `{max(result.delta, 0)}` credits"
        elif result.delta == 0:
            outcome = "pushed and kept your credits"
        else:
            outcome = f"lost `{abs(result.delta)}` credits"
        msg = (
            f"**{title}**\n"
            f"{result.detail}\n"
            f"You {outcome}.\n"
            f"New balance: `{record.balance}`"
        )
        await self.bot.responses.edit_original(interaction, content=msg)
