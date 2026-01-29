import nextcord
from nextcord.ext import commands
from utils.config_manager import config
from utils.server_utils import start_server, stop_server, server_lock, is_server_running

class PrefixCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.MAX_ATTEMPTS = 3

    def is_admin(self, ctx):
        admin_id = config.get('admin_user_id', 0)
        return ctx.author.id == admin_id or (hasattr(ctx.author, 'guild_permissions') and ctx.author.guild_permissions.administrator)

    @commands.command(name="stopserver")
    async def stopserver(self, ctx):
        if not self.is_admin(ctx):
            await ctx.send("❌ Permission denied.")
            return
        async with server_lock:
            await stop_server(self.bot)
        await ctx.send("✅ Server shutdown initiated.")

    @commands.command(name="startserver")
    async def startserver(self, ctx):
        if not self.is_admin(ctx):
            await ctx.send("❌ Permission denied.")
            return
        async with server_lock:
            if await is_server_running():
                await ctx.send("✅ Server is already running!")
                return
            await start_server(self.bot)
        await ctx.send("✅ Server startup initiated.")

def setup(bot):
    bot.add_cog(PrefixCommands(bot))
