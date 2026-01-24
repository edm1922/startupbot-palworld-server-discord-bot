import nextcord
import subprocess
import os
import asyncio
import psutil
import datetime
from nextcord.ext import commands
from dotenv import load_dotenv

# Import our new modules
from config_manager import config
from views import ServerControlView, InteractiveConfigView
from rest_api import rest_api
from server_utils import is_server_running, start_server, stop_server, restart_server, server_lock

# Environment variables are loaded automatically by config_manager

# Retrieve configuration values from our new config manager
TOKEN = config.get_discord_token()
GUILD_ID = config.get('guild_id', 0)
# We will use config.get directly in functions to ensure we always have the latest values
# without needing to restart the bot when settings are changed.
SERVER_DIRECTORY = config.get('server_directory', '')
STARTUP_SCRIPT = config.get('startup_script', '')

if not TOKEN:
    raise ValueError("❌ DISCORD_BOT_TOKEN not found! Check your .env file.")

if not SERVER_DIRECTORY or not STARTUP_SCRIPT:
    print("⚠️ Warning: Server directory or startup script not configured. Please use /config commands to set them.")

# Define bot with proper intents and command sync
intents = nextcord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!", 
    intents=intents,
    help_command=None
)

server_starter = None
restart_task = None
restart_enabled = True
next_restart_time = None  # Global to track when the next restart happens
attempts = {"start": {}, "stop": {}}  # Track attempts per user
MAX_ATTEMPTS = 3
ATTEMPT_RESET_TIME = 86400  # 24 hours in seconds
# Global variable for server control view
server_control_view = None
# Track task objects to prevent duplicates on reconnect
running_tasks = {}

import socket
import sys

# ... (imports)

def enforce_single_instance():
    """Ensure only one instance of the bot is running by binding to a dedicated port."""
    try:
        # Create a socket with a unique port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 64210))  # Arbitrary high port
        # Keep the socket open until program exit
        return s
    except socket.error as e:
        print(f"\n\n[FATAL ERROR]: Instance check failed: {e}")
        print("[FATAL ERROR]: ANOTHER INSTANCE OF THE BOT IS ALREADY RUNNING!")
        print("Please close all other Python windows/terminals and try again.")
        print("Exiting in 5 seconds...")
        import time
        time.sleep(5)
        sys.exit(1)

# Hold the socket object globally so it doesn't get garbage collected/closed
instance_lock = None

@bot.event
async def on_ready():
    print(f'[READY] Logged in as {bot.user}')
    print(f'[INFO] Connected to server: {GUILD_ID}')
    print(f'[INFO] Bot connected and ready!')
    # Initialize and add the persistent view for server controls only if not already done
    global server_control_view
    if server_control_view is None:
        print("[INIT] Initializing persistent ServerControlView...")
        server_control_view = ServerControlView()
        bot.add_view(server_control_view)
    else:
        print("[INFO] ServerControlView already initialized, skipping.")
    
    print(f'[READY] Commands will be available in guild: {GUILD_ID}')
    
    # Set bot status
    await bot.change_presence(activity=nextcord.Game(name="/palhelp"))
    
    # Force sync commands
    try:
        print("[SYNC] Syncing commands...")
        await bot.sync_all_application_commands()
        print('[SUCCESS] All slash commands synced successfully!')
    except Exception as e:
        print(f"[ERROR] Failed to sync commands: {e}")
    
    asyncio.create_task(monitor_system_ram())
    
    # Start tasks only if not already running
    if 'auto_restart' not in running_tasks or running_tasks['auto_restart'].done():
        running_tasks['auto_restart'] = asyncio.create_task(auto_restart())
    
    if 'scheduled_shutdown' not in running_tasks or running_tasks['scheduled_shutdown'].done():
        running_tasks['scheduled_shutdown'] = asyncio.create_task(scheduled_shutdown())
        
    if 'scheduled_startup' not in running_tasks or running_tasks['scheduled_startup'].done():
        running_tasks['scheduled_startup'] = asyncio.create_task(scheduled_startup())
        
    if 'reset_attempts' not in running_tasks or running_tasks['reset_attempts'].done():
        running_tasks['reset_attempts'] = asyncio.create_task(reset_attempts())
        
    if 'tail_palguard_logs' not in running_tasks or running_tasks['tail_palguard_logs'].done():
        running_tasks['tail_palguard_logs'] = asyncio.create_task(tail_palguard_logs())
        
    if 'monitor_players' not in running_tasks or running_tasks['monitor_players'].done():
        running_tasks['monitor_players'] = asyncio.create_task(monitor_players())

