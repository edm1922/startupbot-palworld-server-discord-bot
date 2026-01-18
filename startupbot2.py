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
AUTHORIZED_USER_ID = 692030849646067765

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
requests = {}  # Store pending requests

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'✅ Connected to server: {GUILD_ID}')
    asyncio.create_task(monitor_system_ram())

def is_allowed_channel(ctx):
    return ctx.channel and ctx.channel.id == ALLOWED_CHANNEL_ID

def is_server_running():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'PalServer.exe' in proc.info['name']:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

async def monitor_system_ram():
    while True:
        memory = psutil.virtual_memory()
        total_memory = memory.total / (1024 ** 3)
        used_memory = memory.used / (1024 ** 3)
        memory_percent = memory.percent
        ram_channel = bot.get_channel(RAM_USAGE_CHANNEL_ID)
        if ram_channel:
            await ram_channel.send(f"💻 **System RAM Usage:** {used_memory:.2f} GB / {total_memory:.2f} GB ({memory_percent}% used)")
        await asyncio.sleep(600)

async def handle_request(ctx, action):
    if not is_allowed_channel(ctx):
        await ctx.send("❌ This command can only be used in the designated server channel.")
        return
    
    request_msg = await ctx.send(f"<@{AUTHORIZED_USER_ID}>, {ctx.author.mention} has requested to {action} the server. React with ✅ to approve or ❌ to deny.")
    requests[request_msg.id] = (ctx, action)
    await request_msg.add_reaction("✅")
    await request_msg.add_reaction("❌")

@bot.event
async def on_reaction_add(reaction, user):
    if user.id != AUTHORIZED_USER_ID:
        return
    
    message_id = reaction.message.id
    if message_id in requests:
        ctx, action = requests.pop(message_id)
        if reaction.emoji == "✅":
            if action == "start":
                await startserver(ctx, bypass=True)
            elif action == "stop":
                await stopserver(ctx, bypass=True)
            elif action == "restart":
                await restartserver(ctx, bypass=True)
        else:
            await ctx.send("❌ Request denied.")

@bot.command()
async def requeststart(ctx):
    await handle_request(ctx, "start")

@bot.command()
async def requeststop(ctx):
    await handle_request(ctx, "stop")

@bot.command()
async def requestrestart(ctx):
    await handle_request(ctx, "restart")

async def startserver(ctx, bypass=False):
    global server_starter
    if is_server_running():
        await ctx.send("⚠️ Server is already running.")
        return
    
    await ctx.send(f"🚀 Starting the Palworld server using `{STARTUP_SCRIPT}`...")
    
    try:
        if os.name == 'nt':
            subprocess.Popen(["cmd.exe", "/c", STARTUP_SCRIPT], cwd=SERVER_DIRECTORY, shell=True)
        else:
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

async def stopserver(ctx, bypass=False):
    if not is_server_running():
        await ctx.send("⚠️ The server is not currently running.")
        return

    await ctx.send("🛑 Stopping the server in **30 seconds**...")
    await asyncio.sleep(30)

    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/IM", "PalServer.exe", "/T"], shell=True)
        else:
            subprocess.run(["pkill", "-f", "PalServer"], shell=True)

        embed = nextcord.Embed(title="paltastic", description="🔴 **STOPPED**\nPalworld", color=0xFF0000)
        embed.set_footer(text="powered by Paltastic")
        await ctx.send(embed=embed)
        channel = bot.get_channel(STATUS_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Failed to stop the server: {e}")

async def restartserver(ctx, bypass=False):
    if not is_server_running():
        await ctx.send("⚠️ The server is not currently running. Starting it now...")
        await startserver(ctx, bypass=True)
        return
    
    await ctx.send("🔄 Restarting the server now...")
    await stopserver(ctx, bypass=True)
    await asyncio.sleep(10)
    await startserver(ctx, bypass=True)

bot.run(TOKEN)