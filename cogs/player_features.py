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
        is_admin = interaction.user.guild_permissions.administrator or interaction.user.id == config.get('admin_user_id', 0)
        
        if is_admin:
            embed = nextcord.Embed(title="🛠️ Admin Command Center", color=0xe74c3c)
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
            embed.add_field(name="⚙️ System & Config", value=(
                "**/config** - Open admin dashboard\n"
                "**/setup_channels** - Configure bot channels\n"
                "**/server_controls** - Start/Stop/Restart server\n"
                "**/saveworld** - Force world save\n"
                "**/test_give_item** - Test RCON delivery"
            ), inline=False)
            
            embed.add_field(name="🎰 Gambling Admin", value=(
                "**/gamble_admin setup_wheel** - Post wheel UI\n"
                "**/gamble_admin add_grand_prize** - Add prize to wheel\n"
                "**/gamble_admin sync_templates** - Bulk import from folder\n"
                "**/gamble_admin manage_rewards** - Edit weights & view stats\n"
                "**/gamble_admin purge** - Clear channel history"
            ), inline=False)
            
            embed.add_field(name="📦 Systems Admin", value=(
                "**/chest setup_ui** - Spawn Mystery Room UI\n"
                "**/chest admin configure** - Edit roll cost/rates\n"
                "**/chest admin add_reward** - Add item to chest\n"
                "**/kit_admin add_item** - Create or edit Kits\n"
                "**/kit_admin give** - Send Kit to player via RCON\n"
                "**/pal_admin import_folder** - Bulk import Pal JSONs"
            ), inline=False)

            embed.add_field(name="🎨 Skin Shop Admin", value=(
                "**/skin_admin sync** - Auto-scan folder for skins\n"
                "**/skin_admin update** - Edit name, price, or image\n"
                "**/skin_admin setup_shop** - Post shop UI to channel"
            ), inline=False)
            
            embed.add_field(name="🎁 Economy & Grants", value=(
                "**/paldog_admin give_paldogs** - Gift PALDOGS to a player\n"
                "**/paldog_admin grant_reward** - Grant items/Pals to inventory\n"
                "**/giveaway_admin create** - Start new giveaway\n"
                "**/giveaway_admin reroll** - Draw new winner"
            ), inline=False)
            
            embed.set_footer(text="🛠️ Use /palhelp as a non-admin to see player commands.")
        else:
            embed = nextcord.Embed(title="🤖 Palworld Bot - Command Center", color=0x3498db)
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            # Player Features
            player_cmds = (
                "**/palhelp** - Show this menu\n"
                "**/link [steamid]** - Link your account (Required)\n"
                "**/profile [@user]** - View stats, rank, & level\n"
                "**/balance** - Check your PALDOGS & EXP\n"
                "**/give_paldogs @user [amount]** - Send money to others"
            )
            embed.add_field(name="👤 Player Commands", value=player_cmds, inline=False)

            # Rewards & Events
            rewards_cmds = (
                "**/inventory** - Claim won Pals & Items\n"
                "**/kit view [name]** - Browse available kits\n"
                "**/skinshop** - Browse & buy Pal skins\n"
                "**/giveaway** - Active giveaways"
            )
            embed.add_field(name="🎁 Rewards & Events", value=rewards_cmds, inline=False)

            # Server Info
            server_cmds = (
                "**/players** - See who's online\n"
                "**/serverinfo** - Server status & information\n"
                "**/nextrestart** - Time until auto-restart"
            )
            embed.add_field(name="🖥️ Server Info", value=server_cmds, inline=False)

            embed.set_footer(text="💡 Earn PALDOGS by playing! Contact an admin for help.")
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @nextcord.slash_command(
        description="Link your Discord account to your SteamID",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
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

    @nextcord.slash_command(
        description="Open Shop",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
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

    @nextcord.slash_command(name="give_paldogs", description="Give PALDOGS to another player")
    async def give_paldogs(self, interaction: nextcord.Interaction, user: nextcord.Member, amount: int):
        # 1. Validation
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be greater than 0.", ephemeral=True)
            return
        
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You cannot give PALDOGS to yourself.", ephemeral=True)
            return

        # 2. Get DB stats for both
        sender_stats = await db.get_player_by_discord(interaction.user.id)
        if not sender_stats:
            await interaction.response.send_message("❌ You must link your account first! Use `/link`.", ephemeral=True)
            return

        receiver_stats = await db.get_player_by_discord(user.id)
        if not receiver_stats:
            await interaction.response.send_message(f"❌ {user.display_name} has not linked their account yet.", ephemeral=True)
            return

        # 3. Transfer
        success = await db.transfer_paldogs(sender_stats['steam_id'], receiver_stats['steam_id'], amount)
        
        if success:
            embed = nextcord.Embed(title="💸 Transfer Successful", color=0x2ecc71)
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name="Sender", value=interaction.user.mention, inline=True)
            embed.add_field(name="Recipient", value=user.mention, inline=True)
            embed.add_field(name="Amount", value=f"**{amount:,} PALDOGS**", inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Transaction failed. Insufficient funds or processing error.", ephemeral=True)

def setup(bot):
    bot.add_cog(PlayerFeatures(bot))
