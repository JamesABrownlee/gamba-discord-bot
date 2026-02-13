import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from gamba_bot.database import InsufficientBalanceError, UserRecord
from gamba_bot.services.games import (
    SLOT_EMOJI,
    SlotResult,
    evaluate_slots,
    slot_paytable_lines,
    spin_slot_reels,
)
from gamba_bot.utils.currency import format_cents, parse_credits_to_cents


class HoldButton(discord.ui.Button):
    def __init__(self, reel_index: int):
        super().__init__(label=f"Hold {reel_index + 1}: OFF", style=discord.ButtonStyle.secondary)
        self.reel_index = reel_index

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: SlotsView = self.view  # type: ignore[assignment]
        await view.toggle_hold(interaction, self.reel_index)


class SpinButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Spin", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: SlotsView = self.view  # type: ignore[assignment]
        await view.spin(interaction)


class WinningsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Winnings", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view: SlotsView = self.view  # type: ignore[assignment]
        await view.show_winnings(interaction)


class SlotsView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        *,
        origin_interaction: discord.Interaction,
        stake: int,
        user_record: UserRecord,
    ) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.origin_interaction = origin_interaction
        self.user_id = origin_interaction.user.id
        self.stake = stake
        self.balance = user_record.balance
        self.holds = [False, False, False]
        self.stops, self.symbols = spin_slot_reels(None, [False, False, False])
        self.last_result: SlotResult | None = None
        self._settle_lock = asyncio.Lock()

        self.spin_button = SpinButton()
        self.hold_buttons = [HoldButton(0), HoldButton(1), HoldButton(2)]
        self.winnings_button = WinningsButton()

        self.add_item(self.spin_button)
        for btn in self.hold_buttons:
            self.add_item(btn)
        self.add_item(self.winnings_button)
        self._sync_hold_buttons()

    def _sync_hold_buttons(self) -> None:
        for idx, btn in enumerate(self.hold_buttons):
            is_held = self.holds[idx]
            btn.label = f"Hold {idx + 1}: {'ON' if is_held else 'OFF'}"
            btn.style = discord.ButtonStyle.danger if is_held else discord.ButtonStyle.secondary

    def _disable_inputs(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    def _machine_line(self) -> str:
        return " | ".join(SLOT_EMOJI[symbol] for symbol in self.symbols)

    def build_embed(self, *, footer: str) -> discord.Embed:
        embed = discord.Embed(title="Slots", color=discord.Color.blurple())
        embed.add_field(name="Reels", value=self._machine_line(), inline=False)
        embed.add_field(
            name="Holds",
            value=(
                f"R1: {'ON' if self.holds[0] else 'OFF'} | "
                f"R2: {'ON' if self.holds[1] else 'OFF'} | "
                f"R3: {'ON' if self.holds[2] else 'OFF'}"
            ),
            inline=False,
        )
        embed.add_field(name="Stake / Spin", value=f"`{format_cents(self.stake)}` credits", inline=True)
        embed.add_field(name="Balance", value=f"`{format_cents(self.balance)}` credits", inline=True)
        if self.last_result:
            embed.add_field(
                name="Last Spin",
                value=f"{self.last_result.reason}\nNet: `{format_cents(self.last_result.net_delta)}`",
                inline=False,
            )
        embed.set_footer(text=footer)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This slots session is not yours.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        self._disable_inputs()
        timeout_embed = self.build_embed(footer="Session timed out.")
        try:
            await self.origin_interaction.edit_original_response(embed=timeout_embed, view=self)
        except discord.HTTPException:
            return

    async def toggle_hold(self, interaction: discord.Interaction, reel_index: int) -> None:
        self.holds[reel_index] = not self.holds[reel_index]
        self._sync_hold_buttons()
        embed = self.build_embed(footer="Select holds, then press Spin.")
        await interaction.response.edit_message(embed=embed, view=self)

    async def show_winnings(self, interaction: discord.Interaction) -> None:
        lines = "\n".join(slot_paytable_lines())
        content = f"**Payouts (multiplier x stake)**\n{lines}"
        await interaction.response.send_message(
            content,
            ephemeral=interaction.guild is not None,
        )

    async def spin(self, interaction: discord.Interaction) -> None:
        if all(self.holds):
            await interaction.response.send_message(
                "At least one reel must be unheld before spinning.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        async with self._settle_lock:
            await asyncio.sleep(0.3)
            self.stops, self.symbols = spin_slot_reels(self.stops, self.holds)
            result = evaluate_slots(self.symbols, self.stake)
            self.last_result = result
            try:
                record = await self.bot.db.settle_bet(
                    self.origin_interaction.user,
                    stake=self.stake,
                    delta=result.net_delta,
                )
            except InsufficientBalanceError:
                self._disable_inputs()
                embed = self.build_embed(footer="Insufficient balance for another spin.")
                await interaction.edit_original_response(embed=embed, view=self)
                return

            self.balance = record.balance
            if result.net_delta > 0:
                footer = f"You won {format_cents(result.gross_win)} (net +{format_cents(result.net_delta)})."
            elif result.net_delta == 0:
                footer = "Break-even spin."
            else:
                footer = f"No payout. Lost {format_cents(abs(result.net_delta))}."
            embed = self.build_embed(footer=footer)
            await interaction.edit_original_response(embed=embed, view=self)


class SlotsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="slots", description="Interactive slots with hold controls.")
    @app_commands.describe(stake="Credits to bet per spin")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def slots_cmd(
        self,
        interaction: discord.Interaction,
        stake: app_commands.Range[float, 0.01, 50_000_000.0],
    ) -> None:
        await self.bot.responses.defer(interaction)
        stake_cents = parse_credits_to_cents(stake)
        record = await self.bot.db.ensure_user(interaction.user)
        if record.balance < stake_cents:
            await interaction.edit_original_response(
                content="Insufficient balance for that stake.",
                embed=None,
                view=None,
            )
            return

        view = SlotsView(
            self.bot,
            origin_interaction=interaction,
            stake=stake_cents,
            user_record=record,
        )
        embed = view.build_embed(footer="Press Spin to play. Use Hold buttons to lock reels.")
        await interaction.edit_original_response(content=None, embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SlotsCog(bot))
