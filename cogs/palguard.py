import json
import os
import nextcord
from nextcord.ext import commands
from utils.rcon_utility import rcon_util
from utils.database import db

class PalguardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pals = []
        self.items = []
        self.eggs = []
        self.load_pals()
        self.load_items()
        self.load_eggs()

    def load_pals(self):
        pals_path = os.path.join("gamedata", "pals.json")
        if os.path.exists(pals_path):
            try:
                with open(pals_path, "r", encoding="utf-8") as pals_file:
                    self.pals = json.load(pals_file).get("creatures", [])
            except Exception as e:
                print(f"❌ Error loading pals.json: {e}")

    def load_items(self):
        items_path = os.path.join("gamedata", "items.json")
        if os.path.exists(items_path):
            try:
                with open(items_path, "r", encoding="utf-8") as items_file:
                    self.items = json.load(items_file).get("items", [])
            except Exception as e:
                print(f"❌ Error loading items.json: {e}")

    def load_eggs(self):
        eggs_path = os.path.join("gamedata", "eggs.json")
        if os.path.exists(eggs_path):
            try:
                with open(eggs_path, "r", encoding="utf-8") as eggs_file:
                    self.eggs = json.load(eggs_file).get("eggs", [])
            except Exception as e:
                print(f"❌ Error loading eggs.json: {e}")

    async def get_steam_id(self, player_input: str) -> str:
        """Helper to resolve player name or direct steam ID to a valid steam_ID with prefix"""
        # If it's already a steam_ID, return it
        if player_input.startswith("steam_"):
            return player_input
        
        # If it looks like a raw long SteamID (17 digits)
        if player_input.isdigit() and len(player_input) >= 15:
            return f"steam_{player_input}"
        
        # Try looking up by name in database
        stats = await db.get_player_stats_by_name(player_input)
        if stats and stats.get("steam_id"):
            return stats["steam_id"]
            
        # Return as is if no match found (it might be a raw ID without prefix)
        if player_input.isdigit():
            return f"steam_{player_input}"
        return player_input

    @nextcord.slash_command(
        name="palguard",
        description="PalGuard Admin Commands",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def palguard(self, interaction: nextcord.Interaction):
        pass

    # --- GIVE GROUP ---
    @palguard.subcommand(name="give", description="Give items, pals, or experience")
    async def give_group(self, interaction: nextcord.Interaction):
        pass

    @give_group.subcommand(name="item", description="Give an item to a player")
    async def give_item(
        self,
        interaction: nextcord.Interaction,
        player: str = nextcord.SlashOption(description="Player name or SteamID", autocomplete=True),
        item: str = nextcord.SlashOption(description="Item name", autocomplete=True),
        amount: int = nextcord.SlashOption(description="Quantity to give", min_value=1, default=1)
    ):
        await interaction.response.defer(ephemeral=True)
        
        steamid = await self.get_steam_id(player)
        # Find item ID by name if it's a name from autocomplete
        item_id = next((i["id"] for i in self.items if i["name"].lower() == item.lower()), item)
        
        success = await rcon_util.give_item(steamid, item_id, amount)
        if success:
            await interaction.followup.send(f"✅ Successfully gave **{amount}x {item}** to player `{player}`.")
        else:
            await interaction.followup.send(f"❌ Failed to give item. Check if player `{player}` is online and SteamID is correct.")

    @give_group.subcommand(name="pal", description="Give a pal to a player")
    async def give_pal(
        self,
        interaction: nextcord.Interaction,
        player: str = nextcord.SlashOption(description="Player name or SteamID", autocomplete=True),
        pal: str = nextcord.SlashOption(description="Pal name", autocomplete=True),
        level: int = nextcord.SlashOption(description="Pal level", min_value=1, max_value=50, default=1)
    ):
        await interaction.response.defer(ephemeral=True)
        
        steamid = await self.get_steam_id(player)
        pal_id = next((p["id"] for p in self.pals if p["name"].lower() == pal.lower()), pal)
        
        cmd = f"givepal {steamid} {pal_id} {level}"
        server_info = rcon_util._get_server_info()
        
        if not server_info:
            await interaction.followup.send("❌ RCON not configured.")
            return

        resp = await rcon_util.rcon_command(server_info, cmd)
        if resp and "success" in resp.lower():
            await interaction.followup.send(f"✅ Successfully gave **{pal}** (Lv.{level}) to player `{player}`.")
        else:
            await interaction.followup.send(f"Result: {resp}")

    @give_group.subcommand(name="exp", description="Give experience to a player")
    async def give_exp(
        self,
        interaction: nextcord.Interaction,
        player: str = nextcord.SlashOption(description="Player name or SteamID", autocomplete=True),
        amount: int = nextcord.SlashOption(description="Amount of EXP", min_value=1)
    ):
        await interaction.response.defer(ephemeral=True)
        
        steamid = await self.get_steam_id(player)
        success = await rcon_util.give_exp(steamid, amount)
        
        if success:
            await interaction.followup.send(f"✅ Successfully gave **{amount} EXP** to player `{player}`.")
        else:
            await interaction.followup.send(f"❌ Failed to give EXP. Check if player `{player}` is online.")

    @give_group.subcommand(name="egg", description="Give a pal egg to a player")
    async def give_egg(
        self,
        interaction: nextcord.Interaction,
        player: str = nextcord.SlashOption(description="Player name or SteamID", autocomplete=True),
        egg: str = nextcord.SlashOption(description="Egg name", autocomplete=True)
    ):
        await interaction.response.defer(ephemeral=True)
        
        steamid = await self.get_steam_id(player)
        egg_id = next((e["id"] for e in self.eggs if e["name"].lower() == egg.lower()), egg)
        
        cmd = f"giveegg {steamid} {egg_id}"
        server_info = rcon_util._get_server_info()
        
        if not server_info:
            await interaction.followup.send("❌ RCON not configured.")
            return

        resp = await rcon_util.rcon_command(server_info, cmd)
        if resp and ("success" in resp.lower() or "sent" in resp.lower()):
            await interaction.followup.send(f"✅ Successfully gave **{egg}** to player `{player}`.")
        else:
            await interaction.followup.send(f"Result: {resp}")

    # --- AUTOCOMPLETES ---

    @give_item.on_autocomplete("player")
    @give_pal.on_autocomplete("player")
    @give_exp.on_autocomplete("player")
    @give_egg.on_autocomplete("player")
    async def player_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = await db.get_player_names_autocomplete(current)
        await interaction.response.send_autocomplete(choices)

    @give_item.on_autocomplete("item")
    async def item_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [i["name"] for i in self.items if current.lower() in i["name"].lower()][:25]
        await interaction.response.send_autocomplete(choices)

    @give_pal.on_autocomplete("pal")
    async def pal_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [p["name"] for p in self.pals if current.lower() in p["name"].lower()][:25]
        await interaction.response.send_autocomplete(choices)

    @give_egg.on_autocomplete("egg")
    async def egg_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [e["name"] for e in self.eggs if current.lower() in e["name"].lower()][:25]
        await interaction.response.send_autocomplete(choices)

def setup(bot):
    bot.add_cog(PalguardCog(bot))