# @bot.event
# async def on_interaction(interaction: nextcord.Interaction):
#     print(f"📨 Received interaction: {interaction.type} - ID: {interaction.data.get('custom_id') or interaction.data.get('name')}")
#     # Handle button interactions for server controls
#     if interaction.type == nextcord.InteractionType.component:
#         if interaction.data["custom_id"] in ["start_server_btn", "restart_server_btn", "stop_server_btn"]:
#             # The view will handle permissions and the actual functionality
#             # Just make sure the interaction is acknowledged
#             pass

# Slash command for server controls
@bot.slash_command(description="Show server control panel with buttons", guild_ids=[GUILD_ID])
async def server_controls(interaction: nextcord.Interaction):
    try:
        # Check if user has permission
        admin_id = config.get('admin_user_id', 0)
        
        # Safe permission check
        is_admin = False
        if interaction.user.id == admin_id:
            is_admin = True
        elif hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator:
            is_admin = True
            
        if not is_admin:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        embed = nextcord.Embed(
            title="Palworld Server Controls",
            description="Use the buttons below to control the Palworld server.",
            color=0x00FF00
        )
        
        # Ensure view exists
        global server_control_view
        if server_control_view is None:
            server_control_view = ServerControlView()
            bot.add_view(server_control_view)
            
        await interaction.response.send_message(embed=embed, view=server_control_view, ephemeral=True)
    except Exception as e:
        print(f"Error in server_controls: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
        except:
            pass

# Configuration slash commands
@bot.slash_command(name="config", description="Open configuration modals", guild_ids=[GUILD_ID])
async def config_command(interaction: nextcord.Interaction):
    print("👉 Config command triggered!")
    try:
        # Check if user has permission
        admin_id = config.get('admin_user_id', 0)
        
        # Safe permission check
        is_admin = False
        if interaction.user.id == admin_id:
            is_admin = True
        elif hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator:
            is_admin = True
            
        if not is_admin:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        view = InteractiveConfigView(interaction.user.id)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)
    except Exception as e:
        print(f"Error in config command: {e}")
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
        except:
            pass

