import nextcord
from nextcord.ext import commands, tasks
import asyncio
import logging
from utils.server_utils import (
    is_server_running, 
    verify_server_responsive, 
    get_server_state, 
    set_server_state, 
    ServerState,
    register_state_callback,
    update_status_channel_name
)
from utils.rest_api import rest_api
from utils.config_manager import config


class ServerStatusMonitor(commands.Cog):
    """Monitors server status and updates state based on process and REST API checks."""
    
    def __init__(self, bot):
        self.bot = bot
        self.last_known_state = ServerState.OFFLINE
        
        # Register the channel name update callback
        register_state_callback(update_status_channel_name)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Start the monitoring loop when bot is ready."""
        if not self.status_monitor_loop.is_running():
            self.status_monitor_loop.start()
            logging.info("🔍 Server status monitoring started")
    
    def cog_unload(self):
        """Stop the monitoring loop when cog is unloaded."""
        self.status_monitor_loop.cancel()
    
    @tasks.loop(seconds=15)  # Check every 15 seconds
    async def status_monitor_loop(self):
        """Continuously monitor server status and update state."""
        try:
            current_state = get_server_state()
            process_running = await is_server_running()
            
            # State machine logic
            if current_state == ServerState.OFFLINE:
                # If process appears while we think it's offline, set to STARTING
                if process_running:
                    logging.info("🟡 Server process detected while state was OFFLINE, transitioning to STARTING")
                    await set_server_state(ServerState.STARTING, self.bot)
            
            elif current_state == ServerState.STARTING:
                # Check if process is still running
                if not process_running:
                    logging.warning("🔴 Server process died during STARTING phase")
                    await set_server_state(ServerState.OFFLINE, self.bot)
                else:
                    # Try to verify REST API responsiveness
                    if rest_api.is_configured():
                        if await verify_server_responsive():
                            logging.info("🟢 Server is now fully ONLINE (REST API responsive)")
                            await set_server_state(ServerState.ONLINE, self.bot)
                            
                            # Send notification
                            status_channel_id = config.get('status_channel_id', 0)
                            if status_channel_id:
                                channel = self.bot.get_channel(status_channel_id)
                                if channel:
                                    embed = nextcord.Embed(
                                        title="paltastic", 
                                        description="🟢 **ONLINE**\nPalworld Server is now fully operational!", 
                                        color=0x00FF00
                                    )
                                    embed.set_footer(text="powered by Paltastic")
                                    try:
                                        await channel.send(embed=embed)
                                    except:
                                        pass
                    else:
                        # No REST API configured, just mark as ONLINE if process is running
                        logging.info("🟢 Server process running (REST API not configured)")
                        await set_server_state(ServerState.ONLINE, self.bot)
            
            elif current_state == ServerState.ONLINE:
                # Verify server is still running and responsive
                if not process_running:
                    logging.warning("🔴 Server process disappeared, transitioning to OFFLINE")
                    await set_server_state(ServerState.OFFLINE, self.bot)
                    
                    # Send notification
                    status_channel_id = config.get('status_channel_id', 0)
                    if status_channel_id:
                        channel = self.bot.get_channel(status_channel_id)
                        if channel:
                            embed = nextcord.Embed(
                                title="paltastic", 
                                description="🔴 **OFFLINE**\nPalworld Server has stopped", 
                                color=0xFF0000
                            )
                            embed.set_footer(text="powered by Paltastic")
                            try:
                                await channel.send(embed=embed)
                            except:
                                pass
                elif rest_api.is_configured():
                    # Periodically verify REST API is still responsive
                    if not await verify_server_responsive():
                        logging.warning("⚠️ Server process running but REST API not responding")
                        # Don't change state immediately, might be temporary
            
            elif current_state == ServerState.STOPPING:
                # Check if process has stopped
                if not process_running:
                    logging.info("🔴 Server has fully stopped")
                    await set_server_state(ServerState.OFFLINE, self.bot)
        
        except Exception as e:
            logging.error(f"❌ Error in status monitor loop: {e}")
    
    @status_monitor_loop.before_loop
    async def before_status_monitor(self):
        """Wait for bot to be ready before starting the loop."""
        await self.bot.wait_until_ready()
        
        # Initial state detection
        logging.info("🔍 Performing initial server state detection...")
        process_running = await is_server_running()
        
        if process_running:
            if rest_api.is_configured():
                if await verify_server_responsive():
                    logging.info("🟢 Initial state: ONLINE (process + REST API responsive)")
                    await set_server_state(ServerState.ONLINE, self.bot)
                else:
                    logging.info("🟡 Initial state: STARTING (process running, REST API not ready)")
                    await set_server_state(ServerState.STARTING, self.bot)
            else:
                logging.info("🟢 Initial state: ONLINE (process running, no REST API)")
                await set_server_state(ServerState.ONLINE, self.bot)
        else:
            logging.info("🔴 Initial state: OFFLINE")
            await set_server_state(ServerState.OFFLINE, self.bot)
    
    @nextcord.slash_command(description="Check current server status")
    async def serverstatus(self, interaction: nextcord.Interaction):
        """Show detailed server status information."""
        await interaction.response.defer(ephemeral=True)
        
        current_state = get_server_state()
        process_running = await is_server_running()
        
        # State emoji mapping
        state_info = {
            ServerState.OFFLINE: ("🔴 OFFLINE", 0xFF0000, "Server is not running"),
            ServerState.STARTING: ("🟡 STARTING", 0xFFFF00, "Server is initializing..."),
            ServerState.ONLINE: ("🟢 ONLINE", 0x00FF00, "Server is fully operational"),
            ServerState.STOPPING: ("🟠 STOPPING", 0xFF8800, "Server is shutting down")
        }
        
        title, color, description = state_info.get(current_state, ("⚪ UNKNOWN", 0x808080, "Unknown state"))
        
        embed = nextcord.Embed(
            title=f"Server Status: {title}",
            description=description,
            color=color
        )
        
        # Add detailed information
        embed.add_field(name="Process Running", value="✅ Yes" if process_running else "❌ No", inline=True)
        
        if rest_api.is_configured():
            api_responsive = await verify_server_responsive()
            embed.add_field(name="REST API", value="✅ Responsive" if api_responsive else "❌ Not Responding", inline=True)
        else:
            embed.add_field(name="REST API", value="⚠️ Not Configured", inline=True)
        
        # Get player count if API is available
        if rest_api.is_configured():
            player_data = await rest_api.get_player_list()
            if player_data:
                player_count = len(player_data.get('players', []))
                embed.add_field(name="Players Online", value=f"👥 {player_count}", inline=True)
        
        embed.set_footer(text="Status updates automatically every 15 seconds")
        
        await interaction.followup.send(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(ServerStatusMonitor(bot))
