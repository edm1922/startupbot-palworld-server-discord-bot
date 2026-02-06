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

    @nextcord.slash_command(
        name="config", 
        description="Open configuration menu",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def config_command(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
        
        view = InteractiveConfigView(interaction.user.id)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)

    @nextcord.slash_command(
        name="setup_channels", 
        description="Configure bot channels",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
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
        skin_shop_channel: nextcord.TextChannel = nextcord.SlashOption(description="Skin Shop channel", required=False),
        wheel_channel: nextcord.TextChannel = nextcord.SlashOption(description="Lucky Wheel channel", required=False)
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
        if skin_shop_channel:
            config.set('skin_shop_channel_id', skin_shop_channel.id)
            changes.append(f"Skin Shop -> {skin_shop_channel.mention}")
        if wheel_channel:
            config.set('gambling_channel_id', wheel_channel.id)
            changes.append(f"Lucky Wheel -> {wheel_channel.mention}")

        if not changes:
            await interaction.response.send_message("No changes specified.", ephemeral=True)
            return

        embed = nextcord.Embed(title="Channels Updated", description="\n".join(changes), color=0x00FF00)
        await interaction.response.send_message(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(AdminConfig(bot))
