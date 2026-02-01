import nextcord
from nextcord.ext import commands
from nextcord import Interaction
from utils.database import db
from cogs.rank_system import rank_system
import logging

class ShopAdminCog(commands.Cog):
    """Hidden Administrator Commands for Shop Management"""
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, interaction: Interaction):
        from utils.config_manager import config
        admin_id = config.get('admin_user_id', 0)
        return interaction.user.id == admin_id or interaction.user.guild_permissions.administrator

    @nextcord.slash_command(name="paldog_admin", description="Paldog Shop Administration", default_member_permissions=8)
    async def paldog_admin(self, interaction: Interaction):
        # This will never be called directly as it's a group
        pass

    @paldog_admin.subcommand(name="reset_progression", description="⚠️ RESET ALL PLAYER RANKS AND PALDOGS")
    async def reset_progression(self, interaction: Interaction, confirm: bool = nextcord.SlashOption(description="Are you absolutely sure?", required=True)):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        if not confirm:
            await interaction.response.send_message("❌ Reset aborted.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        await db.reset_all_progression()
        await interaction.followup.send("🚨 **DATABASE PURGED.** All players have been reset to Level 1, 0 EXP, and 0 PALDOGS.", ephemeral=True)

    @paldog_admin.subcommand(name="give_all", description="🎁 Give PALDOGS to every registered player")
    async def give_all(
        self,
        interaction: Interaction,
        amount: int = nextcord.SlashOption(description="Amount of PALDOGS to give", min_value=1),
        reason: str = nextcord.SlashOption(description="Reason for the gift", default="Admin Gift")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        await db.add_palmarks_to_all(amount, reason)
        await interaction.followup.send(f"✅ Successfully gave **{amount:,} PALDOGS** to all players!\nReason: *{reason}*", ephemeral=False)


    @paldog_admin.subcommand(name="set_announcer_price", description="Update the price of an announcer pack")
    async def set_announcer_price(
        self,
        interaction: Interaction, 
        announcer: str = nextcord.SlashOption(description="The announcer pack to edit", autocomplete=True),
        price: int = nextcord.SlashOption(description="New price in PALDOGS", min_value=0)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        if rank_system.update_announcer_price(announcer, price):
            await interaction.response.send_message(f"✅ Updated **{announcer}** price to **{price:,} PALDOGS**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Announcer pack '{announcer}' not found.", ephemeral=True)

    @set_announcer_price.on_autocomplete("announcer")
    async def announcer_autocomplete(self, interaction: Interaction, current: str):
        choices = [a for a in rank_system.announcer_packs.keys() if current.lower() in a.lower() and a != 'default']
        await interaction.response.send_autocomplete(choices[:25])

def setup(bot):
    bot.add_cog(ShopAdminCog(bot))
    logging.info("✅ ShopAdminCog (Standalone) LOADED")
