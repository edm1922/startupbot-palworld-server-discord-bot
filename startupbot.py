import nextcord
import subprocess
import os
import asyncio
import psutil
from nextcord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve configuration values
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID"))
STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID"))
RAM_USAGE_CHANNEL_ID = int(os.getenv("RAM_USAGE_CHANNEL_ID"))
RESTART_INTERVAL = int(os.getenv("RESTART_INTERVAL", 10800))  # Default: 3 hours
SERVER_DIRECTORY = os.getenv("SERVER_DIRECTORY")
STARTUP_SCRIPT = os.getenv("STARTUP_SCRIPT")

if not TOKEN:
    raise ValueError("❌ DISCORD_BOT_TOKEN not found! Check your .env file.")

if not SERVER_DIRECTORY or not STARTUP_SCRIPT:
    raise ValueError("❌ Server directory or startup script not found in .env file!")

# Define bot with proper intents
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

server_starter = None
restart_task = None
restart_enabled = True

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'✅ Connected to server: {GUILD_ID}')
    
    # Start monitoring RAM usage
    asyncio.create_task(monitor_system_ram())

def is_allowed_channel(ctx):
    """Check if the command is used in the allowed channel."""
    return ctx.channel and ctx.channel.id == ALLOWED_CHANNEL_ID

def is_server_running():
    """Check if the Palworld server is running."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'PalServer.exe' in proc.info['name']:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

async def monitor_system_ram():
    """Monitor RAM usage and send updates every 10 minutes."""
    while True:
        memory = psutil.virtual_memory()
        total_memory = memory.total / (1024 ** 3)
        used_memory = memory.used / (1024 ** 3)
        memory_percent = memory.percent

        ram_channel = bot.get_channel(RAM_USAGE_CHANNEL_ID)
        if ram_channel:
            await ram_channel.send(f"💻 **System RAM Usage:** {used_memory:.2f} GB / {total_memory:.2f} GB ({memory_percent}% used)")
        else:
            print("⚠️ RAM usage channel not found!")
        await asyncio.sleep(600)  # Check every 10 minutes

async def auto_restart():
    """Automatically restart the server at the set interval."""
    global restart_task
    while restart_enabled:
        await asyncio.sleep(RESTART_INTERVAL)
        await restartserver(None)

@bot.command()
async def setrestartinterval(ctx, hours: int):
    """Set the restart interval (1-24 hours)."""
    global RESTART_INTERVAL, restart_task
    if not is_allowed_channel(ctx):
        await ctx.send("❌ This command can only be used in the designated server channel.")
        return

    if hours < 1 or hours > 24:
        await ctx.send("⚠️ Please set an interval between 1 and 24 hours.")
        return

    RESTART_INTERVAL = hours * 3600
    await ctx.send(f"✅ Restart interval set to {hours} hours.")
    
    if restart_task is None or restart_task.done():
        restart_task = asyncio.create_task(auto_restart())

@bot.command()
async def togglerestart(ctx, mode: str):
    """Enable or disable automatic server restarts."""
    global restart_enabled, restart_task
    if not is_allowed_channel(ctx):
        await ctx.send("❌ This command can only be used in the designated server channel.")
        return
    
    if mode.lower() == "on":
        restart_enabled = True
        await ctx.send("✅ Automatic server restarts **enabled**.")
        if restart_task is None or restart_task.done():
            restart_task = asyncio.create_task(auto_restart())
    elif mode.lower() == "off":
        restart_enabled = False
        await ctx.send("🛑 Automatic server restarts **disabled**.")
    else:
        await ctx.send("⚠️ Invalid mode! Use `!togglerestart on` or `!togglerestart off`.")

@bot.command()
async def startserver(ctx):
    """Start the Palworld server."""
    if not is_allowed_channel(ctx):
        await ctx.send("❌ This command can only be used in the designated server channel.")
        return

    global server_starter
    if is_server_running():
        await ctx.send(f"⚠️ Server is already running, started by <@{server_starter}>.")
        return

    await ctx.send(f"🚀 Starting the Palworld server using `{STARTUP_SCRIPT}`...")

    try:
        if os.name == 'nt':  # Windows
            subprocess.Popen(["cmd.exe", "/c", STARTUP_SCRIPT], cwd=SERVER_DIRECTORY, shell=True)
        else:  # Linux
            await asyncio.create_subprocess_exec("bash", STARTUP_SCRIPT, cwd=SERVER_DIRECTORY)

        server_starter = ctx.author.id

        embed = nextcord.Embed(title="paltastic", description="🟢 **ONLINE**\nPalworld", color=0x00FF00)
        embed.set_footer(text="powered by Paltastic")

        await ctx.send(embed=embed)

        channel = bot.get_channel(STATUS_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Failed to start the server: {e}")

@bot.command()
async def stopserver(ctx):
    """Stop the Palworld server."""
    if not is_allowed_channel(ctx):
        await ctx.send("❌ This command can only be used in the designated server channel.")
        return

    if not is_server_running():
        await ctx.send("⚠️ The server is not currently running.")
        return

    await ctx.send("🛑 Stopping the server in **30 seconds**...")

    global restart_enabled
    restart_enabled = False

    await asyncio.sleep(30)

    try:
        if os.name == 'nt':  # Windows
            subprocess.run(["taskkill", "/F", "/IM", "PalServer.exe", "/T"], shell=True)
        else:  # Linux
            subprocess.run(["pkill", "-f", "PalServer"], shell=True)

        embed = nextcord.Embed(title="paltastic", description="🔴 **STOPPED**\nPalworld", color=0xFF0000)
        embed.set_footer(text="powered by Paltastic")

        await ctx.send(embed=embed)

        channel = bot.get_channel(STATUS_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Failed to stop the server: {e}")

@bot.command()
async def restartserver(ctx=None):
    """Restart the server (manual or automatic)."""
    if ctx and not is_allowed_channel(ctx):
        await ctx.send("❌ This command can only be used in the designated server channel.")
        return

    if not is_server_running():
        if ctx:
            await ctx.send("⚠️ The server is not currently running. Starting it now...")
        await startserver(ctx)
        return

    if ctx:
        await ctx.send("🔄 Restarting the server now...")
    await stopserver(ctx)
    await asyncio.sleep(10)
    await startserver(ctx)

@bot.command(name="bothelp")
async def bothelp(ctx):
    """Display available commands."""
    help_text = """
    **Available Commands:**
    - `!startserver` → Start the Palworld server.
    - `!stopserver` → Stop the Palworld server.
    - `!restartserver` → Restart the server.
    - `!setrestartinterval <hours>` → Set auto-restart interval (1-24 hours).
    - `!togglerestart on/off` → Enable/Disable automatic restarts.
    - `!bothelp` → Show this help menu.
    """
    await ctx.send(help_text)

bot.run(TOKEN)
