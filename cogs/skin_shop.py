import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button, Select
import os
import zipfile
import io
import logging
from utils.database import db
from cogs.skin_system_logic import skin_system

# --- PATH CONFIG ---
# INSTALLER reuse
INSTALLER_SRC = os.path.join(os.getcwd(), "data", "palskins", "install_skin.bat")
INSTRUCTIONS_SRC = os.path.join(os.getcwd(), "data", "palskins", "Instruction.txt")

async def create_public_skin_shop_embed():
    """Create the premium storefront embed for the skin shop channel"""
    embed = nextcord.Embed(
        title="🎨 PALWORLD VIRTUAL CLOSET",
        description=(
            "Upgrade your Pals with premium skins! Each purchase comes with an **Auto-Installer**.\n\n"
            "**Price List:**"
        ),
        color=0xAD1457
    )
    
    skins = skin_system.get_all_skins()
    if not skins:
        embed.add_field(name="📝 Shop Empty", value="New skins arriving soon!")
    else:
        # Table format
        header = "🎨 Skin Name          | 💰 Price    \n"
        divider = "---------------------|------------\n"
        rows = ""
        for sid, data in skins.items():
            name_str = data['name'].ljust(20)
            price_str = f"{data['price']:,} PD".ljust(10)
            rows += f"{name_str} | {price_str}\n"
        
        embed.add_field(name="Available Skins", value=f"```\n{header}{divider}{rows}```", inline=False)
        
        for sid, data in skins.items():
            price_tag = "FREE" if data['price'] == 0 else f"{data['price']:,} PD"
            desc = data.get('description', "")
            if desc == "Auto-discovered skin.": desc = "" # Hide generic text
            
            value_text = f"**💰 {price_tag}**"
            if desc: value_text += f"\n_{desc}_"
            
            embed.add_field(
                name=f"✨ {data['name']}",
                value=value_text,
                inline=True
            )

    embed.set_footer(text="🛒 Click 'Browse & Buy' to purchase • Support: Run the .bat as Admin if it fails.", icon_url="https://i.imgur.com/AfFp7pu.png")
    return embed

async def create_personal_shop_embed(player_stats, skin_id=None):
    """Create the private shop view for a specific player, optionally with a skin preview"""
    balance = player_stats.get('palmarks', 0)
    
    if skin_id and (skin := skin_system.get_skin(skin_id)):
        embed = nextcord.Embed(
            title=f"🎨 PREVIEW: {skin['name']}",
            description=(
                f"{skin.get('description', 'No description.')}\n\n"
                f"💰 Price: **{skin['price']:,} PALDOGS**\n"
                f"💳 Your Balance: **{balance:,} PALDOGS**\n\n"
                "*(Click the button below to see the skin image)*"
            ),
            color=0xff0080
        )
        # Handle Preview Image (Direct URL works instantly)
        if skin.get('image_url'):
            embed.set_image(url=skin['image_url'])
            
        return embed
    
    embed = nextcord.Embed(
        title="🏪 SKIN SHOP CATALOG",
        description=(
            f"👋 Welcome, **{player_stats['player_name']}**!\n"
            f"💰 Your Balance: **{balance:,} PALDOGS**\n\n"
            "Select a skin from the menu below to preview it and purchase."
        ),
        color=0xff0080
    )
    return embed

