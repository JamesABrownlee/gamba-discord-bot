import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.database import InsufficientBalanceError
from gamba_bot.services.games import create_blackjack_round, dealer_must_hit, hand_total, is_blackjack
from gamba_bot.utils.currency import format_cents

BLACKJACK_WIN_MULTIPLIER = 1.5

# Values are in cent-units so the selector can offer 0.01 style low stakes.
STAKE_TIERS = {
    "low": {
        "label": "Low Stakes",
        "description": "0.01 to 10.00",
        "values": [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000],
    },
    "medium": {
        "label": "Medium Stakes",
        "description": "50 to 500",
        "values": [5000, 7500, 10000, 20000, 30000, 50000],
    },
    "high": {
        "label": "High Stakes",
        "description": "1,000 to 100,000",
        "values": [100000, 250000, 500000, 1000000, 2500000, 5000000, 10000000],
    },
    "high_roller": {
        "label": "High Roller",
        "description": "500,000 to 50,000,000",
        "values": [50000000, 100000000, 250000000, 500000000, 1000000000, 2500000000, 5000000000],
    },
}

TIER_ORDER = ("low", "medium", "high", "high_roller")


def _fmt_units(value: int | float) -> str:
    return format_cents(int(value))


def _cards_text(cards: list[str]) -> str:
    return " ".join(cards)


class StakeSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(placeholder="Select stake", min_values=1, max_values=1, options=[], row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: BlackjackSessionView = self.view  # type: ignore[assignment]
        await view.select_stake(interaction, int(self.values[0]))


class TierButton(discord.ui.Button):
    def __init__(self, tier_key: str, *, row: int) -> None:
        cfg = STAKE_TIERS[tier_key]
        super().__init__(label=cfg["label"], style=discord.ButtonStyle.secondary, row=row)
        self.tier_key = tier_key

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: BlackjackSessionView = self.view  # type: ignore[assignment]
        await view.select_tier(interaction, self.tier_key)


class DealButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Deal Hand", style=discord.ButtonStyle.success, row=2)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: BlackjackSessionView = self.view  # type: ignore[assignment]
        await view.deal_hand(interaction)


class HitButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Hit", style=discord.ButtonStyle.primary, row=2)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: BlackjackSessionView = self.view  # type: ignore[assignment]
        await view.hit(interaction)


class StickButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Stick", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: BlackjackSessionView = self.view  # type: ignore[assignment]
        await view.stick(interaction)


class NewHandYesButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="New Hand: Yes", style=discord.ButtonStyle.success, row=3)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: BlackjackSessionView = self.view  # type: ignore[assignment]
        await view.new_hand_yes(interaction)


class NewHandNoButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="New Hand: No", style=discord.ButtonStyle.danger, row=3)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: BlackjackSessionView = self.view  # type: ignore[assignment]
        await view.new_hand_no(interaction)


