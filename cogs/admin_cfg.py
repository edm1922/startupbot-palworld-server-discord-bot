import nextcord
from nextcord.ext import commands
import logging
from utils.config_manager import config
from cogs.views import InteractiveConfigView

class AdminConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, interaction: nextcord.Interaction):
        admin_id = config.get('admin_user_id', 0)
        if interaction.user.id == admin_id:
            return True
        if hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator:
            return True
        return False

    @nextcord.slash_command(name="config", description="Open configuration menu")
    async def config_command(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
        
        view = InteractiveConfigView(interaction.user.id)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)

    @nextcord.slash_command(name="setup_channels", description="Configure bot channels")
    async def setup_channels(
        self,
        interaction: nextcord.Interaction,
        admin_channel: nextcord.TextChannel = nextcord.SlashOption(description="Admin commands channel", required=False),
        status_channel: nextcord.TextChannel = nextcord.SlashOption(description="Status announcements", required=False),
        ram_channel: nextcord.TextChannel = nextcord.SlashOption(description="RAM monitor reports", required=False),
        chat_channel: nextcord.TextChannel = nextcord.SlashOption(description="Chat relay", required=False),
        monitor_channel: nextcord.TextChannel = nextcord.SlashOption(description="Player logs", required=False),
        stats_channel: nextcord.TextChannel = nextcord.SlashOption(description="Live stats", required=False),
        shop_channel: nextcord.TextChannel = nextcord.SlashOption(description="Shop channel", required=False),
        roulette_channel: nextcord.TextChannel = nextcord.SlashOption(description="Roulette channel", required=False),
        blackjack_channel: nextcord.TextChannel = nextcord.SlashOption(description="Blackjack channel", required=False)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        changes = []
        if admin_channel:
            config.set('allowed_channel_id', admin_channel.id)
            changes.append(f"Admin -> {admin_channel.mention}")
        if status_channel:
            config.set('status_channel_id', status_channel.id)
            changes.append(f"Status -> {status_channel.mention}")
        if ram_channel:
            config.set('ram_usage_channel_id', ram_channel.id)
            changes.append(f"RAM -> {ram_channel.mention}")
        if chat_channel:
            config.set('chat_channel_id', chat_channel.id)
            changes.append(f"Chat -> {chat_channel.mention}")
        if monitor_channel:
            config.set('player_monitor_channel_id', monitor_channel.id)
            changes.append(f"Monitor -> {monitor_channel.mention}")
        if stats_channel:
            config.set('stats_channel_id', stats_channel.id)
            changes.append(f"Stats -> {stats_channel.mention}")
        if shop_channel:
            config.set('shop_channel_id', shop_channel.id)
            changes.append(f"Shop -> {shop_channel.mention}")
        if roulette_channel:
            config.set('gambling_channel_id', roulette_channel.id)
            changes.append(f"Roulette -> {roulette_channel.mention}")
        if blackjack_channel:
            config.set('blackjack_channel_id', blackjack_channel.id)
            changes.append(f"Blackjack -> {blackjack_channel.mention}")

        if not changes:
            await interaction.response.send_message("No changes specified.", ephemeral=True)
            return

        embed = nextcord.Embed(title="Channels Updated", description="\n".join(changes), color=0x00FF00)
        await interaction.response.send_message(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(AdminConfig(bot))