@bot.slash_command(name="setup_channels", description="Configure bot channels by selecting them", guild_ids=[GUILD_ID])
async def setup_channels(
    interaction: nextcord.Interaction,
    admin_channel: nextcord.TextChannel = nextcord.SlashOption(description="Channel for admin commands", required=False),
    status_channel: nextcord.TextChannel = nextcord.SlashOption(description="Channel for server status (Online/Offline)", required=False),
    ram_channel: nextcord.TextChannel = nextcord.SlashOption(description="Channel for RAM usage monitoring", required=False),
    chat_channel: nextcord.TextChannel = nextcord.SlashOption(description="Channel for Game <-> Discord chat", required=False),
    monitor_channel: nextcord.TextChannel = nextcord.SlashOption(description="Channel for Player Join/Leave notifications", required=False)
):
    # Check if user has permission
    admin_id = config.get('admin_user_id', 0)
    if interaction.user.id != admin_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    changes = []
    if admin_channel:
        config.set('allowed_channel_id', admin_channel.id)
        changes.append(f"Admin Channel -> {admin_channel.mention}")
    
    if status_channel:
        config.set('status_channel_id', status_channel.id)
        changes.append(f"Status Channel -> {status_channel.mention}")

    if ram_channel:
        config.set('ram_usage_channel_id', ram_channel.id)
        changes.append(f"RAM Channel -> {ram_channel.mention}")

    if chat_channel:
        config.set('chat_channel_id', chat_channel.id)
        changes.append(f"Chat Channel -> {chat_channel.mention}")

    if monitor_channel:
        config.set('player_monitor_channel_id', monitor_channel.id)
        changes.append(f"Monitor Channel -> {monitor_channel.mention}")

    if not changes:
        await interaction.response.send_message("No changes specified.", ephemeral=True)
        return

    embed = nextcord.Embed(
        title="Channels Updated",
        description="\n".join(changes),
        color=0x00FF00
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(name="edit", description="Edit server configuration settings", guild_ids=[GUILD_ID])
async def edit(
    interaction: nextcord.Interaction,
    server_dir: str = nextcord.SlashOption(description="Full path to server directory", required=False),
    startup_script: str = nextcord.SlashOption(description="Name of the startup batch file", required=False),
    shutdown_time: str = nextcord.SlashOption(description="Daily shutdown time (HH:MM)", required=False),
    startup_time: str = nextcord.SlashOption(description="Daily startup time (HH:MM)", required=False),
    api_endpoint: str = nextcord.SlashOption(description="REST API Endpoint (IP:Port)", required=False),
    api_key: str = nextcord.SlashOption(description="REST API Key (Admin Password)", required=False),
    log_dir: str = nextcord.SlashOption(description="PalGuard Logs directory path", required=False),
    webhook_url: str = nextcord.SlashOption(description="Webhook URL for chat relay", required=False),
    admin_user: nextcord.Member = nextcord.SlashOption(description="Set a specific bot administrator", required=False)
):
    # Check if user has permission
    admin_id = config.get('admin_user_id', 0)
    if interaction.user.id != admin_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    changes = []
    if server_dir:
        config.set('server_directory', server_dir)
        changes.append(f"Server Directory: `{server_dir}`")
    
    if startup_script:
        config.set('startup_script', startup_script)
        changes.append(f"Startup Script: `{startup_script}`")

    if shutdown_time:
        config.set('shutdown_time', shutdown_time)
        changes.append(f"Shutdown Time: `{shutdown_time}`")

    if startup_time:
        config.set('startup_time', startup_time)
        changes.append(f"Startup Time: `{startup_time}`")

    if api_endpoint:
        config.set('rest_api_endpoint', api_endpoint)
        changes.append(f"API Endpoint: `{api_endpoint}`")

    if api_key:
        config.set('rest_api_key', api_key)
        changes.append(f"API Key: `********`")

    if log_dir:
        config.set('log_directory', log_dir)
        changes.append(f"Log Directory: `{log_dir}`")

    if webhook_url:
        config.set('chat_webhook_url', webhook_url)
        changes.append(f"Webhook URL: `Updated`")

    if admin_user:
        config.set('admin_user_id', admin_user.id)
        changes.append(f"Admin User: {admin_user.mention}")

    if not changes:
        await interaction.response.send_message("No changes specified.", ephemeral=True)
        return

    embed = nextcord.Embed(
        title="Configuration Updated",
        description="\n".join(changes),
        color=0x00FF00
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)



# Slash command to show player list using REST API
@bot.slash_command(description="Show current players on the server", guild_ids=[GUILD_ID])
async def players(interaction: nextcord.Interaction):
    if not rest_api.is_configured():
        await interaction.response.send_message(
            "REST API is not configured. Please use /config to set up REST API endpoint and key.", 
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    player_data = await rest_api.get_player_list()
    
    if player_data:
        player_list = player_data.get('players', [])
        if player_list:
            player_names = "\n".join([f"• {player.get('name', 'Unknown')}" for player in player_list])
            embed = nextcord.Embed(
                title=f"Current Players ({len(player_list)})",
                description=player_names,
                color=0x00FF00
            )
        else:
            embed = nextcord.Embed(
                title="Current Players",
                description="No players currently online.",
                color=0xFFFF00
            )
    else:
        error_msg = rest_api.get_last_error()
        embed = nextcord.Embed(
            title="Player List Error",
            description=f"❌ **Failed to fetch players:**\n{error_msg}",
            color=0xFF0000
        )
        if "Connection Failed" in error_msg:
             embed.set_footer(text="Tip: If the bot is on the same PC as the server, try using 127.0.0.1 as the endpoint.")
    
    await interaction.followup.send(embed=embed, ephemeral=True)

# Slash command to show server info using REST API
@bot.slash_command(description="Show server information", guild_ids=[GUILD_ID])
async def serverinfo(interaction: nextcord.Interaction):
    if not rest_api.is_configured():
        await interaction.response.send_message(
            "REST API is not configured. Please use /config to set up REST API endpoint and key.", 
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    server_data = await rest_api.get_server_info()
    
    if server_data:
        embed = nextcord.Embed(
            title="Server Information",
            color=0x00FF00
        )
        
        for key, value in server_data.items():
            embed.add_field(name=key.title(), value=str(value), inline=True)
    else:
        error_msg = rest_api.get_last_error()
        embed = nextcord.Embed(
            title="Server Info Error",
            description=f"❌ **Failed to fetch server info:**\n{error_msg}",
            color=0xFF0000
        )
    
    await interaction.followup.send(embed=embed, ephemeral=True)

# Slash command to save the world
@bot.slash_command(description="Save the current world state", guild_ids=[GUILD_ID])
async def saveworld(interaction: nextcord.Interaction):
    # Check if user has permission
    admin_id = config.get('admin_user_id', 0)
    if interaction.user.id != admin_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if not rest_api.is_configured():
        await interaction.response.send_message(
            "REST API is not configured. World save requires REST API.", 
            ephemeral=True
        )
        return
    
    success = await rest_api.save_world()
    if success:
        await interaction.response.send_message("✅ World save command sent to server.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed to send world save command to server.", ephemeral=True)

# Slash command to check next restart
@bot.slash_command(description="Check how much time is left until the next auto-restart", guild_ids=[GUILD_ID])
async def nextrestart(interaction: nextcord.Interaction):
    global next_restart_time
    
    if not config.get('auto_restart_enabled', True):
        await interaction.response.send_message("ℹ️ Auto-restart is currently **disabled** in configuration.", ephemeral=True)
        return
        
    if next_restart_time is None:
        await interaction.response.send_message("⏳ Next restart time has not been calculated yet. The cycle might be starting...", ephemeral=True)
        return
        
    now = datetime.datetime.now()
    if next_restart_time <= now:
        await interaction.response.send_message("🔄 Restart is happening **right now** or very soon!", ephemeral=True)
        return
        
    diff = next_restart_time - now
    hours, remainder = divmod(int(diff.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    time_str = ""
    if hours > 0: time_str += f"{hours}h "
    if minutes > 0: time_str += f"{minutes}m "
    time_str += f"{seconds}s"
    
    embed = nextcord.Embed(
        title="⏰ Next Auto-Restart",
        description=f"The server is scheduled to restart in **{time_str.strip()}**.",
        color=0xFEE75C
    )
    embed.add_field(name="Scheduled Time", value=f"<t:{int(next_restart_time.timestamp())}:T> (Local Time)", inline=False)
    
    # Add status info
    if not await is_server_running():
        embed.set_footer(text="⚠️ Note: Server is currently offline. Restart may be skipped.")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Slash command for help
@bot.slash_command(name="palhelp", description="List down all available commands", guild_ids=[GUILD_ID])
async def help_command(interaction: nextcord.Interaction):
    embed = nextcord.Embed(
        title="🤖 Bot Commands Help",
        description="Here is a list of all available commands for the bot:",
        color=0x00ADD8
    )
    
    # Slash Commands section
    slash_cmds = (
        "**/palhelp** - Show this help message\n"
        "**/server_controls** - Show server control panel with buttons (Admin only)\n"
        "**/config** - Open configuration modals (Admin only)\n"
        "**/setup_channels** - Select channels for various bot features (Admin only)\n"
        "**/edit** - Edit server settings directly (Admin only)\n"
        "**/players** - Show current players online\n"
        "**/serverinfo** - Show detailed server information\n"
        "**/saveworld** - Manually save the world state (Admin only)\n"
        "**/nextrestart** - See time remaining until next auto-restart"
    )
    embed.add_field(name="🚀 Slash Commands", value=slash_cmds, inline=False)
    
    # Prefix Commands section
    prefix_cmds = (
        "**!startserver** - Start the Palworld server (Admin only)\n"
        "**!stopserver** - Stop the Palworld server (Admin only)"
    )
    embed.add_field(name="⌨️ Prefix Commands", value=prefix_cmds, inline=False)
    
    embed.set_footer(text="Powered by Paltastic")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Update the original commands to use new config
@bot.command(name="stopserver")
async def stopserver(ctx):
    # Check if user has permission
    admin_id = config.get('admin_user_id', 0)
    if ctx.author.id != admin_id and not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permission to use this command.")
        return
        
    user_attempts = attempts["stop"].get(ctx.author.id, 0)
    if ctx.author.id != admin_id:
        if user_attempts >= MAX_ATTEMPTS:
            return await ctx.send("❌ You have reached the maximum attempts for today.")
        attempts["stop"][ctx.author.id] = user_attempts + 1
    async with server_lock:
        await stop_server(bot)
    await ctx.send(f"✅ Server shutdown initiated. (Attempts left: {MAX_ATTEMPTS - attempts['stop'][ctx.author.id]}/{MAX_ATTEMPTS})")

@bot.command(name="startserver")
async def startserver(ctx):
    # Check if user has permission
    admin_id = config.get('admin_user_id', 0)
    if ctx.author.id != admin_id and not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permission to use this command.")
        return
        
    user_attempts = attempts["start"].get(ctx.author.id, 0)
    if ctx.author.id != admin_id:
        if user_attempts >= MAX_ATTEMPTS:
            return await ctx.send("❌ You have reached the maximum attempts for today.")
        attempts["start"][ctx.author.id] = user_attempts + 1
    async with server_lock:
        if await is_server_running():
            return await ctx.send("✅ Server is already running!")
        await start_server(bot)
    await ctx.send(f"✅ Server startup initiated. (Attempts left: {MAX_ATTEMPTS - attempts['start'][ctx.author.id]}/{MAX_ATTEMPTS})")

def is_allowed_channel(ctx):
    allowed_id = config.get('allowed_channel_id', 0)
    return ctx.channel and ctx.channel.id == allowed_id


async def reset_attempts():
    while True:
        await asyncio.sleep(ATTEMPT_RESET_TIME)
        attempts["start"].clear()
        attempts["stop"].clear()

async def monitor_system_ram():
    while True:
        memory = psutil.virtual_memory()
        total_memory = memory.total / (1024 ** 3)
        used_memory = memory.used / (1024 ** 3)
        memory_percent = memory.percent
        
        ram_channel_id = config.get('ram_usage_channel_id', 0)
        ram_channel = bot.get_channel(ram_channel_id)
        if ram_channel:
            await ram_channel.send(f"💻 **System RAM Usage:** {used_memory:.2f} GB / {total_memory:.2f} GB ({memory_percent}% used)")
        await asyncio.sleep(600)

async def monitor_players():
    """Monitors player join/leave events via REST API"""
    last_players = set()
    first_run = True
    
    while True:
        try:
            if not rest_api.is_configured():
                await asyncio.sleep(30)
                continue
            
            # Skip check if server is offline to avoid console spam
            if not await is_server_running():
                # Clear state so we can detect joins immediately when it comes back up
                if last_players:
                    print("📡 Server offline: Clearing player monitoring state.")
                    last_players = set()
                first_run = True
                await asyncio.sleep(15)
                continue

            player_data = await rest_api.get_player_list()
            if player_data is not None:
                players = player_data.get('players', [])
                current_players = {p.get('userId'): p.get('name') for p in players if p.get('userId')}
                
                # Check for joins and leaves
                if not first_run:
                    # Joined
                    for uid, name in current_players.items():
                        if uid not in last_players:
                            await send_player_event(name, "joined")
                    
                    # Left
                    for uid, name in last_players.items():
                        if uid not in current_players:
                            await send_player_event(name, "left")
                
                last_players = current_players
                first_run = False
        except Exception as e:
            print(f"Error in monitor_players: {e}")
            
        await asyncio.sleep(15) # Check every 15 seconds

async def send_player_event(name, event_type):
    """Sends join/leave notification to the designated channel"""
    channel_id = config.get('player_monitor_channel_id', 0)
    channel = bot.get_channel(channel_id)
    
    if channel:
        color = 0x00FF00 if event_type == "joined" else 0xFF0000
        icon = "📥" if event_type == "joined" else "📤"
        
        embed = nextcord.Embed(
            description=f"{icon} **{name}** has {event_type} the server.",
            color=color,
            timestamp=nextcord.utils.utcnow()
        )
        await channel.send(embed=embed)

async def auto_restart():
    """Periodically restarts the server based on the configured interval"""
    while True:
        try:
            # Get latest interval from config
            interval = config.get('restart_interval', 10800)
            
            # 📢 Pre-restart Announcements
            announcements_str = config.get('restart_announcements', '30,10,5,1')
            try:
                # Convert to sorted list of seconds in descending order
                announce_times = sorted([int(m.strip()) * 60 for m in announcements_str.split(',') if m.strip().isdigit()], reverse=True)
            except:
                announce_times = [1800, 600, 300, 60] # Default fallback

            # Calculate actual sleep time (interval - max countdown)
            # This ensures the total cycle matches the interval
            countdown_duration = max(announce_times) if announce_times else 0
            initial_sleep = max(0, interval - countdown_duration)
            
            print(f"🚥 Auto-Restart Cycle: Sleeping {initial_sleep}s, then {countdown_duration}s countdown.")
            
            # Update the global next_restart_time for users to see
            global next_restart_time
            next_restart_time = datetime.datetime.now() + datetime.timedelta(seconds=initial_sleep + countdown_duration)
            
            await asyncio.sleep(initial_sleep)
            
            global restart_enabled
            if not config.get('auto_restart_enabled', True) or not restart_enabled:
                print("⏭️ Auto-Restart Skipped: Feature is disabled in configuration.")
                await asyncio.sleep(60) # Wait a bit before checking again
                continue

            # Check if server is actually running first
            if not await is_server_running():
                print("⏭️ Auto-Restart Skipped: Server is currently offline.")
                await asyncio.sleep(60)
                continue

            print(f"⏰ Auto-Restart Threshold Reached. Starting countdown.")
            
            # Notify admin channel about the start of the countdown
            if announce_times:
                allowed_channel_id = config.get('allowed_channel_id', 0)
                channel = bot.get_channel(allowed_channel_id)
                if channel:
                    await channel.send(f"🔄 **Auto-Restart:** Countdown started. Server will restart in {max(announce_times)//60} minutes.")

                # Run countdown
                for i, wait_sec in enumerate(announce_times):
                    if rest_api.is_configured():
                        mins = wait_sec // 60
                        msg = f"⚠️ SERVER RESTART IN {mins} MINUTE{'S' if mins != 1 else ''} FOR MAINTENANCE"
                        if wait_sec < 60:
                            msg = f"⚠️ SERVER RESTART IN {wait_sec} SECONDS"
                        await rest_api.broadcast_message(msg)
                    
                    # Sleep until the next announcement
                    if i < len(announce_times) - 1:
                        sleep_duration = wait_sec - announce_times[i+1]
                        if sleep_duration > 0:
                            await asyncio.sleep(sleep_duration)
                    else:
                        # Last announcement, sleep the remaining time
                        await asyncio.sleep(announce_times[-1])
            
            # Perform the restart
            async with server_lock:
                success = await restart_server(bot, graceful=True)
            
            if not success:
                print("⚠️ Auto-Restart: Sequence failed. Retrying in 10 minutes instead of waiting for full interval.")
                # Update next restart time to reflect retry
                next_restart_time = datetime.datetime.now() + datetime.timedelta(minutes=10)
                await asyncio.sleep(600)
            else:
                print("✅ Auto-Restart: Sequence completed successfully.")
            
        except Exception as e:
            print(f"❌ Error in auto_restart task: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(60) # Prevent tight loop on crash


async def scheduled_shutdown():
    """Daily server shutdown at a specific time."""
    last_triggered_date = None
    while True:
        try:
            now = datetime.datetime.now()
            shutdown_str = config.get('shutdown_time', '05:00')
            
            # Simple format validation
            if ':' not in shutdown_str:
                await asyncio.sleep(60)
                continue
                
            h, m = map(int, shutdown_str.split(':'))
            
            # Check if it's currently the target time and we haven't triggered today
            if now.hour == h and now.minute == m and last_triggered_date != now.date():
                if await is_server_running():
                    print(f"⏰ Scheduled Shutdown Triggered: {shutdown_str}")
                    
                    # Notify admin channel
                    admin_channel_id = config.get('allowed_channel_id', 0)
                    admin_channel = bot.get_channel(admin_channel_id)
                    if admin_channel:
                        await admin_channel.send(f"🕒 **Scheduled Shutdown:** Initiating shutdown process ({shutdown_str})...")
                    
                    # Use the improved stop_server which now handles graceful shutdown 
                    # organically if REST API is configured, then falls back to force stop.
                    if rest_api.is_configured():
                        await rest_api.broadcast_message("⚠️ DAILY SCHEDULED SHUTDOWN IN 10 SECONDS")
                        await asyncio.sleep(10)

                    async with server_lock:
                        await stop_server(bot, graceful=True)
                    last_triggered_date = now.date()
                else:
                    # Server already offline, just mark as triggered for today
                    last_triggered_date = now.date()
                    print(f"⏰ Scheduled Shutdown Skipped: Server already offline ({shutdown_str})")
                    
        except Exception as e:
            print(f"Error in scheduled_shutdown: {e}")
            
        await asyncio.sleep(10) # Check every 10 seconds for efficiency

async def scheduled_startup():
    """Daily server startup at a specific time."""
    last_triggered_date = None
    while True:
        try:
            now = datetime.datetime.now()
            startup_str = config.get('startup_time', '10:00')
            
            if ':' not in startup_str:
                await asyncio.sleep(60)
                continue
                
            h, m = map(int, startup_str.split(':'))
            
            # Check if it's currently the target time and we haven't triggered today
            if now.hour == h and now.minute == m and last_triggered_date != now.date():
                if not await is_server_running():
                    print(f"⏰ Scheduled Startup Triggered: {startup_str}")
                    
                    # Notify admin channel
                    admin_channel_id = config.get('allowed_channel_id', 0)
                    admin_channel = bot.get_channel(admin_channel_id)
                    if admin_channel:
                        await admin_channel.send(f"🕒 **Scheduled Startup:** Initiating daily startup ({startup_str})...")
                        
                    async with server_lock:
                        await start_server(bot)
                    last_triggered_date = now.date()
                else:
                    # Server already online, just mark as triggered for today
                    last_triggered_date = now.date()
                    print(f"⏰ Scheduled Startup Skipped: Server already online ({startup_str})")
                    
        except Exception as e:
            print(f"Error in scheduled_startup: {e}")
            
        await asyncio.sleep(10) # Check every 10 seconds for efficiency




@bot.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author == bot.user:
        return

    # Process normal commands (!startserver, etc)
    await bot.process_commands(message)

    # Cross-Chat: Discord -> Palworld
    chat_channel_id = config.get('chat_channel_id', 0)
    if message.channel.id == chat_channel_id and not message.content.startswith('!'):
        if rest_api.is_configured():
            # Broadcast the message in-game with [Discord] prefix as seen in example
            broadcast_text = f"[Discord] {message.author.display_name}: {message.content}"
            success = await rest_api.broadcast_message(broadcast_text)
            if success:
                # Add a subtle reaction to show it was sent
                try: await message.add_reaction("🎮")
                except: pass
        else:
            print("⚠️ Cannot relay Discord message: REST API not configured.")

import re
import aiohttp

async def tail_palguard_logs():
    """Tails the latest PalGuard/PalDefender log file to relay in-game chat to Discord
    Refined based on palchat_example using regex and premium formatting.
    """
    last_pos = 0
    current_log_file = None
    blocked_phrases = ["/adminpassword", "/creativemenu", "/"]
    
    # Regex from palchat_example to extract user and message
    chat_regex = r"\[Chat::(?:Global)\]\['([^']+)'.*\]: (.*)"
    
    while True:
        try:
            log_dir = config.get('log_directory', '').strip()
            chat_channel_id = config.get('chat_channel_id', 0)
            webhook_url = config.get('chat_webhook_url', '').strip()
            
            if not log_dir or not chat_channel_id:
                await asyncio.sleep(10)
                continue
                
            if not os.path.exists(log_dir):
                await asyncio.sleep(10)
                continue

            files = sorted(
                [f for f in os.listdir(log_dir) if f.endswith('.log') or f.endswith('.txt')],
                key=lambda x: os.path.getmtime(os.path.join(log_dir, x)),
                reverse=True
            )
            
            if not files:
                await asyncio.sleep(5)
                continue
                
            latest_file = os.path.join(log_dir, files[0])

            if latest_file != current_log_file:
                current_log_file = latest_file
                last_pos = os.path.getsize(current_log_file)
                print(f"📑 Watching log: {current_log_file}")

            file_size = os.path.getsize(current_log_file)
            
            if file_size > last_pos:
                with open(current_log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_pos)
                    lines = f.readlines()
                    last_pos = f.tell()
                    
                    channel = bot.get_channel(chat_channel_id)
                    if not channel and not webhook_url:
                        continue

                    for line in lines:
                        # Use regex from example for robust parsing
                        match = re.search(chat_regex, line)
                        if match:
                            username, content = match.groups()
                            
                            # Filter blocked phrases
                            if any(bp in content for bp in blocked_phrases):
                                continue

                            # Option A: Send via Webhook (Premium look: shows player name as sender)
                            if webhook_url:
                                async with aiohttp.ClientSession() as session:
                                    payload = {"username": username, "content": content}
                                    async with session.post(webhook_url, json=payload) as resp:
                                        if resp.status >= 400:
                                            print(f"⚠️ Webhook failed ({resp.status})")
                                            # Fallback to normal message if webhook fails
                                            if channel: await channel.send(f"💬 **In-Game:** {username}: {content}")
                            # Option B: Normal bot message
                            elif channel:
                                await channel.send(f"💬 **In-Game:** {username}: {content}")
            
        except Exception as e:
            print(f"Error in tail_palguard_logs: {e}")
            
        await asyncio.sleep(2) # Check every 2 seconds

if __name__ == "__main__":
    instance_lock = enforce_single_instance()
    bot.run(TOKEN)