class BlackjackSessionView(discord.ui.View):
    def __init__(self, bot: commands.Bot, *, origin_interaction: discord.Interaction, balance: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.origin_interaction = origin_interaction
        self.user_id = origin_interaction.user.id
        self.balance = balance
        self.selected_tier = "low"
        self.selected_stake = STAKE_TIERS["low"]["values"][0]
        self.round_state = None
        self.status = "Choose a stake range and stake amount."
        self.awaiting_new_hand = False
        self.finished = False
        self.idle_timeout_seconds = 60.0
        self.last_action = time.monotonic()
        self._lock = asyncio.Lock()

        self.stake_select = StakeSelect()
        self.tier_buttons = {tier: TierButton(tier, row=1) for tier in TIER_ORDER}
        self.deal_button = DealButton()
        self.hit_button = HitButton()
        self.stick_button = StickButton()
        self.new_yes_button = NewHandYesButton()
        self.new_no_button = NewHandNoButton()

        self.add_item(self.stake_select)
        for tier in TIER_ORDER:
            self.add_item(self.tier_buttons[tier])
        self.add_item(self.deal_button)
        self.add_item(self.hit_button)
        self.add_item(self.stick_button)
        self.add_item(self.new_yes_button)
        self.add_item(self.new_no_button)

        self._rebuild_controls()
        self._watchdog_task = asyncio.create_task(self._idle_watchdog())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This blackjack session is not yours.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        return

    async def _idle_watchdog(self) -> None:
        while not self.finished:
            await asyncio.sleep(2)
            if time.monotonic() - self.last_action >= self.idle_timeout_seconds:
                self.finished = True
                self._disable_all()
                self.status = "No action for 60 seconds. Session ended."
                try:
                    await self.origin_interaction.edit_original_response(embed=self._build_embed(), view=self)
                except discord.HTTPException:
                    pass
                self.stop()
                return

    def _disable_all(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button) or isinstance(child, discord.ui.Select):
                child.disabled = True

    def _affordable_values(self, tier: str) -> list[int]:
        return [v for v in STAKE_TIERS[tier]["values"] if v <= self.balance]

    def _best_affordable_tier(self) -> str | None:
        available = [tier for tier in TIER_ORDER if self._affordable_values(tier)]
        if not available:
            return None
        return available[-1]

    def _normalize_selected_stake(self) -> None:
        tier_values = self._affordable_values(self.selected_tier)
        if tier_values:
            if self.selected_stake not in tier_values:
                self.selected_stake = tier_values[-1]
            return

        fallback_tier = self._best_affordable_tier()
        if fallback_tier is None:
            self.selected_stake = 0
            return
        self.selected_tier = fallback_tier
        self.selected_stake = self._affordable_values(fallback_tier)[-1]

    def _rebuild_select(self) -> None:
        options = []
        for value in STAKE_TIERS[self.selected_tier]["values"]:
            options.append(
                discord.SelectOption(
                    label=_fmt_units(value),
                    value=str(value),
                    default=(value == self.selected_stake),
                    description="Affordable" if value <= self.balance else "Insufficient balance",
                )
            )
        self.stake_select.options = options[:25]
        self.stake_select.disabled = not bool(self._affordable_values(self.selected_tier))

    def _rebuild_controls(self) -> None:
        self._normalize_selected_stake()
        self._rebuild_select()

        for tier, btn in self.tier_buttons.items():
            enabled = bool(self._affordable_values(tier))
            btn.disabled = not enabled
            btn.style = discord.ButtonStyle.primary if tier == self.selected_tier else discord.ButtonStyle.secondary

        playing = self.round_state is not None and not self.awaiting_new_hand and not self.finished
        lobby = self.round_state is None and not self.awaiting_new_hand and not self.finished
        post_round = self.awaiting_new_hand and not self.finished

        self.deal_button.disabled = not lobby or self.selected_stake <= 0
        self.hit_button.disabled = not playing
        self.stick_button.disabled = not playing
        self.new_yes_button.disabled = not post_round
        self.new_no_button.disabled = not post_round

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Blackjack", color=discord.Color.gold())
        embed.add_field(
            name="Stake Tiers",
            value=(
                "Low Stakes: 0.01 to 10.00\n"
                "Medium Stakes: 50 to 500\n"
                "High Stakes: 1,000 to 100,000\n"
                "High Roller: 500,000 to 50,000,000"
            ),
            inline=False,
        )
        embed.add_field(name="Balance", value=f"`{_fmt_units(self.balance)}`", inline=True)
        if self.selected_stake > 0:
            embed.add_field(name="Selected Stake", value=f"`{_fmt_units(self.selected_stake)}`", inline=True)
        else:
            embed.add_field(name="Selected Stake", value="`Unavailable`", inline=True)
        embed.add_field(name="Decks", value="8-deck shoe", inline=True)

        if self.round_state is not None:
            player_total = hand_total(self.round_state.player_hand)
            if self.awaiting_new_hand:
                dealer_cards = _cards_text(self.round_state.dealer_hand)
                dealer_total = hand_total(self.round_state.dealer_hand)
                dealer_line = f"{dealer_cards} ({dealer_total})"
            else:
                dealer_line = f"{self.round_state.dealer_hand[0]} ??"

            embed.add_field(
                name=f"Player ({player_total})",
                value=_cards_text(self.round_state.player_hand),
                inline=False,
            )
            embed.add_field(name="Dealer", value=dealer_line, inline=False)
            embed.add_field(name="Cards Remaining", value=str(len(self.round_state.deck)), inline=True)

        embed.set_footer(text=self.status)
        return embed

    async def _safe_edit(self, interaction: discord.Interaction | None) -> None:
        embed = self._build_embed()
        if interaction is not None and not interaction.response.is_done():
            try:
                await interaction.response.edit_message(embed=embed, view=self)
                return
            except discord.NotFound:
                pass
        await self.origin_interaction.edit_original_response(embed=embed, view=self)

    async def select_tier(self, interaction: discord.Interaction, tier_key: str) -> None:
        self.last_action = time.monotonic()
        if self.round_state is not None and not self.awaiting_new_hand:
            await interaction.response.send_message("Finish the current hand first.", ephemeral=True)
            return
        if not self._affordable_values(tier_key):
            await interaction.response.send_message("Insufficient balance for that tier.", ephemeral=True)
            return
        self.selected_tier = tier_key
        self._normalize_selected_stake()
        self.status = f"Tier set to {STAKE_TIERS[tier_key]['label']}."
        self._rebuild_controls()
        await self._safe_edit(interaction)

    async def select_stake(self, interaction: discord.Interaction, stake: int) -> None:
        self.last_action = time.monotonic()
        if self.round_state is not None and not self.awaiting_new_hand:
            await interaction.response.send_message("Finish the current hand first.", ephemeral=True)
            return
        if stake > self.balance:
            await interaction.response.send_message("You cannot afford that stake.", ephemeral=True)
            return
        self.selected_stake = stake
        self.status = f"Stake set to {_fmt_units(stake)}."
        self._rebuild_controls()
        await self._safe_edit(interaction)

    async def _settle_and_finish_hand(self, interaction: discord.Interaction | None, *, delta: int, summary: str) -> None:
        try:
            record = await self.bot.db.settle_bet(
                self.origin_interaction.user,
                stake=self.selected_stake,
                delta=delta,
            )
        except InsufficientBalanceError:
            self.status = "Insufficient balance to settle hand."
            self.awaiting_new_hand = True
            self.round_state = None
            self._rebuild_controls()
            await self._safe_edit(interaction)
            return

        self.balance = int(record.balance)
        self.awaiting_new_hand = True
        if delta > 0:
            change = f"+{_fmt_units(delta)}"
        elif delta < 0:
            change = f"-{_fmt_units(abs(delta))}"
        else:
            change = "0.00"
        self.status = f"{summary} Hand result: {change}. Balance: {_fmt_units(self.balance)}. New hand?"
        self._rebuild_controls()
        await self._safe_edit(interaction)

    async def deal_hand(self, interaction: discord.Interaction) -> None:
        self.last_action = time.monotonic()
        if self.selected_stake <= 0:
            await interaction.response.send_message("No available stake for your balance.", ephemeral=True)
            return
        if self.balance < self.selected_stake:
            self._normalize_selected_stake()
            self.status = "Stake adjusted to your available balance."
            self._rebuild_controls()
            await self._safe_edit(interaction)
            return

        self.awaiting_new_hand = False
        self.round_state = create_blackjack_round(8)

        if is_blackjack(self.round_state.dealer_hand):
            await interaction.response.defer()
            await self._settle_and_finish_hand(
                interaction,
                delta=-self.selected_stake,
                summary="Dealer has blackjack.",
            )
            return

        if is_blackjack(self.round_state.player_hand):
            await interaction.response.defer()
            delta = int(self.selected_stake * BLACKJACK_WIN_MULTIPLIER)
            await self._settle_and_finish_hand(
                interaction,
                delta=delta,
                summary="Blackjack.",
            )
            return

        self.status = "Hand dealt. Choose Hit or Stick."
        self._rebuild_controls()
        await self._safe_edit(interaction)

    async def hit(self, interaction: discord.Interaction) -> None:
        self.last_action = time.monotonic()
        if self.round_state is None:
            await interaction.response.send_message("Deal a hand first.", ephemeral=True)
            return
        card = self.round_state.player_hit()
        player_total = hand_total(self.round_state.player_hand)
        if player_total > 21:
            await interaction.response.defer()
            await self._settle_and_finish_hand(
                interaction,
                delta=-self.selected_stake,
                summary=f"You drew {card} and busted at {player_total}.",
            )
            return

        self.status = f"You drew {card}. Choose Hit or Stick."
        self._rebuild_controls()
        await self._safe_edit(interaction)

    async def stick(self, interaction: discord.Interaction) -> None:
        self.last_action = time.monotonic()
        if self.round_state is None:
            await interaction.response.send_message("Deal a hand first.", ephemeral=True)
            return

        await interaction.response.defer()
        while dealer_must_hit(self.round_state.dealer_hand):
            self.round_state.dealer_hit()

        player_total = hand_total(self.round_state.player_hand)
        dealer_total = hand_total(self.round_state.dealer_hand)

        if dealer_total > 21:
            delta = int(self.selected_stake * BLACKJACK_WIN_MULTIPLIER)
            summary = f"Dealer busted at {dealer_total}."
        elif player_total > dealer_total:
            delta = int(self.selected_stake * BLACKJACK_WIN_MULTIPLIER)
            summary = f"You win {player_total} to {dealer_total}."
        elif player_total < dealer_total:
            delta = -self.selected_stake
            summary = f"Dealer wins {dealer_total} to {player_total}."
        else:
            delta = 0
            summary = f"Push at {player_total}."

        await self._settle_and_finish_hand(interaction, delta=delta, summary=summary)

    async def new_hand_yes(self, interaction: discord.Interaction) -> None:
        self.last_action = time.monotonic()
        self.awaiting_new_hand = False
        self.round_state = None
        if self.selected_stake > self.balance:
            self._normalize_selected_stake()
            self.status = "Stake adjusted down to the highest affordable value."
        else:
            self.status = "Ready for next hand."
        self._rebuild_controls()
        await self._safe_edit(interaction)

    async def new_hand_no(self, interaction: discord.Interaction) -> None:
        self.last_action = time.monotonic()
        self.finished = True
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        self._disable_all()
        self.status = "Session closed."
        await self._safe_edit(interaction)
        self.stop()


class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="Play blackjack with stake tiers and hand controls.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def blackjack_cmd(self, interaction: discord.Interaction) -> None:
        await self.bot.responses.defer(interaction)
        record = await self.bot.db.ensure_user(interaction.user)
        view = BlackjackSessionView(self.bot, origin_interaction=interaction, balance=int(record.balance))
        await interaction.edit_original_response(content=None, embed=view._build_embed(), view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BlackjackCog(bot))
