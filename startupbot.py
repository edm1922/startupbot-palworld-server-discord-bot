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

# Load environment variables from .env file
load_dotenv()

# Retrieve configuration values from our new config manager
TOKEN = config.get_discord_token()
GUILD_ID = config.get('guild_id', 0)
ALLOWED_CHANNEL_ID = config.get('allowed_channel_id', 0)
STATUS_CHANNEL_ID = config.get('status_channel_id', 0)
RAM_USAGE_CHANNEL_ID = config.get('ram_usage_channel_id', 0)
PLAYER_MONITOR_CHANNEL_ID = config.get('player_monitor_channel_id', 0)
# RESTART_INTERVAL is now pulled dynamically from config in the auto_restart loop
SERVER_DIRECTORY = config.get('server_directory', '')
STARTUP_SCRIPT = config.get('startup_script', '')
SHUTDOWN_TIME = config.get('shutdown_time', "05:00")
STARTUP_TIME = config.get('startup_time', "10:00")
ADMIN_ID = config.get('admin_user_id', 0)  # No default hardcoded ID

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
attempts = {"start": {}, "stop": {}}  # Track attempts per user
MAX_ATTEMPTS = 3
ATTEMPT_RESET_TIME = 86400  # 24 hours in seconds
# Global variable for server control view
server_control_view = None

import socket
import sys

# ... (imports)

def enforce_single_instance():
    """Ensure only one instance of the bot is running by binding to a dedicated port."""
    try:
        # Create a socket with a unique port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 64209))  # Arbitrary high port
        # Keep the socket open until program exit
        return s
    except socket.error:
        print("\n\n⛔ FATAL ERROR: ANOTHER INSTANCE OF THE BOT IS ALREADY RUNNING!")
        print("Please close all other Python windows/terminals and try again.")
        print("Exiting in 5 seconds...")
        import time
        time.sleep(5)
        sys.exit(1)

# Hold the socket object globally so it doesn't get garbage collected/closed
instance_lock = enforce_single_instance()

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'✅ Connected to server: {GUILD_ID}')
    print(f'✅ Bot connected and ready!')
    # Initialize and add the persistent view for server controls
    global server_control_view
    server_control_view = ServerControlView()
    bot.add_view(server_control_view)
    
    print(f'✅ Commands will be available in guild: {GUILD_ID}')
    
    # Set bot status
    await bot.change_presence(activity=nextcord.Game(name="/palhelp"))
    
    # Force sync commands
    try:
        print("⏳ Syncing commands...")
        await bot.sync_all_application_commands()
        print('✅ All slash commands synced successfully!')
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    
    asyncio.create_task(monitor_system_ram())
    asyncio.create_task(auto_restart())  # Start auto-restart
    asyncio.create_task(scheduled_shutdown())
    asyncio.create_task(scheduled_startup())
    asyncio.create_task(reset_attempts())
    asyncio.create_task(tail_palguard_logs()) # Start Game -> Discord cross-chat
    asyncio.create_task(monitor_players()) # Start Player Join/Leave notifications

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
        global ALLOWED_CHANNEL_ID
        ALLOWED_CHANNEL_ID = admin_channel.id
        changes.append(f"Admin Channel -> {admin_channel.mention}")
    
    if status_channel:
        config.set('status_channel_id', status_channel.id)
        global STATUS_CHANNEL_ID
        STATUS_CHANNEL_ID = status_channel.id
        changes.append(f"Status Channel -> {status_channel.mention}")

    if ram_channel:
        config.set('ram_usage_channel_id', ram_channel.id)
        global RAM_USAGE_CHANNEL_ID
        RAM_USAGE_CHANNEL_ID = ram_channel.id
        changes.append(f"RAM Channel -> {ram_channel.mention}")

    if chat_channel:
        config.set('chat_channel_id', chat_channel.id)
        changes.append(f"Chat Channel -> {chat_channel.mention}")

    if monitor_channel:
        config.set('player_monitor_channel_id', monitor_channel.id)
        global PLAYER_MONITOR_CHANNEL_ID
        PLAYER_MONITOR_CHANNEL_ID = monitor_channel.id
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
        global SERVER_DIRECTORY
        SERVER_DIRECTORY = server_dir
        changes.append(f"Server Directory: `{server_dir}`")
    
    if startup_script:
        config.set('startup_script', startup_script)
        global STARTUP_SCRIPT
        STARTUP_SCRIPT = startup_script
        changes.append(f"Startup Script: `{startup_script}`")

    if shutdown_time:
        config.set('shutdown_time', shutdown_time)
        global SHUTDOWN_TIME
        SHUTDOWN_TIME = shutdown_time
        changes.append(f"Shutdown Time: `{shutdown_time}`")

    if startup_time:
        config.set('startup_time', startup_time)
        global STARTUP_TIME
        STARTUP_TIME = startup_time
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
        global ADMIN_ID
        ADMIN_ID = admin_user.id
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
        embed = nextcord.Embed(
            title="Player List Error",
            description="Could not retrieve player list from server.",
            color=0xFF0000
        )
    
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
        embed = nextcord.Embed(
            title="Server Info Error",
            description="Could not retrieve server information from API.",
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
        "**/saveworld** - Manually save the world state (Admin only)"
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
    await stop_server()
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
    if is_server_running():
        return await ctx.send("✅ Server is already running!")
    await start_server()
    await ctx.send(f"✅ Server startup initiated. (Attempts left: {MAX_ATTEMPTS - attempts['start'][ctx.author.id]}/{MAX_ATTEMPTS})")

def is_allowed_channel(ctx):
    return ctx.channel and ctx.channel.id == ALLOWED_CHANNEL_ID

def is_server_running():
    server_directory = config.get('server_directory')
    startup_script = config.get('startup_script')
    
    # Normalize path for comparison
    if server_directory:
        server_directory = os.path.normpath(server_directory.lower())

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            # Check CWD (Current Working Directory)
            try:
                proc_cwd = os.path.normpath(proc.cwd().lower()) if proc.cwd() else ""
                if server_directory and server_directory in proc_cwd:
                     return True
            except (psutil.AccessDenied, FileNotFoundError):
                pass
            
            # Check cmdline for startup script
            if proc.info['cmdline'] and startup_script:
                cmdline = " ".join(proc.info['cmdline']).lower()
                if startup_script.lower() in cmdline:
                    return True

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

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
            timestamp=datetime.datetime.utcnow()
        )
        await channel.send(embed=embed)

