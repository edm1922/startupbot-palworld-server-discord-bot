import nextcord
from nextcord.ext import commands
import datetime
import logging
from utils.config_manager import config
from utils.rest_api import rest_api
from utils.server_utils import is_server_running
from utils.rcon_utility import rcon_util
from utils.database import db
from cogs.views import ServerControlView

class ServerManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.next_restart_time = None # This will be updated by the main loop

    def is_admin(self, interaction: nextcord.Interaction):
        admin_id = config.get('admin_user_id', 0)
        if interaction.user.id == admin_id:
            return True
        if hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator:
            return True
        return False

    @nextcord.slash_command(
        name="server_controls", 
        description="Show server control panel with buttons",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def server_controls(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        embed = nextcord.Embed(
            title="Palworld Server Controls",
            description="Use the buttons below to control the Palworld server.",
            color=0x00FF00
        )
        
        # In modular version, we assume ServerControlView is already added to bot in main.py
        # or we can create a fresh one here.
        view = ServerControlView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @nextcord.slash_command(description="Show current players on the server")
    async def players(self, interaction: nextcord.Interaction):
        if not rest_api.is_configured():
            await interaction.response.send_message("❌ REST API is not configured.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        player_data = await rest_api.get_player_list()
        
        if player_data:
            player_list = player_data.get('players', [])
            if player_list:
                player_entries = [f"• **{p.get('name', 'Unknown')}** (`{p.get('userId', 'Unknown')}`)" for p in player_list]
                embed = nextcord.Embed(
                    title=f"Current Players ({len(player_list)})",
                    description="\n".join(player_entries),
                    color=0x00FF00
                )
            else:
                embed = nextcord.Embed(title="Current Players", description="No players online.", color=0xFFFF00)
        else:
            embed = nextcord.Embed(title="Error", description=f"❌ Failed to fetch players: {rest_api.get_last_error()}", color=0xFF0000)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @nextcord.slash_command(description="Show server information")
    async def serverinfo(self, interaction: nextcord.Interaction):
        if not rest_api.is_configured():
            await interaction.response.send_message("❌ REST API is not configured.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        server_data = await rest_api.get_server_info()
        
        if server_data:
            embed = nextcord.Embed(title="Server Information", color=0x00FF00)
            for key, value in server_data.items():
                embed.add_field(name=key.title(), value=str(value), inline=True)
        else:
            embed = nextcord.Embed(title="Error", description=f"❌ Failed to fetch info: {rest_api.get_last_error()}", color=0xFF0000)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @nextcord.slash_command(
        name="saveworld", 
        description="Save the current world state",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def saveworld(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
        
        if not rest_api.is_configured():
            await interaction.response.send_message("❌ REST API required for save.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        success = await rest_api.save_world()
        await interaction.followup.send("✅ World save command sent." if success else "❌ Save failed.", ephemeral=True)

    @nextcord.slash_command(description="Check time until next auto-restart")
    async def nextrestart(self, interaction: nextcord.Interaction):
        # We need to access the next_restart_time from the bot instance or a shared state
        start_time = getattr(self.bot, 'next_restart_time', None)
        
        if not config.get('auto_restart_enabled', True):
            await interaction.response.send_message("ℹ️ Auto-restart is disabled.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
            
        if start_time is None:
            await interaction.followup.send("⏳ Calculating next restart...", ephemeral=True)
            return
            
        now = datetime.datetime.now()
        if start_time <= now:
            await interaction.followup.send("🔄 Restart is imminent!", ephemeral=True)
            return
            
        diff = start_time - now
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        time_str = f"{hours}h {minutes}m {seconds}s"
        embed = nextcord.Embed(title="⏰ Next Auto-Restart", description=f"Restart in **{time_str}**.", color=0xFEE75C)
        embed.add_field(name="Scheduled Time", value=f"<t:{int(start_time.timestamp())}:T>", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @nextcord.slash_command(
        name="test_give_item", 
        description="Test giving an item via RCON",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def test_give_item(
        self,
        interaction: nextcord.Interaction,
        player_name: str = nextcord.SlashOption(description="Exact player name"),
        item_id: str = nextcord.SlashOption(description="Item ID"),
        amount: int = nextcord.SlashOption(description="Amount", default=1, min_value=1)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        if not rcon_util.is_configured():
            await interaction.response.send_message("❌ RCON not configured.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        stats = await db.get_player_stats_by_name(player_name.strip())
        if not stats:
            await interaction.followup.send(f"❌ Player '{player_name}' not found.")
            return
        
        success, resp = await rcon_util.give_item(stats['steam_id'], item_id, amount)
        if success:
            await interaction.followup.send(f"✅ Sent **{amount}x {item_id}** to **{player_name}**.\nResponse: `{resp}`")
        else:
            await interaction.followup.send(f"❌ RCON command failed: `{resp}`")

    @test_give_item.on_autocomplete("player_name")
    async def player_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = await db.get_player_names_autocomplete(current)
        await interaction.response.send_autocomplete(choices)

def setup(bot):
    bot.add_cog(ServerManagement(bot))
