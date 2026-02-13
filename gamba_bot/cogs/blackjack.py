import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.database import InsufficientBalanceError
from gamba_bot.services.games import (
    BlackjackRound,
    create_blackjack_round,
    dealer_must_hit,
    hand_total,
    is_blackjack,
)

BLACKJACK_WIN_MULTIPLIER = 1.5


def _cards_text(cards: list[str]) -> str:
    return " ".join(cards)


def _blackjack_embed(
    round_state: BlackjackRound,
    *,
    stake: int,
    footer: str,
    reveal_dealer: bool,
) -> discord.Embed:
    player_total = hand_total(round_state.player_hand)
    if reveal_dealer:
        dealer_cards = _cards_text(round_state.dealer_hand)
        dealer_total = hand_total(round_state.dealer_hand)
        dealer_line = f"{dealer_cards} ({dealer_total})"
    else:
        dealer_line = f"{round_state.dealer_hand[0]} ??"
    embed = discord.Embed(title="Blackjack", color=discord.Color.gold())
    embed.add_field(
        name=f"Player ({player_total})",
        value=_cards_text(round_state.player_hand),
        inline=False,
    )
    embed.add_field(name="Dealer", value=dealer_line, inline=False)
    embed.add_field(name="Stake", value=f"`{stake}` credits", inline=True)
    embed.add_field(name="Deck Remaining", value=str(len(round_state.deck)), inline=True)
    embed.set_footer(text=footer)
    return embed


class BlackjackView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        *,
        origin_interaction: discord.Interaction,
        stake: int,
        round_state: BlackjackRound,
    ) -> None:
        super().__init__(timeout=90)
        self.bot = bot
        self.origin_interaction = origin_interaction
        self.user_id = origin_interaction.user.id
        self.stake = stake
        self.round_state = round_state
        self.finished = False
        self._finalize_lock = asyncio.Lock()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This blackjack hand is not yours.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        if self.finished:
            return
        await self._finalize_round(
            interaction=None,
            delta=-self.stake,
            summary="Hand timed out. Stake lost.",
            reveal_dealer=True,
        )

    async def _finalize_round(
        self,
        *,
        interaction: discord.Interaction | None,
        delta: int,
        summary: str,
        reveal_dealer: bool,
    ) -> None:
        async with self._finalize_lock:
            if self.finished:
                return
            self.finished = True
            self.disable_all_items()
            try:
                record = await self.bot.db.settle_bet(
                    self.origin_interaction.user,
                    stake=self.stake,
                    delta=delta,
                )
            except InsufficientBalanceError:
                error_embed = _blackjack_embed(
                    self.round_state,
                    stake=self.stake,
                    footer="Could not settle hand due to insufficient balance.",
                    reveal_dealer=True,
                )
                target = interaction or self.origin_interaction
                await target.edit_original_response(embed=error_embed, view=self)
                return

            footer = f"{summary} New balance: {record.balance}"
            final_embed = _blackjack_embed(
                self.round_state,
                stake=self.stake,
                footer=footer,
                reveal_dealer=reveal_dealer,
            )
            target = interaction or self.origin_interaction
            if interaction is not None and not interaction.response.is_done():
                await interaction.response.edit_message(embed=final_embed, view=self)
            else:
                await target.edit_original_response(embed=final_embed, view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        card = self.round_state.player_hit()
        player_total = hand_total(self.round_state.player_hand)
        if player_total > 21:
            await self._finalize_round(
                interaction=interaction,
                delta=-self.stake,
                summary=f"You drew {card} and busted with {player_total}.",
                reveal_dealer=True,
            )
            return

        embed = _blackjack_embed(
            self.round_state,
            stake=self.stake,
            footer=f"You drew {card}. Hit or Stick.",
            reveal_dealer=False,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stick", style=discord.ButtonStyle.secondary)
    async def stick(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        while dealer_must_hit(self.round_state.dealer_hand):
            self.round_state.dealer_hit()

        player_total = hand_total(self.round_state.player_hand)
        dealer_total = hand_total(self.round_state.dealer_hand)

        if dealer_total > 21:
            delta = int(self.stake * BLACKJACK_WIN_MULTIPLIER)
            summary = f"Dealer busted with {dealer_total}. You win."
        elif player_total > dealer_total:
            delta = int(self.stake * BLACKJACK_WIN_MULTIPLIER)
            summary = f"You win {player_total} to {dealer_total}."
        elif player_total < dealer_total:
            delta = -self.stake
            summary = f"Dealer wins {dealer_total} to {player_total}."
        else:
            delta = 0
            summary = f"Push at {player_total}."
        await self._finalize_round(
            interaction=interaction,
            delta=delta,
            summary=summary,
            reveal_dealer=True,
        )


class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="Play a quick blackjack hand.")
    @app_commands.describe(stake="Credits to bet")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def blackjack_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[int, 1, 1_000_000],
    ) -> None:
        user_record = await self.bot.db.ensure_user(interaction.user)
        if user_record.balance < stake:
            await self.bot.responses.send_or_followup(
                interaction,
                content="Insufficient balance for that stake.",
            )
            return

        round_state = create_blackjack_round()
        if is_blackjack(round_state.dealer_hand):
            record = await self.bot.db.settle_bet(interaction.user, stake=stake, delta=-stake)
            embed = _blackjack_embed(
                round_state,
                stake=stake,
                footer=f"Dealer has blackjack. You lose. New balance: {record.balance}",
                reveal_dealer=True,
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=interaction.guild is not None,
            )
            return

        if is_blackjack(round_state.player_hand):
            delta = int(stake * BLACKJACK_WIN_MULTIPLIER)
            record = await self.bot.db.settle_bet(interaction.user, stake=stake, delta=delta)
            embed = _blackjack_embed(
                round_state,
                stake=stake,
                footer=f"Blackjack. You win {delta} credits. New balance: {record.balance}",
                reveal_dealer=True,
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=interaction.guild is not None,
            )
            return

        view = BlackjackView(
            self.bot,
            origin_interaction=interaction,
            stake=stake,
            round_state=round_state,
        )
        embed = _blackjack_embed(
            round_state,
            stake=stake,
            footer="Hit to draw, Stick to stand.",
            reveal_dealer=False,
        )
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=interaction.guild is not None,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BlackjackCog(bot))
