import nextcord
from nextcord.ext import commands
import sys
import os
import asyncio
import aiohttp
import logging
from utils.config_manager import config
from utils.bot_utils import load_cogs, enforce_single_instance
from utils.error_handler import setup_logging
from utils.rest_api import rest_api
from cogs.views import ServerControlView
from cogs.shop_system import UnifiedShopView, ShopView
from cogs.skin_shop import UnifiedSkinShopView
from cogs.live_stats import LiveStatsDisplay
from cogs.giveaway import GiveawayJoinView, GiveawayClaimView
from cogs.event_system import EventView

from utils.console_utils import disable_quick_edit

# 1. Setup Logging
setup_logging()

# 2. Disable QuickEdit (Prevents freezing) and Enforce Single Instance
disable_quick_edit()
enforce_single_instance(64210)

# 3. Bot Initialization
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Global variables/State attached to bot
bot.http_session = None
live_stats = LiveStatsDisplay(bot)

@bot.event
async def on_ready():
    logging.info(f"✨ Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Initialize HTTP Session
    if bot.http_session is None:
        bot.http_session = aiohttp.ClientSession()
        await rest_api.initialize()
    
    # Register Persistent Views
    bot.add_view(ServerControlView())
    bot.add_view(UnifiedShopView(bot))
    bot.add_view(UnifiedSkinShopView(bot))
    bot.add_view(ShopView(bot))
    bot.add_view(GiveawayJoinView())
    bot.add_view(GiveawayClaimView())
    bot.add_view(EventView())
    
    await bot.change_presence(activity=nextcord.Game(name="/palhelp"))
    
    # Start Live Stats Loop
    if live_stats:
        bot.loop.create_task(live_stats.start_auto_update())
        
    logging.info("🚀 Bot is ready and persistent views are active!")

@bot.command(name="sync")
async def sync_commands(ctx, force: str = None):
    """Manually sync slash commands to this server (Faster & Reliable)"""
    admin_id = config.get('admin_user_id', 0)
    is_admin = (ctx.author.id == admin_id) or (hasattr(ctx.author, 'guild_permissions') and ctx.author.guild_permissions.administrator)
    
    if not is_admin:
        return

    msg = await ctx.send("🔄 **SYNCING COMMANDS...** (Preaching to Discord)")
    try:
        if force == "global":
            # ONLY use this if commands are broken globally
            await ctx.send("🧹 Clearing global cache... (Slow)")
            await bot.sync_all_application_commands()
            await msg.edit(content="✅ **GLOBAL SYNC COMPLETE.** Discord might take 1 hour to update globally.")
        else:
            # Sync to the current guild (IMMEDIATE)
            if ctx.guild:
                # This rolls over all registered global commands to the guild instantly
                await bot.sync_application_commands(guild_id=ctx.guild.id)
                await msg.edit(content=f"✅ **GUILD SYNC COMPLETE!**\nServer: `{ctx.guild.name}`\n*Commands should appear in the / list instantly.*")
            else:
                await msg.edit(content="❌ Run this inside a server to sync guild commands.")
                
    except Exception as e:
        await msg.edit(content=f"❌ Sync failed: {e}")
        if "429" in str(e):
            await ctx.send("⚠️ **RATE LIMITED.** Please wait 5 minutes before trying again.")

# 4. Load Extensions
load_cogs(bot)

# 5. Run Bot
if __name__ == "__main__":
    token = config.get_discord_token()
    if not token:
        logging.critical("❌ No Discord token found in configuration!")
        sys.exit(1)
    
    try:
        bot.run(token)
    except Exception as e:
        logging.critical(f"❌ Bot failed to start: {e}")