async def auto_restart():
    """Periodically restarts the server based on the configured interval"""
    while True:
        # Get latest interval from config in case it was changed
        interval = config.get('restart_interval', 10800)
        await asyncio.sleep(interval)
        
        global restart_enabled
        if restart_enabled:
            # Check if server is actually running first
            # We don't want to restart if it's already offline (e.g. during scheduled downtime)
            if not is_server_running():
                print("⏭️ Auto-Restart Skipped: Server is currently offline.")
                continue

            print(f"⏰ Auto-Restart Triggered (Interval: {interval}s)")
            
            # 📢 Pre-restart Announcements
            # Get announcement times from config (comma-separated minutes, e.g., "30,10,5,1")
            announcements_str = config.get('restart_announcements', '30,10,5,1')
            try:
                # Convert to sorted list of seconds in descending order
                announce_times = sorted([int(m.strip()) * 60 for m in announcements_str.split(',') if m.strip().isdigit()], reverse=True)
            except:
                announce_times = [1800, 600, 300, 60] # Default fallback

            # Notify admin channel about the start of the countdown
            allowed_channel_id = config.get('allowed_channel_id', 0)
            channel = bot.get_channel(allowed_channel_id)
            if channel:
                await channel.send(f"🔄 **Auto-Restart:** Countdown started. Server will restart in {max(announce_times)//60} minutes.")

            # Run countdown
            announce_times.sort(reverse=True)
            
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
            
            await stop_server()
            await asyncio.sleep(10)  # Wait for processes to fully terminate
            await start_server()


async def scheduled_shutdown():
    last_triggered_date = None
    while True:
        now = datetime.datetime.now()
        shutdown_str = config.get('shutdown_time', '05:00')
        
        try:
            h, m = map(int, shutdown_str.split(':'))
            # Check if it's currently the target time and we haven't triggered today
            if now.hour == h and now.minute == m and last_triggered_date != now.date():
                print(f"⏰ Scheduled Shutdown Triggered: {shutdown_str}")
                await stop_server()
                last_triggered_date = now.date()
        except Exception as e:
            print(f"Error in scheduled_shutdown: {e}")
            
        await asyncio.sleep(30) # Check every 30 seconds

async def scheduled_startup():
    last_triggered_date = None
    while True:
        now = datetime.datetime.now()
        startup_str = config.get('startup_time', '10:00')
        
        try:
            h, m = map(int, startup_str.split(':'))
            # Check if it's currently the target time and we haven't triggered today
            if now.hour == h and now.minute == m and last_triggered_date != now.date():
                print(f"⏰ Scheduled Startup Triggered: {startup_str}")
                await start_server()
                last_triggered_date = now.date()
        except Exception as e:
            print(f"Error in scheduled_startup: {e}")
            
        await asyncio.sleep(30) # Check every 30 seconds

async def stop_server():
    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/IM", "PalServer.exe", "/T"], shell=True)
        else:
            subprocess.run(["pkill", "-f", "PalServer"], shell=True)
        
        embed = nextcord.Embed(title="paltastic", description="🔴 **OFFLINE**\nPalworld", color=0xFF0000)
        embed.set_footer(text="powered by Paltastic")
        
        status_channel_id = config.get('status_channel_id', 0)
        channel = bot.get_channel(status_channel_id)
        if channel:
            await channel.send(embed=embed)
    except Exception as e:
        allowed_channel_id = config.get('allowed_channel_id', 0)
        channel = bot.get_channel(allowed_channel_id)
        if channel:
            await channel.send(f"❌ Failed to stop the server: {e}")

async def start_server():
    global server_starter
    try:
        startup_script = config.get('startup_script', '')
        server_directory = config.get('server_directory', '')
        
        if os.name == 'nt':
            subprocess.Popen(["cmd.exe", "/c", startup_script], cwd=server_directory, shell=True)
        else:
            await asyncio.create_subprocess_exec("bash", startup_script, cwd=server_directory)
        
        server_starter = "Scheduled Task"
        embed = nextcord.Embed(title="paltastic", description="🟢 **ONLINE**\nPalworld", color=0x00FF00)
        embed.set_footer(text="powered by Paltastic")
        
        status_channel_id = config.get('status_channel_id', 0)
        channel = bot.get_channel(status_channel_id)
        if channel:
            await channel.send(embed=embed)
    except Exception as e:
        allowed_channel_id = config.get('allowed_channel_id', 0)
        channel = bot.get_channel(allowed_channel_id)
        if channel:
            await channel.send(f"❌ Failed to start the server: {e}")



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

bot.run(TOKEN)
