import nextcord
from nextcord.ext import commands
from utils.config_manager import config
from utils.rcon_utility import rcon_util
from utils.database import db
from cogs.kit_system import kit_system

class KitManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, interaction: nextcord.Interaction):
        admin_id = config.get('admin_user_id', 0)
        return interaction.user.id == admin_id or (hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator)

    @nextcord.slash_command(name="kit")
    async def kit_group(self, interaction: nextcord.Interaction):
        """Parent command for kit management"""
        pass

    @kit_group.subcommand(name="edit", description="Change a kit's description or price")
    async def edit_preset(
        self,
        interaction: nextcord.Interaction,
        kit_name: str = nextcord.SlashOption(description="Name of the kit to edit", required=True),
        new_description: str = nextcord.SlashOption(description="New description text", required=False),
        new_price: int = nextcord.SlashOption(description="New PALDOGS price", required=False, min_value=0)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
            
        if kit_system.edit_kit(kit_name, new_description, new_price):
            await interaction.response.send_message(f"✅ Kit **{kit_name}** updated successfully.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Kit '{kit_name}' not found.", ephemeral=True)

    @edit_preset.on_autocomplete("kit_name")
    async def edit_kit_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [k for k in kit_system.get_all_kit_names() if current.lower() in k.lower()]
        await interaction.response.send_autocomplete(choices[:25])

    @kit_group.subcommand(name="add_item", description="Add an item to a kit")
    async def add_item_to_kit(
        self,
        interaction: nextcord.Interaction,
        kit_name: str = nextcord.SlashOption(description="Kit name"),
        item_id: str = nextcord.SlashOption(description="Item ID"),
        amount: int = nextcord.SlashOption(min_value=1),
        description: str = nextcord.SlashOption(required=False),
        price: int = nextcord.SlashOption(required=False, min_value=0)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
        msg = kit_system.create_or_update_kit(kit_name, item_id, amount, description, price)
        await interaction.response.send_message(f"✅ {msg}: Added **{amount}x {item_id}**.", ephemeral=True)

    @add_item_to_kit.on_autocomplete("kit_name")
    async def add_kit_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [k for k in kit_system.get_all_kit_names() if current.lower() in k.lower()]
        await interaction.response.send_autocomplete(choices[:25])

    @kit_group.subcommand(name="view", description="Show kit contents")
    async def view_kit(self, interaction: nextcord.Interaction, kit_name: str = nextcord.SlashOption(required=False)):
        if kit_name:
            kit = kit_system.get_kit(kit_name)
            if not kit:
                await interaction.response.send_message("❌ Kit not found.", ephemeral=True)
                return
            items = "\n".join([f"• **{i}**: {a}x" for i, a in kit['items'].items()]) or "No items."
            embed = nextcord.Embed(title=f"📦 Kit: {kit_name}", description=kit.get('description', 'No description'), color=0x00ADD8)
            embed.add_field(name="Contents", value=items)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            kits = kit_system.get_all_kit_names()
            embed = nextcord.Embed(title="📦 Available Kits", color=0x00ADD8)
            for k in kits:
                info = kit_system.get_kit(k)
                embed.add_field(name=k.title(), value=f"{len(info['items'])} items", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @view_kit.on_autocomplete("kit_name")
    async def view_kit_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [k for k in kit_system.get_all_kit_names() if current.lower() in k.lower()]
        await interaction.response.send_autocomplete(choices[:25])

    @kit_group.subcommand(name="delete", description="Permanently delete a kit")
    async def delete_kit(self, interaction: nextcord.Interaction, kit_name: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
        if kit_system.delete_kit(kit_name):
            await interaction.response.send_message(f"🗑️ Deleted kit **{kit_name}**.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Kit not found.", ephemeral=True)

    @delete_kit.on_autocomplete("kit_name")
    async def delete_kit_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [k for k in kit_system.get_all_kit_names() if current.lower() in k.lower()]
        await interaction.response.send_autocomplete(choices[:25])

    @kit_group.subcommand(name="give", description="Send a kit to a player via RCON")
    async def give_kit(
        self,
        interaction: nextcord.Interaction,
        player_name: str = nextcord.SlashOption(description="Player name"),
        kit_name: str = nextcord.SlashOption(description="Kit name")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
            
        if not rcon_util.is_configured():
            await interaction.response.send_message("❌ RCON not configured.", ephemeral=True)
            return

        kit = kit_system.get_kit(kit_name)
        if not kit:
            await interaction.response.send_message(f"❌ Kit '{kit_name}' not found.", ephemeral=True)
            return
        
        await interaction.response.defer()
        stats = await db.get_player_stats_by_name(player_name.strip())
        if not stats:
            await interaction.followup.send(f"❌ Player '{player_name}' not found.")
            return
        
        results = []
        success_count = 0
        for item_id, amt in kit['items'].items():
            if await rcon_util.give_item(stats['steam_id'], item_id, amt):
                results.append(f"✅ {amt}x {item_id}")
                success_count += 1
            else:
                results.append(f"❌ {amt}x {item_id} (Failed)")
                
        embed = nextcord.Embed(title=f"🎁 Kit '{kit_name}' Sent", description="\n".join(results), color=0x00FF00 if success_count == len(kit['items']) else 0xFFA500)
        await interaction.followup.send(embed=embed)

    @give_kit.on_autocomplete("kit_name")
    async def give_kit_name_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [k for k in kit_system.get_all_kit_names() if current.lower() in k.lower()]
        await interaction.response.send_autocomplete(choices[:25])

    @give_kit.on_autocomplete("player_name")
    async def give_kit_player_autocomplete(self, interaction: nextcord.Interaction, current: str):
        await interaction.response.send_autocomplete(await db.get_player_names_autocomplete(current))

def setup(bot):
    bot.add_cog(KitManagement(bot))
    # Direct print for console visibility
    print(f"✅ KitManagement Cog LOADED from: {__file__}")

    @bot.command(name="checkcode")
    async def check_code(ctx):
        import inspect
        source = inspect.getsource(KitManagement)
        # Send first 1500 chars to avoid Discord limit
        await ctx.send(f"```python\n# Current KitManagement source (partial):\n{source[:1500]}\n```")