class UnifiedSkinShopView(View):
    """The persistent view in the store channel"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label="🛒 Browse & Buy Skins", style=nextcord.ButtonStyle.green, emoji="🎨", custom_id="skinshop_persistent_browse")
    async def open_shop(self, button: Button, interaction: nextcord.Interaction):
        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats:
            await interaction.response.send_message(
                "❌ **Registration Required!**\n"
                "Please link your account at the **Main Shop** channel first.", 
                ephemeral=True
            )
        else:
            embed = await create_personal_shop_embed(stats)
            view = SkinShopView(skin_system.get_all_skins(), self.bot, stats)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @nextcord.ui.button(label="🔄 Refresh Shop", style=nextcord.ButtonStyle.secondary, custom_id="skinshop_persistent_refresh")
    async def refresh_shop(self, button: Button, interaction: nextcord.Interaction):
        embed = await create_public_skin_shop_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class SkinShop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command(name="skinshop", description="Open the skin shop menu")
    async def skinshop_command(self, interaction: nextcord.Interaction):
        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats:
            await interaction.response.send_message("❌ Please register at the main shop first!", ephemeral=True)
            return
            
        embed = await create_personal_shop_embed(stats)
        view = SkinShopView(skin_system.get_all_skins(), self.bot, stats)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class SkinShopView(View):
    def __init__(self, skins, bot, player_stats):
        super().__init__(timeout=120)
        self.skins = skins
        self.bot = bot
        self.player_stats = player_stats
        self.selected_skin_id = None
        self.setup_items()

    def setup_items(self):
        self.clear_items()
        options = []
        for sid, data in self.skins.items():
            options.append(nextcord.SelectOption(
                label=f"{data['name']}",
                description=f"{data['price']:,} PD - {data.get('description', '')[:50]}",
                value=sid,
                emoji="🎨",
                default=(sid == self.selected_skin_id)
            ))

        if options:
            select = Select(
                placeholder="Choose a skin to preview...",
                options=options,
                custom_id="skin_select_preview",
                row=0
            )
            select.callback = self.preview_callback
            self.add_item(select)
            
            # Show Image Button
            has_img = False
            if self.selected_skin_id:
                skin = skin_system.get_skin(self.selected_skin_id)
                if skin and (skin.get('image_url') or skin.get('image_filename')):
                    has_img = True
            
            view_btn = Button(
                label="👁️ View Image",
                style=nextcord.ButtonStyle.secondary,
                disabled=(self.selected_skin_id is None or not has_img),
                row=1
            )
            view_btn.callback = self.view_image_callback
            self.add_item(view_btn)

            # Buy Button
            buy_btn = Button(
                label="Confirm Purchase 💰",
                style=nextcord.ButtonStyle.success,
                disabled=(self.selected_skin_id is None),
                row=1
            )
            buy_btn.callback = self.purchase_callback
            self.add_item(buy_btn)

    async def preview_callback(self, interaction: nextcord.Interaction):
        self.selected_skin_id = interaction.data['values'][0]
        self.setup_items()
        embed = await create_personal_shop_embed(self.player_stats, self.selected_skin_id)
        await interaction.response.edit_message(embed=embed, view=self)

    async def view_image_callback(self, interaction: nextcord.Interaction):
        if not self.selected_skin_id: return
        
        skin = skin_system.get_skin(self.selected_skin_id)
        if not skin: return

        if skin.get('image_url'):
            # Just send an ephemeral embed with the image
            embed = nextcord.Embed(title=f"🖼️ Preview: {skin['name']}", color=0xff0080)
            embed.set_image(url=skin['image_url'])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        elif skin.get('image_filename'):
            skins_dir = skin_system.get_skins_dir()
            img_path = os.path.join(skins_dir, skin['image_filename'])
            if os.path.exists(img_path):
                file = nextcord.File(img_path, filename=skin['image_filename'])
                embed = nextcord.Embed(title=f"🖼️ Preview: {skin['name']}", color=0xff0080)
                embed.set_image(url=f"attachment://{skin['image_filename']}")
                await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Image file not found on server.", ephemeral=True)
        else:
            await interaction.response.send_message("📝 This skin has no preview image.", ephemeral=True)

    async def purchase_callback(self, interaction: nextcord.Interaction):
        if not self.selected_skin_id: return
        
        await interaction.response.defer(ephemeral=True)
        skin_data = skin_system.get_skin(self.selected_skin_id)
        
        if not skin_data:
            await interaction.followup.send("❌ This skin is no longer available.", ephemeral=True)
            return

        # Double check stats
        stats = await db.get_player_by_discord(interaction.user.id)
        price = skin_data['price']
        
        if not stats or stats.get('palmarks', 0) < price:
            await interaction.followup.send("❌ Insufficient balance.", ephemeral=True)
            return

        # Verify MOD file existence if not a link
        skins_dir = skin_system.get_skins_dir()
        pak_path = os.path.join(skins_dir, skin_data['pak_filename'])
        if not skin_data.get('download_url') and not os.path.exists(pak_path):
            await interaction.followup.send("❌ Skin file is missing from bot data.", ephemeral=True)
            return

        try:
            # Deduct
            await db.add_palmarks(stats['steam_id'], -price, f"Bought Skin: {skin_data['name']}")
            
            files_to_send = []
            delivery_msg = ""
            download_url = skin_data.get('download_url')
            
            if download_url:
                delivery_msg = (
                    f"🔗 **Download Link:** [Click here to download]({download_url})\n\n"
                    "Extract the `.pak` and use the **install script** below.\n"
                    "📖 *Please read the attached **Instruction.txt** for removal.*"
                )
                if os.path.exists(INSTALLER_SRC):
                    files_to_send.append(nextcord.File(INSTALLER_SRC, filename="install_skin.bat"))
                if os.path.exists(INSTRUCTIONS_SRC):
                    files_to_send.append(nextcord.File(INSTRUCTIONS_SRC, filename="Instruction.txt"))
            else:
                delivery_msg = (
                    "**Installation:**\n"
                    "1. Save & Extract the ZIP.\n"
                    "2. Run `install_skin.bat`.\n"
                    "📖 *See **Instruction.txt** inside for switching skins.*"
                )
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    zip_file.write(pak_path, skin_data['pak_filename'])
                    if os.path.exists(INSTALLER_SRC):
                        zip_file.write(INSTALLER_SRC, "install_skin.bat")
                    if os.path.exists(INSTRUCTIONS_SRC):
                        zip_file.write(INSTRUCTIONS_SRC, "Instruction.txt")
                zip_buffer.seek(0)
                files_to_send.append(nextcord.File(fp=zip_buffer, filename=f"PalSkin_{self.selected_skin_id}.zip"))

            embed = nextcord.Embed(
                title="✅ Purchase Successful!",
                description=f"You got **{skin_data['name']}**!\n\n{delivery_msg}",
                color=0x4CAF50
            )

            # Add Image to the final success message
            if skin_data.get('image_url'):
                embed.set_image(url=skin_data['image_url'])
            elif skin_data.get('image_filename'):
                img_path = os.path.join(skins_dir, skin_data['image_filename'])
                if os.path.exists(img_path):
                    file_img = nextcord.File(img_path, filename=skin_data['image_filename'])
                    files_to_send.append(file_img)
                    embed.set_image(url=f"attachment://{skin_data['image_filename']}")

            await interaction.followup.send(embed=embed, files=files_to_send, ephemeral=True)
            self.stop()
            
        except Exception as e:
            logging.error(f"Purchase failed: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

def setup(bot):
    bot.add_cog(SkinShop(bot))
