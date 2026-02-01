import nextcord
from nextcord.ext import commands
from utils.config_manager import config
from utils.database import db
from cogs.shop_system import ShopView, create_shop_embed, create_public_shop_embed, UnifiedShopView

class PlayerFeatures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command(name="palhelp", description="Show all available commands")
    async def help_command(self, interaction: nextcord.Interaction):
        embed = nextcord.Embed(title="🤖 Bot Commands Help", color=0x00ADD8)
        slash_cmds = (
            "**/palhelp** - Show this help message\n"
            "**/players** - Show current players online\n"
            "**/serverinfo** - Show detailed server information\n"
            "**/profile** - View your stats, rank, level and balance\n"
            "**/balance** - Quickly check your PALDOGS & EXP\n"
            "**/shop** - Open the PALDOGS Exchange shop\n"
            "**/gamble roulette** - Bet to win items!\n"
            "**/inventory** - Claim your winnings\n"
            "**/link** - Link your account to SteamID\n"
            "**/server_controls** - Admin control panel\n"
            "**/config** - Admin configuration"
        )
        embed.add_field(name="🚀 Commands", value=slash_cmds, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @nextcord.slash_command(description="Link your Discord account to your SteamID")
    async def link(self, interaction: nextcord.Interaction, steam_id: str):
        clean_id = steam_id.strip()
        if not clean_id.startswith("steam_") and clean_id.isdigit() and len(clean_id) == 17:
            clean_id = f"steam_{clean_id}"
        
        stats = await db.get_player_stats(clean_id)
        if not stats:
            await interaction.response.send_message("❌ Player not found in database. Log in first!", ephemeral=True)
            return

        await db.link_account(clean_id, interaction.user.id)
        await interaction.response.send_message(f"✅ Linked to **{stats['player_name']}** (`{clean_id}`)", ephemeral=True)

    @nextcord.slash_command(description="Check your profile")
    async def profile(self, interaction: nextcord.Interaction, user: nextcord.Member = None):
        target_user = user or interaction.user
        stats = await db.get_player_by_discord(target_user.id)
        
        if not stats:
            await interaction.response.send_message("❌ Account not linked.", ephemeral=True)
            return

        pm = stats.get('palmarks', 0)
        rank = stats.get('rank', 'Trainer')
        level = stats.get('level', 1)
        exp = stats.get('experience', 0)
        announcer_id = stats.get('active_announcer', 'default')
        from cogs.rank_system import rank_system
        announcer_name = rank_system.announcer_packs.get(announcer_id, {}).get('name', 'Default')
        
        # Get progress
        progress = await rank_system.get_progress_to_next_rank(stats['steam_id'])
        
        embed = nextcord.Embed(title=f"👤 {stats['player_name']}'s Profile", color=rank_system.get_rank_info(rank).get('color', 0x00ADD8))
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="💰 PALDOGS", value=f"**{pm:,}**", inline=True)
        embed.add_field(name="✨ Level", value=f"**Lv.{level}**", inline=True)
        embed.add_field(name="🏆 Rank", value=f"**{rank}**", inline=True)
        embed.add_field(name="📣 Announcer", value=f"**{announcer_name}**", inline=True)
        
        if progress:
            percent = progress['percentage']
            filled = int(percent / 10)
            bar = "🟩" * filled + "⬛" * (10 - filled)
            embed.add_field(
                name=f"📊 Level Progress ({percent}%)", 
                value=f"{bar}\nEXP: **{exp:,}** / **{progress['required_exp']:,}**", 
                inline=False
            )
        elif progress and progress['is_max_rank']:
            embed.add_field(name="📈 Rank Status", value="⭐ **MAX RANK ACHIEVED** ⭐", inline=False)

        await interaction.response.send_message(embed=embed)

    @nextcord.slash_command(description="Check balance")
    async def balance(self, interaction: nextcord.Interaction):
        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats:
            await interaction.response.send_message("❌ Account not linked.", ephemeral=True)
            return
        embed = nextcord.Embed(title="💰 Your Balance", color=0x2ecc71)
        embed.add_field(name="PALDOGS", value=f"**{stats.get('palmarks', 0):,}**", inline=True)
        embed.add_field(name="Experience", value=f"**{stats.get('experience', 0):,} EXP** (Lv.{stats.get('level', 1)})", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @nextcord.slash_command(description="Open Shop")
    async def shop(self, interaction: nextcord.Interaction):
        shop_channel_id = config.get('shop_channel_id', 0)
        is_admin = interaction.user.guild_permissions.administrator or interaction.user.id == config.get('admin_user_id', 0)
        
        if interaction.channel_id == shop_channel_id and is_admin:
            embed = await create_public_shop_embed()
            await interaction.channel.send(embed=embed, view=UnifiedShopView(self.bot))
            await interaction.response.send_message("✅ Shop posted.", ephemeral=True)
        else:
            stats = await db.get_player_by_discord(interaction.user.id)
            if stats:
                embed = await create_shop_embed()
                await interaction.response.send_message(f"💰 Balance: **{stats.get('palmarks', 0):,} PALDOGS**", embed=embed, view=ShopView(self.bot), ephemeral=True)
            else:
                embed = await create_public_shop_embed()
                await interaction.response.send_message(embed=embed, view=UnifiedShopView(self.bot), ephemeral=True)

def setup(bot):
    bot.add_cog(PlayerFeatures(bot))
