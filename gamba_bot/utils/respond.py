import asyncio
import time
from collections import defaultdict

import discord


def in_guild(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None


class ResponseCoordinator:
    def __init__(self, min_gap_seconds: float = 0.4):
        self.min_gap_seconds = min_gap_seconds
        self._last_send = defaultdict(float)
        self._locks = defaultdict(asyncio.Lock)

    async def defer(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=in_guild(interaction), thinking=True)

    async def send_or_followup(
        self,
        interaction: discord.Interaction,
        *,
        content: str,
    ) -> None:
        async with self._locks[interaction.user.id]:
            now = time.monotonic()
            elapsed = now - self._last_send[interaction.user.id]
            wait_for = max(0.0, self.min_gap_seconds - elapsed)
            if wait_for:
                await asyncio.sleep(wait_for)

            ephemeral = in_guild(interaction)
            if interaction.response.is_done():
                await interaction.followup.send(content, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(content, ephemeral=ephemeral)
            self._last_send[interaction.user.id] = time.monotonic()

    async def edit_original(self, interaction: discord.Interaction, *, content: str) -> None:
        async with self._locks[interaction.user.id]:
            now = time.monotonic()
            elapsed = now - self._last_send[interaction.user.id]
            wait_for = max(0.0, self.min_gap_seconds - elapsed)
            if wait_for:
                await asyncio.sleep(wait_for)

            await interaction.edit_original_response(content=content)
            self._last_send[interaction.user.id] = time.monotonic()
