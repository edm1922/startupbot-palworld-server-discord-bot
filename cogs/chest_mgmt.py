import nextcord
from nextcord.ext import commands
import asyncio
import time
import json
import os
import random
from utils.config_manager import config
from utils.rcon_utility import rcon_util
from utils.database import db
from cogs.chest_system import chest_system
from cogs.kit_mgmt import kit_system
from cogs.pal_system import pal_system

class ChestSelectionView(nextcord.ui.View):
    """Ephemeral view that shows 3 random chest choices"""
    def __init__(self, bot, steam_id, tiers, reroll_cost):
        super().__init__(timeout=600)
        self.bot = bot
        self.steam_id = steam_id
        self.tiers = tiers
        self.reroll_cost = reroll_cost
        
        # Add buttons for opening specific chests
        for i, tier in enumerate(tiers):
            cost = chest_system.config["tier_costs"].get(tier, 500)
            btn = nextcord.ui.Button(
                label=f"Open {tier.title()} ({cost})",
                style=self.get_style(tier),
                custom_id=f"open_tier_{i}_{tier}",
                row=0
            )
            btn.callback = self.make_callback(i, tier, cost)
            self.add_item(btn)

    def get_style(self, tier):
        if tier == "legendary": return nextcord.ButtonStyle.danger # Red
        if tier == "epic": return nextcord.ButtonStyle.primary     # Blurple
        if tier == "rare": return nextcord.ButtonStyle.success     # Green
        return nextcord.ButtonStyle.secondary                      # Grey

    def make_callback(self, index, tier, cost):
        async def callback(interaction: nextcord.Interaction):
            await self.process_open(interaction, tier, cost)
        return callback

    @nextcord.ui.button(label="🔄 Reroll Selection", style=nextcord.ButtonStyle.gray, row=1)
    async def reroll_btn(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        # Check Balance for Reroll
        player = await db.get_player_by_discord(interaction.user.id)
        if not player or player['palmarks'] < self.reroll_cost:
            return await interaction.response.send_message(f"❌ Need {self.reroll_cost} PALDOGS to reroll.", ephemeral=True)
            
        await db.add_palmarks(self.steam_id, -self.reroll_cost, "Chest Reroll")
        
        # Generate new chests
        new_tiers = [chest_system.roll_rarity() for _ in range(3)]
        
        # Update View
        new_view = ChestSelectionView(self.bot, self.steam_id, new_tiers, self.reroll_cost)
        embed = self.generate_embed(new_tiers)
        await interaction.response.edit_message(embed=embed, view=new_view)

    async def process_open(self, interaction: nextcord.Interaction, tier, cost):
        player = await db.get_player_by_discord(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ Not linked.", ephemeral=True)
        
        # 1. Cost Check
        # We also add the progressive cost here if configured, 
        # but requested structure implied fixed tier cost?
        # Let's keep progressive logic to stay consistent with user's previous request.
        # "Total Cost = Base_Tier_Cost + (Level * Increment)"
        level = await db.get_chest_level(self.steam_id)
        increment = chest_system.config.get('cost_increment', 250)
        total_cost = cost + (level * increment)
        
        if player['palmarks'] < total_cost:
             return await interaction.response.send_message(f"❌ Need {total_cost} PALDOGS (Base {cost} + Tax {level*increment}).", ephemeral=True)

        # 2. Daily Limit
        daily_count = await db.get_daily_usage(self.steam_id, 'chest_rolls')
        daily_limit = chest_system.config.get('daily_limit', 50)
        if daily_count >= daily_limit:
            return await interaction.response.send_message(f"⚠️ Daily limit reached ({daily_limit}).", ephemeral=True)

        # 3. Online Check
        online_ids = await self.get_online_steam_ids()
        if self.steam_id.replace("steam_", "") not in online_ids:
             return await interaction.response.send_message("❌ You must be ONLINE to open chests.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            # Transact
            await db.add_palmarks(self.steam_id, -total_cost, f"Chest Open: {tier}")
            await db.increment_chest_level(self.steam_id)
            await db.increment_daily_usage(self.steam_id, 'chest_rolls')
            
            # Roll Reward
            reward = chest_system.roll_reward(tier)
            if not reward:
                await interaction.followup.send(f"⚠️ Chest ({tier}) was empty. Contact Admin.")
                return

            # Deliver
            success, msg = await self.deliver_reward(self.steam_id, reward)
            
            # Feedback
            embed = nextcord.Embed(
                title=f"📦 {tier.upper()} CHEST OPENED!",
                description=f"Spent: **{total_cost}** PALDOGS",
                color=0xFFD700 if tier=="legendary" else 0xA335EE if tier=="epic" else 0x0070DD
            )
            embed.add_field(name="Reward", value=f"**{reward.get('name', reward['id'])}**", inline=False)
            embed.add_field(name="Status", value="✅ Delivered" if success else f"❌ {msg}", inline=False)
            
            await interaction.followup.send(embed=embed, delete_after=10)
            
            if success:
                 # Broadcast
                p_name = player['player_name']
                icon = "🌟" if tier=="legendary" else "🟣" if tier=="epic" else "🔵" if tier=="rare" else "🟢"
                bc = f"{icon} [CHEST] {p_name} opened a {tier.upper()} chest: {reward.get('name', reward['id'])}"
                asyncio.create_task(rcon_util.broadcast(bc))

            # Refresh view with new chests automatically or keep same?
            # Typically you'd refresh.
            new_tiers = [chest_system.roll_rarity() for _ in range(3)]
            new_view = ChestSelectionView(self.bot, self.steam_id, new_tiers, self.reroll_cost)
            new_embed = self.generate_embed(new_tiers)
            await interaction.edit_original_message(embed=new_embed, view=new_view)

            # Record Public Activity
            activity_entry = {
                "user": player['player_name'],
                "tier": tier,
                "reward": reward.get('name', reward['id']),
                "time": time.time()
            }
            # Find the cog instance to update activity
            cog = self.bot.get_cog("ChestManagement")
            if cog:
                cog.recent_activity.insert(0, activity_entry)
                cog.recent_activity = cog.recent_activity[:10]
                # Update the main UI table if we have a message ID
                from utils.config_manager import config
                channel_id = config.get('chest_room_channel_id')
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        asyncio.create_task(cog.update_chest_table(channel))

        except Exception as e:
            print(f"Error opening chest: {e}")
            await interaction.followup.send("❌ Error processing request.")

    def generate_embed(self, tiers):
        embed = nextcord.Embed(title="🛍️ Chest Selection", description="Choose a chest to open or reroll for better options.", color=0x2b2d31)
        for i, tier in enumerate(tiers):
            cost = chest_system.config["tier_costs"].get(tier, 500)
            emoji = "📦"
            if tier == "legendary": emoji = "🌟"
            elif tier == "epic": emoji = "🟣"
            elif tier == "rare": emoji = "🔵"
            else: emoji = "🟢"
            
            embed.add_field(name=f"Chest #{i+1}", value=f"{emoji} **{tier.title()}**\n💰 Cost: {cost}", inline=True)
        
        embed.set_footer(text=f"Reroll Cost: {self.reroll_cost} PALDOGS")
        return embed

    async def get_online_steam_ids(self) -> list:
        if not rcon_util.is_configured(): return []
        resp = await rcon_util.rcon_command(rcon_util._get_server_info(), "ShowPlayers")
        if not resp: return []
        steam_ids = []
        for line in resp.split('\n')[1:]:
            parts = line.split(',')
            if len(parts) >= 3: steam_ids.append(parts[2].strip())
        return steam_ids

    async def deliver_reward(self, steam_id, reward):
        if reward['type'] == 'item':
            return await rcon_util.give_item(steam_id, reward['id'], reward['amount'])
        elif reward['type'] == 'kit':
            kit = kit_system.get_kit(reward['id'])
            if not kit: return False, "Kit not found"
            results = []
            for k_item, k_amt in kit['items'].items():
                s, _ = await rcon_util.give_item(steam_id, k_item, k_amt)
                results.append(s)
            return any(results), "Kit Delivered"
        elif reward['type'] == 'pal':
            return await rcon_util.give_pal_template(steam_id, reward['id'])
        elif reward['type'] == 'currency' and reward['id'] == 'PALDOGS':
            await db.add_palmarks(steam_id, reward['amount'], "Chest Reward")
            return True, "Added"
        elif reward['type'] == 'exp':
            return await rcon_util.give_exp(steam_id, reward['amount'])
        return False, "Unknown"

class ChestView(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label="Find Chests 🔍", style=nextcord.ButtonStyle.success, custom_id="chest_find_btn")
    async def find_chests(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        user_id = interaction.user.id
        player = await db.get_player_by_discord(user_id)
        if not player:
            return await interaction.response.send_message("❌ You are not linked! Use `/link` first.", ephemeral=True)

        steam_id = player['steam_id']
        
        # Initial 3 random tiers
        tiers = [chest_system.roll_rarity() for _ in range(3)]
        reroll_cost = chest_system.config.get("reroll_cost", 100)
        
        view = ChestSelectionView(self.bot, steam_id, tiers, reroll_cost)
        embed = view.generate_embed(tiers)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @nextcord.ui.button(label="Reset Cost 🔄", style=nextcord.ButtonStyle.secondary, custom_id="chest_reset_btn")
    async def reset_cost(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
         # Same logic as before
        user_id = interaction.user.id
        player = await db.get_player_by_discord(user_id)
        if not player: return await interaction.response.send_message("❌ Not linked.", ephemeral=True)
        
        if await db.get_chest_level(player['steam_id']) > 0:
            await db.reset_chest_level(player['steam_id'])
            await interaction.response.send_message("✅ Cost level reset.", ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ Already at base level.", ephemeral=True)

    @nextcord.ui.button(label="My Stats 📊", style=nextcord.ButtonStyle.gray, custom_id="chest_stats_btn")
    async def check_stats(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        user_id = interaction.user.id
        player = await db.get_player_by_discord(user_id)
        if not player: return await interaction.response.send_message("❌ Not linked.", ephemeral=True)
        
        level = await db.get_chest_level(player['steam_id'])
        rolls = await db.get_daily_usage(player['steam_id'], 'chest_rolls')
        
        await interaction.response.send_message(
            f"📊 **Your Chest Stats**\n"
            f"💰 Balance: {player['palmarks']} PALDOGS\n"
            f"📈 Cost Level: {level}\n"
            f"🎲 Rolls Today: {rolls}",
            ephemeral=True
        )

class ChestManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.setup_view())
        self.recent_activity = [] # [ {"user": "User", "tier": "Epic", "reward": "Item"} ]

    async def setup_view(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(ChestView(self.bot))

    def is_admin(self, interaction: nextcord.Interaction):
        admin_id = config.get('admin_user_id', 0)
        return interaction.user.id == admin_id or (hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator)

    @nextcord.slash_command(
        name="chest", 
        description="Chest System Commands",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def chest_group(self, interaction: nextcord.Interaction):
        pass

    @chest_group.subcommand(name="setup_ui", description="[Admin] Spawn the persistent chest UI embed")
    async def setup_chest_ui(self, interaction: nextcord.Interaction, channel: nextcord.TextChannel = None):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("❌ Admin only.", ephemeral=True)

        target_channel = channel or interaction.channel
        config.set('chest_room_channel_id', target_channel.id)
        
        await self.update_chest_table(target_channel)
        await interaction.response.send_message(f"✅ Chest UI spawned in {target_channel.mention}", ephemeral=True)

    async def update_chest_table(self, channel):
        """Update or create the main Mystery Chest Room embed"""
        # Recent Activity Log
        activity_text = ""
        if self.recent_activity:
            for act in self.recent_activity:
                icon = "🌟" if act['tier']=="legendary" else "🟣" if act['tier']=="epic" else "🔵" if act['tier']=="rare" else "🟢"
                activity_text += f"{icon} `{act['user']}` found **{act['reward']}**\n"
        else:
            activity_text = "▫️ *No recent discoveries yet.*"

        embed = nextcord.Embed(
            title="✨ MYSTERY CHEST ROOM ✨",
            description=(
                "Search the room to find Basic, Rare, Epic, or Legendary chests!\n\n"
                "📜 **RECENT DISCOVERIES:**\n"
                f"{activity_text}\n"
                "**How to Play**:\n"
                "1. Click **Find Chests 🔍** to reveal 3 random chests.\n"
                "2. Don't like them? Click **Reroll** to find new ones.\n"
                "3. Click **Open** on the chest you want!\n\n"
                "💰 **Costs** vary by chest rarity!\n"
                "📈 **Progressive Tax**: Opening many chests increases costs slightly."
            ),
            color=0xFFD700
        )
        embed.set_footer(text="Rewards are delivered in-game instantly!")
        
        msg_id = config.get('chest_room_message_id')
        view = ChestView(self.bot)
        
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return
            except nextcord.NotFound:
                config.set('chest_room_message_id', None)
            except Exception as e:
                print(f"⚠️ Error updating chest table: {e}")

        # Create new if doesn't exist
        msg = await channel.send(embed=embed, view=view)
        config.set('chest_room_message_id', msg.id)

    @chest_group.subcommand(name="admin", description="Admin settings for Chests")
    async def chest_admin(self, interaction: nextcord.Interaction):
        pass
    
    @chest_admin.subcommand(name="configure", description="Configure Chest Settings")
    async def configure_chest(
        self, 
        interaction: nextcord.Interaction, 
        reroll_cost: int = nextcord.SlashOption(required=False),
        daily_limit: int = nextcord.SlashOption(required=False),
        basic_cost: int = nextcord.SlashOption(required=False),
        rare_cost: int = nextcord.SlashOption(required=False),
        epic_cost: int = nextcord.SlashOption(required=False),
        legendary_cost: int = nextcord.SlashOption(required=False)
    ):
        if not self.is_admin(interaction): return await interaction.response.send_message("❌ Denied", ephemeral=True)
        
        changes = []
        if reroll_cost is not None:
            chest_system.config['reroll_cost'] = reroll_cost
            changes.append(f"Reroll Cost: {reroll_cost}")
        if daily_limit is not None:
            chest_system.config['daily_limit'] = daily_limit
            changes.append(f"Daily Limit: {daily_limit}")
            
        if basic_cost: chest_system.config['tier_costs']['basic'] = basic_cost
        if rare_cost: chest_system.config['tier_costs']['rare'] = rare_cost
        if epic_cost: chest_system.config['tier_costs']['epic'] = epic_cost
        if legendary_cost: chest_system.config['tier_costs']['legendary'] = legendary_cost
            
        chest_system.save_config()
        await interaction.response.send_message(f"✅ Updated:\n" + "\n".join(changes), ephemeral=True)

    @chest_admin.subcommand(name="add_reward", description="Add a new reward to a specific chest tier")
    async def add_reward(
        self, 
        interaction: nextcord.Interaction, 
        tier: str = nextcord.SlashOption(
            description="Which chest tier should this reward go in?",
            choices=["basic", "rare", "epic", "legendary"],
            required=True
        ), 
        type: str = nextcord.SlashOption(
            description="What type of reward is this?",
            choices=["item", "kit", "pal", "currency", "exp"],
            required=True
        ), 
        id: str = nextcord.SlashOption(
            description="The technical ID (e.g., PalSphere, KitName, or PalTemplate)",
            required=True
        ), 
        amount: int = nextcord.SlashOption(
            description="Amount to give (e.g., 50 for 50 items or 5000 for currency)",
            default=1,
            min_value=1
        ), 
        weight: float = nextcord.SlashOption(
            description="How likely is this to drop compared to others in the same tier?",
            default=1.0,
            min_value=0.1
        )
    ):
        if not self.is_admin(interaction): return await interaction.response.send_message("❌ Denied", ephemeral=True)
        if chest_system.add_reward(tier, type, id, amount, weight):
            await interaction.response.send_message(f"✅ Added **{id}** ({type}) to the **{tier.upper()}** chest pool!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to add reward. Please check the ID and try again.", ephemeral=True)

    @chest_admin.subcommand(name="remove_reward", description="Remove a reward from a chest tier")
    async def remove_reward(
        self, 
        interaction: nextcord.Interaction, 
        tier: str = nextcord.SlashOption(
            description="Which tier is the reward in?",
            choices=["basic", "rare", "epic", "legendary"],
            required=True
        ), 
        id: str = nextcord.SlashOption(
            description="The ID of the reward to remove",
            required=True
        )
    ):
        if not self.is_admin(interaction): return await interaction.response.send_message("❌ Denied", ephemeral=True)
        removed = False
        for t in ['item', 'kit', 'pal', 'currency']:
            if chest_system.remove_reward(tier, id, t):
                removed = True
        
        if removed: await interaction.response.send_message(f"✅ Removed {id}", ephemeral=True)
        else: await interaction.response.send_message("❌ Not found", ephemeral=True)

def setup(bot):
    bot.add_cog(ChestManagement(bot))
