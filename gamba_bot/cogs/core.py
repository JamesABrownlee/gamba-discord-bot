import discord
from discord import app_commands
from discord.ext import commands


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
            content=f"Balance for `{record.display_name}`: `{record.balance}` credits",
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CoreCog(bot))
