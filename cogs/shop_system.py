import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button, Select
from nextcord import Interaction
from utils.database import db
from cogs.kit_system import kit_system
from utils.rcon_utility import rcon_util
from cogs.rank_system import rank_system

class ShopView(View):
    """Interactive shop interface for buying kits with PALDOGS"""
    
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.setup_items()
    
    def setup_items(self):
        self.clear_items()
        
        # Get all kits that have a price > 0 or are available for sale
        kits = kit_system.kits
        if not kits:
            return
            
        options = []
        for name, data in kits.items():
            price = data.get('price', 0)
            desc = data.get('description', 'No description')
            options.append(nextcord.SelectOption(
                label=f"{name.capitalize()} - {price:,} PALDOGS",
                description=desc[:100],
                value=name
            ))
            
        if options:
            select = Select(
                placeholder="Select a kit to purchase...",
                options=options,
                custom_id="shop_kit_select"
            )
            select.callback = self.purchase_callback
            self.add_item(select)
            
        # --- Announcer Packs ---
        announcers = rank_system.announcer_packs
        announcer_options = []
        for aid, data in announcers.items():
            if aid == 'default': continue
            price = data.get('price', 0)
            announcer_options.append(nextcord.SelectOption(
                label=f"📣 {data['name']} - {price:,} PALDOGS",
                description=data.get('description', 'New entrance sound!'),
                value=f"announcer:{aid}"
            ))
        
        if announcer_options:
            a_select = Select(
                placeholder="Select an Announcer Pack...",
                options=announcer_options,
                custom_id="shop_announcer_select"
            )
            a_select.callback = self.announcer_callback
            self.add_item(a_select)
            
        # Add a refresh button
        refresh_btn = Button(label="Refresh Menu", style=nextcord.ButtonStyle.secondary, emoji="🔄", custom_id="shop_refresh")
        refresh_btn.callback = self.refresh_callback
        self.add_item(refresh_btn)

    async def refresh_callback(self, interaction: Interaction):
        kit_system.load_kits()
        self.setup_items()
        embed = await create_shop_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def purchase_callback(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        
        kit_name = interaction.data['values'][0]
        kit_data = kit_system.get_kit(kit_name)
        
        if not kit_data:
            await interaction.followup.send("❌ This kit no longer exists.", ephemeral=True)
            return
            
        price = kit_data.get('price', 0)
        
        # 1. Get player steam_id linked to this discord_id
        # We need a way to look up steam_id by discord_id
        player_stats = await self.get_player_by_discord(interaction.user.id)
        
        if not player_stats:
            await interaction.followup.send(
                "❌ **Registration Required!**\n"
                "You need to link your account before you can buy items. Please use the **🛒 Browse & Buy** button in the main shop message to register.", 
                ephemeral=True
            )
            return
            
        steam_id = player_stats['steam_id']
        current_palmarks = player_stats.get('palmarks', 0)
        
        if current_palmarks < price:
            await interaction.followup.send(
                f"❌ **Insufficient PALDOGS!**\n"
                f"Required: **{price:,} PALDOGS**\n"
                f"You have: **{current_palmarks:,} PALDOGS**", 
                ephemeral=True
            )
            return
            
        # 2. Confirm purchase
        confirm_view = PurchaseConfirmView(kit_name, price, steam_id, self.bot)
        await interaction.followup.send(
            f"🛒 **Confirm Purchase**\n"
            f"Kit: **{kit_name.capitalize()}**\n"
            f"Price: **{price:,} PALDOGS**\n"
            f"Recipient: **{player_stats['player_name']}** ({steam_id})",
            view=confirm_view,
            ephemeral=True
        )

    async def get_player_by_discord(self, discord_id: int):
        """Helper to find player by discord ID"""
        return await db.get_player_by_discord(discord_id)

    async def announcer_callback(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        
        aid = interaction.data['values'][0].split(':')[1]
        pack = rank_system.announcer_packs.get(aid)
        
        if not pack:
            await interaction.followup.send("❌ Internal error: Pack not found.", ephemeral=True)
            return
            
        player_stats = await self.get_player_by_discord(interaction.user.id)
        if not player_stats:
            await interaction.followup.send("❌ Please register via the main shop menu first!", ephemeral=True)
            return
            
        confirm_view = AnnouncerConfirmView(aid, pack, player_stats['steam_id'], self.bot)
        
        # Format the test messages
        sample_join = pack['join_template'].format(player=player_stats['player_name'])
        sample_rank = pack['rank_template'].format(player=player_stats['player_name'], rank="Champion")
        
        embed = nextcord.Embed(
            title=f"📣 PREVIEW: {pack['name']}",
            description=(
                f"**Price:** {pack['price']:,} PALDOGS\n\n"
                f"**Arrival Line:** `{sample_join}`\n"
                f"**Rank Up Line:** `{sample_rank}`\n\n"
                "*Would you like to purchase and equip this pack?*"
            ),
            color=0x00A8FF
        )
        
        await interaction.followup.send(embed=embed, view=confirm_view, ephemeral=True)

class PurchaseConfirmView(View):
    def __init__(self, kit_name, price, steam_id, bot):
        super().__init__(timeout=60)
        self.kit_name = kit_name
        self.price = price
        self.steam_id = steam_id
        self.bot = bot

    @nextcord.ui.button(label="Confirm & Buy", style=nextcord.ButtonStyle.success, emoji="✅")
    async def confirm_btn(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        
        # 1. Verification Checks
        from utils.rest_api import rest_api
        
        # Check if player is online (REQUIRED for RCON give)
        online_players = await rest_api.get_player_list()
        is_online = False
        if online_players:
            for p in online_players.get('players', []):
                # Clean IDs for comparison
                p_uid = str(p.get('userId', '')).replace('steam_', '')
                target_uid = str(self.steam_id).replace('steam_', '')
                if p_uid == target_uid:
                    is_online = True
                    break
        
        if not is_online:
            await interaction.edit_original_message(
                content="❌ **Purchase Failed: You are not online!**\n"
                        "You must be logged into the Palworld server to receive items.", 
                view=None
            )
            return

        # Double check balance
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT palmarks FROM players WHERE steam_id = ?", (self.steam_id,))
        result = cursor.fetchone()
        
        if not result or result['palmarks'] < self.price:
            await interaction.edit_original_message(content="❌ **Purchase Failed: Insufficient balance.**", view=None)
            conn.close()
            return
            
        # 2. Process Transaction
        new_balance = result['palmarks'] - self.price
        cursor.execute("UPDATE players SET palmarks = ? WHERE steam_id = ?", (new_balance, self.steam_id))
        
        # Record history
        cursor.execute(
            "INSERT INTO reward_history (steam_id, reward_type, amount, description) VALUES (?, ?, ?, ?)",
            (self.steam_id, 'purchase', -self.price, f"Bought kit: {self.kit_name}")
        )
        
        conn.commit()
        conn.close()
        
        # 3. Deliver Items via RCON
        kit_data = kit_system.get_kit(self.kit_name)
        items_report = []
        all_success = True
        
        if rcon_util.is_configured():
            for item_id, amount in kit_data['items'].items():
                success, resp = await rcon_util.give_item(self.steam_id, item_id, amount)
                if success:
                    items_report.append(f"✅ {amount}x **{item_id}**")
                else:
                    items_report.append(f"❌ {amount}x **{item_id}** ({resp})")
                    all_success = False
        
        # 4. Final Response
        if all_success:
            msg = f"✨ **Kit Purchased!**\nSuccessfully delivered **{self.kit_name.capitalize()}** to your inventory.\n"
            msg += "\n".join(items_report)
            msg += f"\n\n💰 New Balance: **{new_balance:,} PALDOGS**"
        else:
            msg = f"⚠️ **Partial Delivery!**\nSome items could not be sent. Please check your inventory.\n"
            msg += "\n".join(items_report)
            msg += f"\n\n*If you didn't receive your items, the Item IDs in the kit might be incorrect.*"
            
        await interaction.edit_original_message(content=msg, view=None)
        
        # Log to shop channel if configured
        # (This could be a public announcement too)

    @nextcord.ui.button(label="Cancel", style=nextcord.ButtonStyle.secondary, emoji="❌")
    async def cancel_btn(self, button: Button, interaction: Interaction):
        await interaction.response.edit_message(content="❌ Purchase cancelled.", view=None)

class AnnouncerConfirmView(View):
    def __init__(self, aid, pack, steam_id, bot):
        super().__init__(timeout=60)
        self.aid = aid
        self.pack = pack
        self.steam_id = steam_id
        self.bot = bot

    @nextcord.ui.button(label="Purchase & Equip", style=nextcord.ButtonStyle.success, emoji="💰")
    async def buy_btn(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        
        stats = await db.get_player_stats(self.steam_id)
        if not stats or stats.get('palmarks', 0) < self.pack['price']:
            await interaction.edit_original_message(content="❌ **Insufficient Balance!**", view=None)
            return
            
        # Deduct and equip
        await db.add_palmarks(self.steam_id, -self.pack['price'], f"Bought Announcer: {self.pack['name']}")
        await db.update_active_announcer(self.steam_id, self.aid)
        
        await interaction.edit_original_message(
            content=f"✅ **Purchased!** You have equipped the **{self.pack['name']}**.\n"
                    f"Everyone will hear your new entrance line next time you join!", 
            view=None, embed=None
        )

    @nextcord.ui.button(label="Equip (Already Owned)", style=nextcord.ButtonStyle.secondary)
    async def equip_btn(self, button: Button, interaction: Interaction):
        # In a real system, we'd check an 'owned_announcers' table. 
        # For now, let's treat it as a purchase-to-unlock. 
        # But we'll allow equipping if they already have it active.
        await interaction.response.send_message("Feature coming soon: Permanent ownership tracking. For now, packs are one-time purchases per equip.", ephemeral=True)

    @nextcord.ui.button(label="Cancel", style=nextcord.ButtonStyle.danger)
    async def cancel_btn(self, button: Button, interaction: Interaction):
        await interaction.response.edit_message(content="❌ Preview closed.", view=None, embed=None)

async def create_shop_embed():
    """Create a premium shop embed"""
    embed = nextcord.Embed(
        title="🏪 PALDOGS EXCHANGE SHOP",
        description=(
            "Exchange your **PALDOGS** for premium item kits delivered directly to your inventory!\n\n"
            "**How to buy:**\n"
            "1. Select a kit from the dropdown menu below\n"
            "2. Confirm your purchase and items will be sent instantly\n"
            "*Note: You must be online in-game to receive items.*"
        ),
        color=0xFFD700
    )
    
    kits = kit_system.kits
    if not kits:
        embed.add_field(name="⚠️ Shop Empty", value="No kits are currently available for purchase.")
    else:
        for name, data in kits.items():
            price = data.get('price', 0)
            embed.add_field(
                name=f"📦 {name.capitalize()} - {price:,} PALDOGS",
                value=f"_{data.get('description', 'No description')}_",
                inline=False
            )
            
    embed.set_footer(text="PALDOGS Shop • Powered by Paltastic", icon_url="https://i.imgur.com/AfFp7pu.png")
    return embed

async def create_public_shop_embed():
    """Create a premium 'Store Front' embed for the shop channel"""
    embed = nextcord.Embed(
        title="🏪 PALWORLD VIRTUAL EXCHANGE",
        description=(
            "Welcome to the official server store! Use your **PALDOGS** earned from in-game activity to purchase premium kits.\n\n"
            "**Current Price List:**"
        ),
        color=0x00FFBB
    )
    
    kits = kit_system.kits
    if not kits:
        embed.add_field(name="⚠️ Shop Empty", value="Check back later for new stock!")
    else:
        # Create a professional looking table in a code block
        table_header = "📦 Kit Name          | 💰 Price    \n"
        table_divider = "-------------------|------------\n"
        table_rows = ""
        
        for name, data in kits.items():
            price = data.get('price', 0)
            # Pad strings for alignment
            name_str = name.capitalize().ljust(18)
            price_str = f"{price:,} PALDOGS".ljust(10)
            table_rows += f"{name_str} | {price_str}\n"
            
        embed.add_field(name="Menu", value=f"```\n{table_header}{table_divider}{table_rows}```", inline=False)
        
        # Add details for each kit below the table
        for name, data in kits.items():
            embed.add_field(
                name=f"🔹 {name.capitalize()}",
                value=f"*{data.get('description', 'Standard issue kit')}*",
                inline=False
            )

    # --- ADD ANNOUNCER PACKS SECTION ---
    announcers = rank_system.announcer_packs
    if announcers:
        a_table_header = "📣 Announcer Pack     | 💰 Price    \n"
        a_table_divider = "-------------------|------------\n"
        a_table_rows = ""
        
        for aid, data in announcers.items():
            if aid == 'default': continue
            price = data.get('price', 0)
            name_str = data['name'].ljust(18)
            price_str = f"{price:,} PALDOGS".ljust(10)
            a_table_rows += f"{name_str} | {price_str}\n"
            
        if a_table_rows:
            embed.add_field(name="🏆 Special: Announcer Packs", value=f"```\n{a_table_header}{a_table_divider}{a_table_rows}```", inline=False)
            
            # Show brief descriptions
            desc_lines = []
            for aid, data in announcers.items():
                if aid == 'default': continue
                desc_lines.append(f"• **{data['name']}**: _{data.get('description', 'Cool entrance line')}_")
            
            embed.add_field(name="📣 Pack Descriptions", value="\n".join(desc_lines), inline=False)

    embed.set_footer(text="🛒 Click 'Browse & Buy' to register and shop • New Announcers Available!")
    return embed

class UnifiedShopView(View):
    """Integrated view for registration and shopping"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label="🛒 Browse & Buy", style=nextcord.ButtonStyle.green, emoji="🧺", custom_id="shop_browse_btn")
    async def open_shop(self, button: Button, interaction: Interaction):
        # 1. Check if user is linked
        stats = await db.get_player_by_discord(interaction.user.id)
        
        if not stats:
            # 2. Not linked? Trigger registration modal
            await interaction.response.send_modal(RegistrationModal(self.bot))
        else:
            # 3. Linked? Show the personal shopping menu
            embed = await create_shop_embed()
            view = ShopView(self.bot)
            
            # Show balance in the message
            balance = stats.get('palmarks', 0)
            await interaction.response.send_message(
                f"👋 **Welcome back, {stats['player_name']}!**\n💰 Your Balance: **{balance:,} PALDOGS**\n🏅 Rank: **{stats['rank']}**",
                embed=embed, 
                view=view, 
                ephemeral=True
            )

    @nextcord.ui.button(label="⚙️ My Settings", style=nextcord.ButtonStyle.secondary, custom_id="shop_settings_btn")
    async def open_settings(self, button: Button, interaction: Interaction):
        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats:
            await interaction.response.send_message("❌ Please register first!", ephemeral=True)
            return
            
        announcer_name = rank_system.announcer_packs.get(stats.get('active_announcer', 'default'), {}).get('name', 'Default')
        
        embed = nextcord.Embed(title="👤 Player Profile & Settings", color=0x3498db)
        embed.add_field(name="Name", value=stats['player_name'], inline=True)
        embed.add_field(name="Rank", value=f"{stats['rank']}", inline=True)
        embed.add_field(name="Balance", value=f"{stats.get('palmarks', 0):,} PALDOGS", inline=True)
        embed.add_field(name="Active Announcer", value=announcer_name, inline=True)
        
        # Add a reset button to use default announcer
        view = View()
        reset_a = Button(label="Reset Announcer", style=nextcord.ButtonStyle.danger)
        
        async def reset_callback(inter):
            await db.update_active_announcer(stats['steam_id'], 'default')
            await inter.response.send_message("✅ Announcer reset to Default.", ephemeral=True)
            
        reset_a.callback = reset_callback
        view.add_item(reset_a)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    @nextcord.ui.button(label="🔄 Refresh Shop", style=nextcord.ButtonStyle.secondary, custom_id="shop_public_refresh")
    async def refresh_shop(self, button: Button, interaction: Interaction):
        # Only allow admins to trigger a public refresh to avoid spam, or just allow anyone but add a cooldown
        # For now, let's just make it refresh the embed
        kit_system.load_kits() # Reload from disk
        rank_system.load_announcers() # Reload from disk
        embed = await create_public_shop_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class RegistrationModal(nextcord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Register for the Store")
        self.bot = bot
        self.name_input = nextcord.ui.TextInput(
            label="What is your EXACT In-Game Name?",
            placeholder="Case-sensitive (e.g. AMEN)",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)

    async def callback(self, interaction: Interaction):
        player_name = self.name_input.value.strip()
        stats = await db.get_player_stats_by_name(player_name)
        
        if not stats:
            await interaction.response.send_message(
                f"❌ **Registration Failed!**\nCharacter '**{player_name}**' was not found in our logs.\n\n"
                "*Please login to the server and play for a few minutes before trying again!*",
                ephemeral=True
            )
            return

        # Link account
        steam_id = stats['steam_id']
        await db.link_account(steam_id, interaction.user.id)
        
        # Now show the shop
        embed = await create_shop_embed()
        view = ShopView(self.bot)
        balance = stats.get('palmarks', 0)
        
        await interaction.response.send_message(
            f"✅ **Account Linked Successfully!**\nWelcome, **{player_name}**!\n💰 Balance: **{balance:,} PALDOGS**\n*You can now browse and purchase kits below.*",
            embed=embed,
            view=view,
            ephemeral=True
        )

