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

    @paldog_admin.subcommand(name="give_paldogs", description="💰 Give PALDOGS to a specific player")
    async def give_paldogs(
        self,
        interaction: Interaction,
        player_name: str = nextcord.SlashOption(description="Player to give to", autocomplete=True),
        amount: int = nextcord.SlashOption(description="Amount of PALDOGS to give", min_value=1),
        reason: str = nextcord.SlashOption(description="Reason for the gift", default="Admin Grant")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        stats = await db.get_player_stats_by_name(player_name)
        if not stats:
            await interaction.followup.send(f"❌ Player '{player_name}' not found.", ephemeral=True)
            return

        await db.add_palmarks(stats['steam_id'], amount, reason)
        await interaction.followup.send(f"✅ Successfully gave **{amount:,} PALDOGS** to **{stats['player_name']}**!\nReason: *{reason}*", ephemeral=True)

    @paldog_admin.subcommand(name="grant_reward", description="🎁 Grant a Pal or Item to a player's /inventory")
    async def grant_reward(
        self,
        interaction: Interaction,
        player_name: str = nextcord.SlashOption(description="Player to grant to", autocomplete=True),
        reward_id: str = nextcord.SlashOption(description="ID of the item or Pal"),
        reward_type: str = nextcord.SlashOption(choices={"Item": "item", "Pal": "pal", "Template Pal": "template_pal"}),
        amount: int = nextcord.SlashOption(description="Amount (for items)", default=1, min_value=1)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        stats = await db.get_player_stats_by_name(player_name)
        if not stats:
            await interaction.followup.send(f"❌ Player '{player_name}' not found.", ephemeral=True)
            return

        await db.add_to_inventory(stats['steam_id'], reward_id, amount, "Admin Grant", reward_type)
        await interaction.followup.send(f"✅ Granted **{amount}x {reward_id}** ({reward_type}) to **{stats['player_name']}**'s virtual inventory!\nThey can claim it using `/inventory`.", ephemeral=True)

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

    @give_paldogs.on_autocomplete("player_name")
    @grant_reward.on_autocomplete("player_name")
    async def player_autocomplete(self, interaction: Interaction, current: str):
        choices = await db.get_player_names_autocomplete(current)
        await interaction.response.send_autocomplete(choices)

def setup(bot):
    bot.add_cog(ShopAdminCog(bot))
    logging.info("✅ ShopAdminCog LOADED")
