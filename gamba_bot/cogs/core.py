import discord
from discord import app_commands
from discord.ext import commands
from gamba_bot.utils.currency import format_cents, parse_credits_to_cents


class CoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            await self.bot.db.ensure_user(message.author)
            return
        if self.bot.user and self.bot.user.mentioned_in(message):
            await self.bot.db.ensure_user(message.author)

    @app_commands.command(name="balance", description="Show your current credit balance.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def balance(self, interaction: discord.Interaction) -> None:
        record = await self.bot.db.ensure_user(interaction.user)
        await self.bot.responses.send_or_followup(
            interaction,
            content=f"Balance for `{record.display_name}`: `{format_cents(record.balance)}` credits",
        )

    @app_commands.command(name="admin_give", description="Admin: give credits to a server member.")
    @app_commands.guild_only()
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(member="Server member to receive credits", amount="Credit amount to give (e.g. 10.50)")
    async def admin_give(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[float, 0.01, 50_000_000.0],
    ) -> None:
        amount_cents = parse_credits_to_cents(amount)
        record = await self.bot.db.add_credits(member, amount_cents)
        await self.bot.responses.send_or_followup(
            interaction,
            content=(
                f"Gave `{format_cents(amount_cents)}` credits to `{member.display_name}`.\n"
                f"New balance: `{format_cents(record.balance)}` credits"
            ),
        )

    @balance.error
    async def on_balance_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(str(error), ephemeral=interaction.guild is not None)
        else:
            await interaction.response.send_message(str(error), ephemeral=interaction.guild is not None)

    @admin_give.error
    async def on_admin_give_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "You must be a server administrator to use this command."
        else:
            message = str(error)
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CoreCog(bot))
