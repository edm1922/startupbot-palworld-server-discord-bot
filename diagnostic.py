import asyncio
import nextcord
from nextcord.ext import commands
import os
import json
import logging
import aiohttp
import sys

# Try to set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

from utils.config_manager import config
from utils.rest_api import rest_api
from utils.database import db

# Setup logging
logging.basicConfig(level=logging.INFO)

async def run_diagnostic():
    print("========================================")
    print("       STARTUPBOT FULL DIAGNOSTIC       ")
    print("========================================")
    
    # 1. Check Configuration
    print("\n[1/5] Checking Configuration...")
    log_dir = config.get('log_directory', '')
    if not log_dir:
        print("[!] Error: log_directory is not set in config.")
    elif not os.path.exists(log_dir):
        print(f"[!] Error: log_directory '{log_dir}' does not exist.")
    else:
        print(f"[OK] Log directory exists: {log_dir}")
        logs = [f for f in os.listdir(log_dir) if f.endswith('.log')]
        print(f"[OK] Found {len(logs)} log files.")
    
    server_dir = config.get('server_directory', '')
    if not server_dir:
        print("[!] Error: server_directory is not set.")
    elif not os.path.exists(server_dir):
        print(f"[!] Error: server_directory '{server_dir}' does not exist.")
    else:
        print(f"[OK] Server directory exists: {server_dir}")

    # 2. Check Database
    print("\n[2/5] Checking Database...")
    try:
        count = await db.get_total_players_count()
        print(f"[OK] Database connected. Found {count} players.")
    except Exception as e:
        print(f"[!] Database error: {e}")

    # 3. Check API Connectivity
    print("\n[3/5] Checking REST API...")
    if rest_api.is_configured():
        try:
            await rest_api.initialize()
            info = await rest_api.get_server_info()
            if info:
                print(f"[OK] REST API connected. Server: {info.get('servername', 'Unknown')}")
            else:
                print("[!] REST API connected but returned no info (Server might be down).")
        except Exception as e:
            print(f"[!] REST API error: {e}")
    else:
        print("[-] REST API not configured.")

    # 4. Check Discord Bot
    print("\n[4/5] Checking Discord Bot...")
    token = config.get_discord_token()
    if not token:
        print("[!] Error: DISCORD_BOT_TOKEN not found in .env")
        return

    # Use a minimal client to avoid full cog loading
    intents = nextcord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        print(f"[OK] Logged in as {bot.user}")
        
        guild_id = config.get('guild_id', 0)
        guild = bot.get_guild(guild_id)
        if not guild:
            print(f"[!] Error: Bot is not in guild {guild_id}")
            # Try to fetch if not in cache
            try:
                guild = await bot.fetch_guild(guild_id)
                print(f"[OK] Fetched guild: {guild.name}")
            except:
                print(f"[!] Error: Could not fetch guild {guild_id}")
        
        if guild:
            channels_to_check = {
                'chat_channel_id': 'Chat Relay',
                'player_monitor_channel_id': 'Player Monitor',
                'status_channel_id': 'Status',
                'ram_usage_channel_id': 'RAM Usage',
                'stats_channel_id': 'Live Stats'
            }
            
            for cid_key, label in channels_to_check.items():
                cid = config.get(cid_key, 0)
                if not cid:
                    print(f"[-] {label} channel ID not set.")
                    continue
                    
                channel = bot.get_channel(cid)
                if not channel:
                    try:
                        channel = await bot.fetch_channel(cid)
                    except:
                        pass
                
                if channel:
                    perms = channel.permissions_for(guild.me)
                    print(f"[OK] Found {label} channel: #{channel.name}")
                    if not perms.send_messages:
                        print(f"   [!] Missing 'Send Messages' permission in #{channel.name}")
                    if not perms.embed_links:
                        print(f"   [!] Missing 'Embed Links' permission in #{channel.name}")
                else:
                    print(f"[!] Error: Could not find {label} channel with ID {cid}")
        
        webhook_url = config.get('chat_webhook_url', '')
        if webhook_url:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(webhook_url) as resp:
                        if resp.status == 200:
                            print("[OK] Chat Webhook URL is valid.")
                        else:
                            print(f"[!] Chat Webhook URL returned status {resp.status}")
                except Exception as e:
                    print(f"[!] Chat Webhook URL error: {e}")
        else:
            print("[-] Chat Webhook URL not set (using regular messages).")

        print("\n[5/5] Diagnostic Complete.")
        await bot.close()

    try:
        # Run bot for max 30 seconds for diagnostic
        await bot.start(token)
    except Exception as e:
        print(f"[!] Bot execution error: {e}")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
