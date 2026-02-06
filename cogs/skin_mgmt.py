import nextcord
from nextcord.ext import commands
import os
from utils.config_manager import config
from cogs.skin_system_logic import skin_system

class SkinManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, interaction: nextcord.Interaction):
        admin_id = config.get('admin_user_id', 0)
        return interaction.user.id == admin_id or (hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator)

    @nextcord.slash_command(
        name="skin_admin", 
        description="Admin commands for Skin Shop Management",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def skin_admin_group(self, interaction: nextcord.Interaction):
        pass

    @skin_admin_group.subcommand(name="set_folder", description="Set the source directory where your .pak files are stored")
    async def set_skin_folder(self, interaction: nextcord.Interaction, folder_path: str = nextcord.SlashOption(description="Full path (e.g. C:\\Skins)", required=True)):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        if not os.path.exists(folder_path):
            await interaction.response.send_message(f"❌ Path `{folder_path}` does not exist on the bot's host machine.", ephemeral=True)
            return

        config.set('skins_source_dir', folder_path)
        await interaction.response.send_message(f"✅ Skin source directory set to: `{folder_path}`", ephemeral=True)

    @skin_admin_group.subcommand(name="sync", description="Scan the skin folder for new .pak files automatically")
    async def sync_skins(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        count, added = skin_system.sync_with_folder()
        if count == 0:
            await interaction.response.send_message(f"✅ Sync complete. No new .pak files found in `{skin_system.get_skins_dir()}`.", ephemeral=True)
        else:
            added_text = "\n".join([f"• `{f}`" for f in added])
            await interaction.response.send_message(f"✨ Found and added **{count}** new skins:\n{added_text}\n\n*Use `/skin_admin update` to set their prices and images!*", ephemeral=True)

    @skin_admin_group.subcommand(name="add", description="Manually register a skin")
    async def add_skin(
        self,
        interaction: nextcord.Interaction,
        skin_id: str = nextcord.SlashOption(description="Unique ID for this skin", required=True),
        name: str = nextcord.SlashOption(description="Display name", required=True),
        price: int = nextcord.SlashOption(description="Price in PALDOGS", required=True, min_value=0),
        pak_filename: str = nextcord.SlashOption(description="The exact .pak filename", required=True),
        description: str = nextcord.SlashOption(description="Short description", required=False),
        image_url: str = nextcord.SlashOption(description="URL to a preview image", required=False),
        image_filename: str = nextcord.SlashOption(description="Local image filename instead of URL", required=False),
        download_url: str = nextcord.SlashOption(description="Direct download link (replaces file upload)", required=False)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        skins_dir = skin_system.get_skins_dir()
        pak_path = os.path.join(skins_dir, pak_filename)
        warning = ""
        # If no download URL is provided, we MUST have the local file for upload
        if not download_url and not os.path.exists(pak_path):
            warning = f"\n⚠️ **Note:** File `{pak_filename}` not found in the current skin folder. Players won't be able to buy this unless you provide a `download_url`!"

        skin_system.add_skin(skin_id, name, price, pak_filename, description or "", image_url or "", image_filename or "", download_url or "")
        
        embed = nextcord.Embed(title="✅ Skin Registered", color=0x00FF00)
        embed.add_field(name="Name", value=name, inline=True)
        embed.add_field(name="Price", value=f"{price:,} PD", inline=True)
        if download_url:
            embed.add_field(name="Delivery", value="🔗 External Link", inline=True)
        else:
            embed.add_field(name="Delivery", value="📂 Bot Upload", inline=True)
            
        if image_url: embed.set_thumbnail(url=image_url)
        elif image_filename: embed.set_footer(text=f"🖼️ Local Image: {image_filename}")
        
        await interaction.response.send_message(content=warning, embed=embed, ephemeral=True)

    @skin_admin_group.subcommand(name="update", description="Modify price, image, name, or link of a skin")
    async def update_skin(
        self,
        interaction: nextcord.Interaction,
        skin_id: str = nextcord.SlashOption(description="Select skin", required=True),
        name: str = nextcord.SlashOption(description="New display name", required=False),
        price: int = nextcord.SlashOption(description="New price", required=False, min_value=0),
        description: str = nextcord.SlashOption(description="New description", required=False),
        image_url: str = nextcord.SlashOption(description="New image URL", required=False),
        image_filename: str = nextcord.SlashOption(description="New local image filename", required=False),
        download_url: str = nextcord.SlashOption(description="New direct download link (e.g. Google Drive)", required=False)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        current_skin = skin_system.get_skin(skin_id)
        if not current_skin:
            await interaction.response.send_message("❌ Skin ID not found.", ephemeral=True)
            return

        updated_name = name if name else current_skin['name']
        updated_price = price if price is not None else current_skin['price']
        updated_desc = description if description else current_skin['description']
        updated_img = image_url if image_url else current_skin['image_url']
        updated_img_file = image_filename if image_filename else current_skin.get('image_filename', "")
        updated_link = download_url if download_url else current_skin.get('download_url', "")

        skin_system.add_skin(skin_id, updated_name, updated_price, current_skin['pak_filename'], updated_desc, updated_img, updated_img_file, updated_link)
        await interaction.response.send_message(f"✅ Skin **{skin_id}** updated successfully.", ephemeral=True)

    @update_skin.on_autocomplete("skin_id")
    async def skin_id_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [sid for sid in skin_system.get_all_skin_ids() if current.lower() in sid.lower()]
        await interaction.response.send_autocomplete(choices[:25])

    @skin_admin_group.subcommand(name="delete", description="Permanently remove a skin")
    async def delete_skin(self, interaction: nextcord.Interaction, skin_id: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        if skin_system.delete_skin(skin_id):
            await interaction.response.send_message(f"🗑️ Deleted skin **{skin_id}**.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Skin ID not found.", ephemeral=True)

    @delete_skin.on_autocomplete("skin_id")
    async def delete_skin_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [sid for sid in skin_system.get_all_skin_ids() if current.lower() in sid.lower()]
        await interaction.response.send_autocomplete(choices[:25])

    @skin_admin_group.subcommand(name="setup_shop", description="Post the persistent skin shop interface")
    async def setup_skin_shop(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        channel_id = config.get('skin_shop_channel_id')
        if not channel_id:
            await interaction.response.send_message("❌ Skin shop channel is not configured.", ephemeral=True)
            return

        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return

        from cogs.skin_shop import UnifiedSkinShopView, create_public_skin_shop_embed
        embed = await create_public_skin_shop_embed()
        view = UnifiedSkinShopView(self.bot)
        
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Skin Shop interface posted!", ephemeral=True)

    @skin_admin_group.subcommand(name="list", description="List skins and verify files/links")
    async def list_skins(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        skins = skin_system.get_all_skins()
        if not skins:
            await interaction.response.send_message("📝 Shop is empty.", ephemeral=True)
            return

        embed = nextcord.Embed(title="🎨 Registered Skins (Audit)", color=0x3498db)
        skins_dir = skin_system.get_skins_dir()
        for sid, data in skins.items():
            link = data.get('download_url', "")
            pak_exists = os.path.exists(os.path.join(skins_dir, data['pak_filename']))
            
            # Status badge
            if link:
                status = "🔗 External Link"
            elif pak_exists:
                status = "✅ File OK (Upload)"
            else:
                status = "❌ File Missing (Upload)"
                
            img_file = data.get('image_filename', "")
            img_status = ""
            if img_file:
                img_exists = os.path.exists(os.path.join(skins_dir, img_file))
                img_status = f" | 🖼️: {'✅' if img_exists else '❌'}"
            
            embed.add_field(
                name=f"{data['name']} ({sid})",
                value=f"💰: {data['price']:,} | 📦: `{data['pak_filename']}`{img_status}\n📌: {status}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(SkinManagement(bot))
