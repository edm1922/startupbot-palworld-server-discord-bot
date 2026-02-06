import nextcord
import json
import os
import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from nextcord.ext import commands, tasks
from utils.config_manager import config
from utils.database import db
from utils.rcon_utility import rcon_util
from utils.rest_api import rest_api
from cogs.kit_system import kit_system
from cogs.pal_system import pal_system

GIVEAWAY_FILE = "data/giveaways.json"

class GiveawayData:
    def __init__(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filename = os.path.join(root_dir, GIVEAWAY_FILE)
        self.giveaways = {}
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.giveaways = json.load(f)
            except json.JSONDecodeError:
                self.giveaways = {}
        else:
            self.giveaways = {}
            self.save_data()

    def save_data(self):
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.giveaways, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving giveaway data: {e}")

    def create_giveaway(self, msg_id, channel_id, prize_type, prize_name, end_time, winners_count, min_participants=0):
        self.giveaways[str(msg_id)] = {
            "channel_id": channel_id,
            "prize_type": prize_type,
            "prize_name": prize_name,
            "end_time": end_time.isoformat(),
            "winners_count": winners_count,
            "min_participants": min_participants,
            "participants": [],
            "winners": {}, # dict of user_id: claimed (bool)
            "is_ended": False
        }
        self.save_data()

    def add_participant(self, msg_id, user_id):
        gid = str(msg_id)
        user_id = str(user_id)
        if gid in self.giveaways:
            if user_id not in self.giveaways[gid]["participants"]:
                self.giveaways[gid]["participants"].append(user_id)
                self.save_data()
                return True
        return False

    def end_giveaway(self, msg_id, winners):
        gid = str(msg_id)
        if gid in self.giveaways:
            self.giveaways[gid]["is_ended"] = True
            # Store winners as a dict: "str(user_id)": False (not claimed)
            self.giveaways[gid]["winners"] = {str(w): False for w in winners}
            self.save_data()

    def mark_claimed(self, msg_id, user_id):
        gid = str(msg_id)
        uid = str(user_id)
        if gid in self.giveaways and uid in self.giveaways[gid]["winners"]:
            self.giveaways[gid]["winners"][uid] = True
            self.save_data()
            return True
        return False

    def get_giveaway(self, msg_id):
        return self.giveaways.get(str(msg_id))

    def delete_giveaway(self, msg_id):
        gid = str(msg_id)
        if gid in self.giveaways:
            del self.giveaways[gid]
            self.save_data()
            return True
        return False

    def update_message_id(self, old_id, new_id):
        old_id, new_id = str(old_id), str(new_id)
        if old_id in self.giveaways:
            data = self.giveaways.pop(old_id)
            self.giveaways[new_id] = data
            self.save_data()
            return True
        return False

    def get_active_giveaways(self):
        return {k: v for k, v in self.giveaways.items() if not v["is_ended"]}
    
    def find_pending_claim(self, user_id):
        uid = str(user_id)
        for gid, data in self.giveaways.items():
            if data["is_ended"] and uid in data["winners"] and not data["winners"][uid]:
                return gid, data
        return None, None

giveaway_data = GiveawayData()

def get_giveaway_embed(data):
    """Utility to generate the giveaway embed based on current data."""
    end_time = datetime.fromisoformat(data["end_time"])
    participants_count = len(data.get("participants", []))
    
    embed = nextcord.Embed(
        title="🎁 SPECIAL GIVEAWAY 🎁",
        description=(
            f"Prize: **{data['prize_name']}** {f'({data['prize_type'].title()})' if data['prize_type'] != 'paldogs' else 'PALDOGS'}\n"
            f"Winners: **{data['winners_count']}**\n"
            f"Participants: **{participants_count}**\n"
            f"Min Participants: **{data.get('min_participants', 0)}**\n"
            f"Ends: <t:{int(end_time.timestamp())}:R> (<t:{int(end_time.timestamp())}:f>)"
        ),
        color=0x00FF88
    )
    embed.set_footer(text="Click the button below to join! • Winners must be online to claim.")
    return embed

async def update_giveaway_message(interaction, msg_id):
    """Updates the giveaway message embed to show live participant count."""
    data = giveaway_data.get_giveaway(msg_id)
    if not data or data["is_ended"]:
        return

    # Try to get the message from the interaction first
    message = interaction.message
    if not message or message.id != int(msg_id):
        # Fallback to fetching
        channel = interaction.client.get_channel(data["channel_id"])
        if not channel:
            try: 
                channel = await interaction.client.fetch_channel(data["channel_id"])
            except: 
                return
        try:
            message = await channel.fetch_message(int(msg_id))
        except:
            return

    embed = get_giveaway_embed(data)
    try:
        await message.edit(embed=embed)
    except Exception as e:
        logging.error(f"Failed to update giveaway message {msg_id}: {e}")

class GiveawayRegistrationModal(nextcord.ui.Modal):
    def __init__(self, msg_id):
        super().__init__(title="Register for Giveaway")
        self.msg_id = msg_id
        self.name_input = nextcord.ui.TextInput(
            label="What is your EXACT In-Game Name?",
            placeholder="Case-sensitive (e.g. AMEN)",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)

    async def callback(self, interaction: nextcord.Interaction):
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
        
        # Now add to giveaway
        if giveaway_data.add_participant(self.msg_id, interaction.user.id):
            await interaction.response.send_message(f"✅ **Account Linked!** You've been entered into the giveaway as **{player_name}**.", ephemeral=True)
            await update_giveaway_message(interaction, self.msg_id)
        else:
            await interaction.response.send_message(f"✅ **Account Linked!** (But you were already in this giveaway)", ephemeral=True)

class GiveawayJoinView(nextcord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label="🎉 Enter Giveaway", style=nextcord.ButtonStyle.blurple, custom_id="giveaway_join_persistent")
    async def join_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        msg_id = interaction.message.id
        
        # Check if user is linked
        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats:
            await interaction.response.send_modal(GiveawayRegistrationModal(msg_id))
            return

        if giveaway_data.add_participant(msg_id, interaction.user.id):
            await interaction.response.send_message("✅ You've entered the giveaway!", ephemeral=True)
            await update_giveaway_message(interaction, msg_id)
        else:
            await interaction.response.send_message("❌ You are already in this giveaway!", ephemeral=True)

class GiveawayClaimView(nextcord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label="🎁 Claim Reward", style=nextcord.ButtonStyle.green, custom_id="giveaway_claim_persistent")
    async def claim_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # 1. Find pending claim
        gid, data = giveaway_data.find_pending_claim(interaction.user.id)
        if not gid:
            await interaction.followup.send("❌ You don't have any pending rewards to claim, or you've already claimed them.", ephemeral=True)
            return

        # 2. Check if user is linked to a SteamID
        player_stat = await db.get_player_by_discord(interaction.user.id)
        if not player_stat:
            await interaction.followup.send("❌ Your Discord account is not linked to any Palworld character. Please link it in-game or contact an admin.", ephemeral=True)
            return

        steam_id = player_stat['steam_id']
        player_name = player_stat['player_name']
        prize_type = data["prize_type"]
        prize_name = data["prize_name"]

        # 3. Check if player is online
        is_online = False
        if rest_api.is_configured():
            player_list = await rest_api.get_player_list()
            if player_list and 'players' in player_list:
                for p in player_list['players']:
                    # Use both account name and potential playerId/userId fields
                    if p.get('userId') == steam_id or p.get('playerId') == steam_id or p.get('name') == player_name:
                        is_online = True
                        break
        
        if not is_online:
            await interaction.followup.send("⚠️ You must be **ONLINE** on the server to claim your reward. Please log in and try again!", ephemeral=True)
            return

        # 4. Give Reward
        success = False
        if prize_type.lower() == "kit":
            kit = kit_system.get_kit(prize_name)
            if kit:
                results = []
                for item_id, amt in kit['items'].items():
                    res_bool, res_msg = await rcon_util.give_item(steam_id, item_id, amt)
                    results.append(res_bool)
                success = any(results)
        elif prize_type.lower() == "pal":
            success, resp = await rcon_util.give_pal_template(steam_id, prize_name)
        elif prize_type.lower() == "paldogs":
            try:
                amount = int(prize_name)
                await db.add_palmarks(steam_id, amount, f"Giveaway Winner")
                success = True
            except Exception as e:
                logging.error(f"Error giving paldogs giveaway prize: {e}")
                success = False

        if success:
            giveaway_data.mark_claimed(gid, interaction.user.id)
            await interaction.followup.send(f"✅ Successfully claimed your **{prize_name}**! Check your inventory/Palbox in-game.", ephemeral=True)
            # Try to update the message to remove button
            try:
                await interaction.edit_original_message(content="✅ **Reward Claimed!** Enjoy your prize!", view=None)
            except:
                pass
        else:
            await interaction.followup.send("❌ Failed to deliver the reward. Please ensure you have space in your inventory/Palbox or contact an admin.", ephemeral=True)

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    def is_admin(self, interaction: nextcord.Interaction):
        admin_id = config.get('admin_user_id', 0)
        return interaction.user.id == admin_id or (hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator)

    @nextcord.slash_command(name="giveaway", description="View active giveaways")
    async def giveaway_group(self, interaction: nextcord.Interaction):
        pass

    @nextcord.slash_command(
        name="giveaway_admin", 
        description="Admin giveaway management",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def giveaway_admin_group(self, interaction: nextcord.Interaction):
        pass

    @giveaway_admin_group.subcommand(name="create", description="Start a new giveaway")
    async def create_giveaway(
        self,
        interaction: nextcord.Interaction,
        duration_mins: int = nextcord.SlashOption(description="Duration in minutes", min_value=1),
        prize_type: str = nextcord.SlashOption(description="Type of prize", choices={"PalDogs": "paldogs", "Kit": "kit", "Pal": "pal"}),
        prize_name: str = nextcord.SlashOption(description="Name of kit/pal or PalDogs amount", autocomplete=True),
        winners_count: int = nextcord.SlashOption(description="Number of winners", min_value=1, default=1),
        min_participants: int = nextcord.SlashOption(description="Minimum participants required", min_value=0, default=0)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        # Validate prize
        if prize_type == "kit":
            if not kit_system.get_kit(prize_name):
                await interaction.response.send_message(f"❌ Kit '{prize_name}' not found.", ephemeral=True)
                return
        elif prize_type == "pal":
            if not pal_system.get_pal(prize_name):
                await interaction.response.send_message(f"❌ Custom Pal '{prize_name}' not found.", ephemeral=True)
                return
        elif prize_type == "paldogs":
            if not prize_name.isdigit():
                await interaction.response.send_message(f"❌ PalDogs amount must be a number.", ephemeral=True)
                return

        end_time = datetime.now() + timedelta(minutes=duration_mins)
        
        embed = nextcord.Embed(
            title="🎁 SPECIAL GIVEAWAY 🎁",
            description=(
                f"Prize: **{prize_name}** ({prize_type.title()})\n"
                f"Winners: **{winners_count}**\n"
                f"Participants: **0**\n"
                f"Min Participants: **{min_participants}**\n"
                f"Ends: <t:{int(end_time.timestamp())}:R> (<t:{int(end_time.timestamp())}:f>)"
            ),
            color=0x00FF88
        )
        embed.set_footer(text="Click the button below to join! • Winners must be online to claim.")
        
        await interaction.response.send_message(f"✅ Giveaway for **{prize_name}** started!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=GiveawayJoinView())
        
        giveaway_data.create_giveaway(msg.id, interaction.channel.id, prize_type, prize_name, end_time, winners_count, min_participants)

    @create_giveaway.on_autocomplete("prize_name")
    async def prize_name_autocomplete(self, interaction: nextcord.Interaction, current: str):
        # Determine prize_type from other options
        options = interaction.data.get('options', [{}])[0].get('options', [])
        prize_type = next((opt['value'] for opt in options if opt['name'] == 'prize_type'), "kit")
        
        if prize_type == "kit":
            choices = [k for k in kit_system.get_all_kit_names() if current.lower() in k.lower()]
        elif prize_type == "pal":
            choices = [p for p in pal_system.get_all_pal_names() if current.lower() in p.lower()]
        elif prize_type == "paldogs":
            suggestions = ["500", "1000", "5000", "10000", "25000", "50000"]
            choices = [s for s in suggestions if current in s]
            if not choices and current.isdigit():
                choices = [current]
        else:
            choices = []
        await interaction.response.send_autocomplete(choices[:25])

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        active = giveaway_data.get_active_giveaways()
        now = datetime.now()

        for msg_id, data in active.items():
            try:
                end_time = datetime.fromisoformat(data["end_time"])
                if now >= end_time:
                    await self.end_giveaway(msg_id)
            except Exception as e:
                logging.error(f"Error checking giveaway {msg_id}: {e}")

    async def end_giveaway(self, msg_id):
        data = giveaway_data.get_giveaway(msg_id)
        if not data or data["is_ended"]:
            return

        channel = self.bot.get_channel(data["channel_id"])
        if not channel:
            try:
                channel = await self.bot.fetch_channel(data["channel_id"])
            except:
                logging.warning(f"Could not find channel {data['channel_id']} for giveaway {msg_id}")
                return

        try:
            message = await channel.fetch_message(int(msg_id))
        except:
            logging.warning(f"Could not find message {msg_id} for giveaway")
            message = None

        participants = data["participants"]
        winners_count = data["winners_count"]
        min_participants = data.get("min_participants", 0)
        
        if len(participants) < min_participants:
            if message:
                embed = nextcord.Embed(
                    title="🎁 GIVEAWAY CANCELLED 🎁",
                    description=f"Prize: **{data['prize_name']}**\nReason: Did not reach the minimum requirement of **{min_participants}** players.",
                    color=0xFF0000
                )
                await message.edit(embed=embed, view=None)
            giveaway_data.end_giveaway(msg_id, [])
            return

        if not participants:
            if message:
                embed = nextcord.Embed(
                    title="🎁 GIVEAWAY ENDED 🎁",
                    description=f"Prize: **{data['prize_name']}**\nNo one participated. 😢",
                    color=0xFF0000
                )
                await message.edit(embed=embed, view=None)
            giveaway_data.end_giveaway(msg_id, [])
            return

        winners = random.sample(participants, min(len(participants), winners_count))
        winner_mentions = ", ".join([f"<@{w}>" for w in winners])
        
        if message:
            embed = nextcord.Embed(
                title="🎁 GIVEAWAY ENDED 🎁",
                description=(
                    f"Prize: **{data['prize_name']}**\n"
                    f"Participants: **{len(participants)}**\n"
                    f"Winners: {winner_mentions}"
                ),
                color=0xFFFF00
            )
            await message.edit(embed=embed, view=None)
        
        await channel.send(f"🎉 Congratulations {winner_mentions}! You won the **{data['prize_name']}**! Check your DMs to claim your prize.")
        
        giveaway_data.end_giveaway(msg_id, winners)

        # Notify winners via DM
        for winner_id in winners:
            try:
                user = await self.bot.fetch_user(int(winner_id))
                if user:
                    dm_embed = nextcord.Embed(
                        title="🏆 YOU WON A GIVEAWAY! 🏆",
                        description=(
                            f"Congratulations! You won **{data['prize_name']}** {f'({data['prize_type'].title()})' if data['prize_type'] != 'paldogs' else 'PALDOGS'}!\n\n"
                            "**How to claim:**\n"
                            "1. Log in to the Palworld server.\n"
                            "2. Click the **Claim Reward** button below.\n"
                            "3. You **MUST** be online in the server to receive your reward."
                        ),
                        color=0x00FF88
                    )
                    await user.send(embed=dm_embed, view=GiveawayClaimView())
            except Exception as e:
                logging.error(f"Failed to send DM to winner {winner_id}: {e}")

    @giveaway_admin_group.subcommand(name="reroll", description="Reroll a winner for an ended giveaway")
    async def reroll_giveaway(
        self, 
        interaction: nextcord.Interaction, 
        message_id: str = nextcord.SlashOption(description="The ID of the giveaway message (copied from message link)")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        data = giveaway_data.get_giveaway(message_id)
        if not data:
            await interaction.response.send_message("❌ Giveaway not found in the database.", ephemeral=True)
            return
            
        if not data["participants"]:
            await interaction.response.send_message("❌ No participants to reroll from.", ephemeral=True)
            return

        winner = random.choice(data["participants"])
        # Add to winners dict if not already there, setting claimed to False
        data["winners"][str(winner)] = False
        giveaway_data.save_data()
        
        await interaction.response.send_message(f"🎉 Reroll complete! New winner: <@{winner}>!")
        
        # Notify winner
        try:
            user = await self.bot.fetch_user(int(winner))
            if user:
                dm_embed = nextcord.Embed(
                    title="🏆 YOU WON A GIVEAWAY (REROLL)! 🏆",
                    description=(
                        f"Congratulations! You won **{data['prize_name']}** {f'({data['prize_type'].title()})' if data['prize_type'] != 'paldogs' else 'PALDOGS'}!\n\n"
                        "**How to claim:**\n"
                        "1. Log in to the Palworld server.\n"
                        "2. Click the **Claim Reward** button below.\n"
                        "3. You **MUST** be online in the server to receive your reward."
                    ),
                    color=0x00FF88
                )
                await user.send(embed=dm_embed, view=GiveawayClaimView())
        except Exception as e:
            logging.error(f"Failed to send DM to reroll winner {winner}: {e}")

    @giveaway_admin_group.subcommand(name="active", description="List all active giveaways")
    async def list_active(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        active = giveaway_data.get_active_giveaways()
        if not active:
            await interaction.response.send_message("📭 No active giveaways at the moment.", ephemeral=True)
            return

        embed = nextcord.Embed(
            title="📊 Active Giveaways",
            color=0x00AAFF,
            timestamp=datetime.now()
        )

        for msg_id, data in active.items():
            end_time = datetime.fromisoformat(data["end_time"])
            participants = len(data.get("participants", []))
            prize = data["prize_name"]
            winners = data["winners_count"]
            
            val = (
                f"Prize: **{prize}**\n"
                f"Winners: **{winners}**\n"
                f"Participants: **{participants}**\n"
                f"Ends: <t:{int(end_time.timestamp())}:R>\n"
                f"Message ID: `{msg_id}`"
            )
            embed.add_field(name=f"ID: {msg_id}", value=val, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @giveaway_admin_group.subcommand(name="delete", description="Delete a giveaway from database")
    async def delete_giveaway(
        self, 
        interaction: nextcord.Interaction, 
        message_id: str = nextcord.SlashOption(description="The ID of the giveaway message to delete")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        data = giveaway_data.get_giveaway(message_id)
        if not data:
            await interaction.response.send_message(f"❌ Giveaway with ID `{message_id}` not found.", ephemeral=True)
            return

        # Attempt to delete the message if it's active
        if not data["is_ended"]:
            try:
                channel = self.bot.get_channel(data["channel_id"])
                if channel:
                    msg = await channel.fetch_message(int(message_id))
                    await msg.delete()
            except:
                pass

        if giveaway_data.delete_giveaway(message_id):
            await interaction.response.send_message(f"✅ Giveaway `{message_id}` has been deleted from the database.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Failed to delete giveaway `{message_id}`.", ephemeral=True)

    @giveaway_admin_group.subcommand(name="show", description="Re-post an active giveaway to the current channel")
    async def show_giveaway(
        self,
        interaction: nextcord.Interaction,
        message_id: str = nextcord.SlashOption(description="The current ID of the giveaway message to show/bump")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return

        data = giveaway_data.get_giveaway(message_id)
        if not data:
            await interaction.response.send_message(f"❌ Giveaway with ID `{message_id}` not found.", ephemeral=True)
            return
        
        if data["is_ended"]:
            await interaction.response.send_message(f"❌ Giveaway `{message_id}` has already ended.", ephemeral=True)
            return

        # Create the embed
        embed = get_giveaway_embed(data)
        
        # Send new message
        new_msg = await interaction.channel.send(embed=embed, view=GiveawayJoinView())
        
        # Update database with new ID
        giveaway_data.update_message_id(message_id, new_msg.id)
        
        await interaction.response.send_message(f"✅ Giveaway re-posted! New Message ID: `{new_msg.id}`", ephemeral=True)
        
        # Try to delete old message to keep it clean
        try:
            channel = self.bot.get_channel(data["channel_id"])
            if channel:
                old_msg = await channel.fetch_message(int(message_id))
                await old_msg.delete()
        except:
            pass
        
        # Update channel ID in data just in case it was moved
        data["channel_id"] = interaction.channel.id
        giveaway_data.save_data()

def setup(bot):
    bot.add_cog(Giveaway(bot))
    print("✅ Giveaway Cog LOADED")
