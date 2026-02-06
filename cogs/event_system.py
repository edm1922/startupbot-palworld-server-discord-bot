import nextcord
import json
import os
from datetime import datetime
from nextcord.ext import commands, tasks
from utils.config_manager import config
from utils.database import db
from utils.rcon_utility import rcon_util
from utils.rest_api import rest_api

EVENT_FILE = "data/events.json"

class EventData:
    def __init__(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filename = os.path.join(root_dir, EVENT_FILE)
        self.events = {}
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    self.events = data.get("events", {})
                    self.manual_timers = data.get("manual_timers", {})
            except Exception as e:
                print(f"Error loading events: {e}")
                self.events = {}
                self.manual_timers = {}
        else:
            self.events = {}
            self.manual_timers = {}

    def save_data(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump({
                    "events": self.events,
                    "manual_timers": self.manual_timers
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving events: {e}")

    def add_manual_timer(self, msg, timestamp):
        timer_id = str(int(datetime.now().timestamp()))
        self.manual_timers[timer_id] = {
            "message": msg,
            "time": timestamp,
            "last_broadcast": None
        }
        self.save_data()
        return timer_id

    def create_event(self, msg_id, name, description, event_time, event_type, creator_id, prize=0):
        self.events[str(msg_id)] = {
            "name": name,
            "description": description,
            "time": event_time,
            "type": event_type,
            "creator_id": creator_id,
            "prize": prize,
            "participants": [],
            "status": "active",
            "winners": [],
            "last_broadcast": None # Track when we last broadcasted for this event
        }
        self.save_data()

    def add_participant(self, msg_id, user_id):
        if str(msg_id) in self.events:
            if user_id not in self.events[str(msg_id)]["participants"]:
                self.events[str(msg_id)]["participants"].append(user_id)
                self.save_data()
                return True
        return False

    def remove_participant(self, msg_id, user_id):
        if str(msg_id) in self.events:
            if user_id in self.events[str(msg_id)]["participants"]:
                self.events[str(msg_id)]["participants"].remove(user_id)
                self.save_data()
                return True
        return False

    def set_winners(self, msg_id, winners):
        if str(msg_id) in self.events:
            self.events[str(msg_id)]["winners"] = winners
            self.events[str(msg_id)]["status"] = "completed"
            self.save_data()

    def delete_event(self, msg_id):
        if str(msg_id) in self.events:
            del self.events[str(msg_id)]
            self.save_data()
            return True
        return False

    def update_event_msg_id(self, old_msg_id, new_msg_id):
        """Update the key for an event in the dictionary (used for bumping)"""
        old_key = str(old_msg_id)
        new_key = str(new_msg_id)
        if old_key in self.events:
            self.events[new_key] = self.events.pop(old_key)
            self.save_data()
            return True
        return False

    def get_event(self, msg_id):
        return self.events.get(str(msg_id))

event_data = EventData()

class EventAddModal(nextcord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Create New Event")
        self.cog = cog
        
        self.name_input = nextcord.ui.TextInput(
            label="Event Name",
            placeholder="e.g. Boss Raid, Racing, PvP Tournament",
            min_length=3,
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)

        self.date_input = nextcord.ui.TextInput(
            label="Date (DD/MM/YYYY)",
            placeholder=f"e.g. {datetime.now().strftime('%d/%m/%Y')}",
            min_length=5,
            max_length=10,
            required=True
        )
        self.add_item(self.date_input)

        self.time_input = nextcord.ui.TextInput(
            label="Time (HH:MM - 24hr format)",
            placeholder="e.g. 22:00 (for 10 PM)",
            min_length=4,
            max_length=5,
            required=True
        )
        self.add_item(self.time_input)

        self.desc_input = nextcord.ui.TextInput(
            label="Description",
            style=nextcord.TextInputStyle.paragraph,
            placeholder="Describe the event, rules, and rewards...",
            min_length=10,
            max_length=1000,
            required=True
        )
        self.add_item(self.desc_input)

        self.prize_input = nextcord.ui.TextInput(
            label="PALDOGS Prize (Optional)",
            placeholder="e.g. 5000",
            required=False
        )
        self.add_item(self.prize_input)

    async def callback(self, interaction: nextcord.Interaction):
        # Handle details in event_add subcommand override
        pass

def format_participants(participants, event_type):
    if not participants:
        return "No one yet!"
    
    mentions = [f"<@{uid}>" for uid in participants]
    
    if event_type == "solo":
        return "\n".join(mentions)
    else: # Duo
        teams = []
        for i in range(0, len(mentions), 2):
            p1 = mentions[i]
            p2 = mentions[i+1] if i+1 < len(mentions) else "*(Waiting for partner...)*"
            teams.append(f"**Team {len(teams)+1}:** {p1} & {p2}")
        return "\n".join(teams)

class DuoPartnerSelectView(nextcord.ui.View):
    def __init__(self, msg_id, original_interaction):
        super().__init__(timeout=60)
        self.msg_id = msg_id
        self.original_interaction = original_interaction

    @nextcord.ui.user_select(placeholder="Select your teammate...")
    async def select_partner(self, select: nextcord.ui.UserSelect, interaction: nextcord.Interaction):
        partner = select.values[0]
        initiator = interaction.user
        
        if partner.id == initiator.id:
            await interaction.response.send_message("❌ You cannot be your own partner!", ephemeral=True)
            return

        if partner.bot:
            await interaction.response.send_message("❌ You cannot team up with a bot!", ephemeral=True)
            return

        data = event_data.get_event(self.msg_id)
        if not data:
            await interaction.response.send_message("❌ Event no longer exists.", ephemeral=True)
            return

        # Check if either is already in
        if initiator.id in data["participants"]:
            await interaction.response.send_message("❌ You are already in this event! Leave first to change teams.", ephemeral=True)
            return
        
        if partner.id in data["participants"]:
            await interaction.response.send_message(f"❌ {partner.display_name} is already in a team!", ephemeral=True)
            return

        # Add both
        event_data.add_participant(self.msg_id, initiator.id)
        event_data.add_participant(self.msg_id, partner.id)
        
        # Update main message
        try:
            msg = await interaction.channel.fetch_message(int(self.msg_id))
            embed = msg.embeds[0]
            participant_list = format_participants(data["participants"], data["type"])
            for i, field in enumerate(embed.fields):
                if "Teams" in field.name:
                    embed.set_field_at(i, name="👥 Teams", value=participant_list, inline=False)
                    break
            await msg.edit(embed=embed)
        except:
            pass

        await interaction.response.send_message(f"✅ Team Registered: {initiator.mention} & {partner.mention}!", ephemeral=True)
        self.stop()

class EventView(nextcord.ui.View):
    def __init__(self, msg_id=None):
        super().__init__(timeout=None)
        self.msg_id = msg_id

    @nextcord.ui.button(label="Participate", style=nextcord.ButtonStyle.success, custom_id="event_participate")
    async def participate(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        msg_id = interaction.message.id
        data = event_data.get_event(msg_id)
        
        if not data:
            await interaction.response.send_message("❌ This event is no longer active.", ephemeral=True)
            return

        is_joined = interaction.user.id in data["participants"]

        if data["type"] == "duo":
            if not is_joined:
                # Need to pick partner
                view = DuoPartnerSelectView(msg_id, interaction)
                await interaction.response.send_message("To join this Duo event, please select your partner below:", view=view, ephemeral=True)
            else:
                # Leave - For Duo, we remove the whole team to be safe
                parts = data["participants"]
                idx = parts.index(interaction.user.id)
                
                # Find the partner
                partner_id = None
                if idx % 2 == 0: # User is P1
                    if idx + 1 < len(parts):
                        partner_id = parts[idx+1]
                else: # User is P2
                    partner_id = parts[idx-1]
                
                event_data.remove_participant(msg_id, interaction.user.id)
                if partner_id:
                    event_data.remove_participant(msg_id, partner_id)
                
                await interaction.response.send_message("❌ You and your partner have withdrawn from the duo event.", ephemeral=True)
                
                # Update embed
                msg = interaction.message
                embed = msg.embeds[0]
                participant_list = format_participants(data["participants"], data["type"])
                for i, field in enumerate(embed.fields):
                    if "Teams" in field.name:
                        embed.set_field_at(i, name="👥 Teams", value=participant_list, inline=False)
                        break
                await msg.edit(embed=embed)
        else: # Solo
            if not is_joined:
                event_data.add_participant(msg_id, interaction.user.id)
                await interaction.response.send_message("✅ You are now participating!", ephemeral=True)
            else:
                event_data.remove_participant(msg_id, interaction.user.id)
                await interaction.response.send_message("❌ You have withdrawn from the event.", ephemeral=True)
            
            # Update embed
            embed = interaction.message.embeds[0]
            participant_list = format_participants(data["participants"], data["type"])
            for i, field in enumerate(embed.fields):
                if "Participants" in field.name:
                    embed.set_field_at(i, name="📝 Participants", value=participant_list, inline=False)
                    break
            await interaction.message.edit(embed=embed)

class EventWinnerDropdown(nextcord.ui.Select):
    def __init__(self, msg_id, participants, prize):
        self.msg_id = msg_id
        self.prize = prize
        options = []
        for p_id in participants[:25]: # Limit to 25
            options.append(nextcord.SelectOption(label=f"User ID: {p_id}", value=str(p_id)))
        
        super().__init__(placeholder="Select the winner...", options=options, custom_id="event_select_winner")

    async def callback(self, interaction: nextcord.Interaction):
        winner_id = int(self.values[0])
        event_data.set_winners(self.msg_id, [winner_id])
        
        # Award prize if any
        award_msg = ""
        if self.prize > 0:
            player = await db.get_player_by_discord(winner_id)
            if player:
                await db.add_palmarks(player['steam_id'], self.prize, f"Won Event: {event_data.get_event(self.msg_id)['name']}")
                award_msg = f"\n🏆 **{self.prize} PALDOGS** have been added to their balance!"
            else:
                award_msg = f"\n⚠️ User not linked to Steam, could not award PALDOGS automatically."

        event_info = event_data.get_event(self.msg_id)
        embed = nextcord.Embed(
            title="🎉 Event Winner Announced!",
            description=f"Congratulations to <@{winner_id}> for winning the **{event_info['name']}**!{award_msg}",
            color=0xF1C40F
        )
        embed.set_thumbnail(url="https://i.imgur.com/vH3m2r7.png") # Trophy icon placeholder
        
        await interaction.response.send_message(embed=embed)
        
        # Disable buttons on the original message
        try:
            msg = await interaction.channel.fetch_message(int(self.msg_id))
            await msg.edit(view=None)
        except:
            pass

class EventWinnerView(nextcord.ui.View):
    def __init__(self, msg_id, participants, prize):
        super().__init__(timeout=60)
        self.add_item(EventWinnerDropdown(msg_id, participants, prize))

class EventSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_event_timers.start()

    def cog_unload(self):
        self.check_event_timers.cancel()

    def is_admin(self, interaction: nextcord.Interaction):
        admin_id = config.get('admin_user_id', 0)
        if interaction.user.id == admin_id:
            return True
        if hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator:
            return True
        return False

    @tasks.loop(seconds=60)
    async def check_event_timers(self):
        """Check events and manual timers to broadcast in-game messages"""
        now = datetime.now().timestamp()
        
        milestones = {
            1800: "30 minutes",
            900: "15 minutes",
            300: "5 minutes",
            60: "1 minute",
            0: "is STARTING NOW!"
        }

        # 1. Check Events
        for msg_id, info in list(event_data.events.items()):
            if info["status"] != "active":
                continue
                
            time_until = info["time"] - now
            for threshold, label in milestones.items():
                if threshold <= time_until < threshold + 60:
                    if info.get("last_broadcast") != threshold:
                        msg = f"[EVENT] '{info['name']}' {'starts in ' + label if threshold > 0 else label}"
                        await rcon_util.broadcast(msg)
                        info["last_broadcast"] = threshold
                        event_data.save_data()
            
            if time_until < -300: # 5 mins past
                pass

        # 2. Check Manual Timers
        for t_id, t_info in list(event_data.manual_timers.items()):
            time_until = t_info["time"] - now
            
            if time_until < -60: # Delete old timers
                del event_data.manual_timers[t_id]
                event_data.save_data()
                continue

            for threshold, label in milestones.items():
                if threshold <= time_until < threshold + 60:
                    if t_info.get("last_broadcast") != threshold:
                        msg = f"[TIMER] {t_info['message']} {'in ' + label if threshold > 0 else label}"
                        await rcon_util.broadcast(msg)
                        t_info["last_broadcast"] = threshold
                        event_data.save_data()

    @nextcord.slash_command(name="timer", description="Quick in-game manual timers")
    async def timer_group(self, interaction: nextcord.Interaction):
        pass

    @timer_group.subcommand(name="set", description="Set a manual in-game countdown")
    async def timer_set(
        self,
        interaction: nextcord.Interaction,
        minutes: int = nextcord.SlashOption(description="Minutes from now", min_value=1, max_value=1440),
        message: str = nextcord.SlashOption(description="Reason for the timer", default="Attention!")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        target_time = int(datetime.now().timestamp() + (minutes * 60))
        t_id = event_data.add_manual_timer(message, target_time)
        
        await interaction.response.send_message(
            f"✅ **Timer Set!**\n"
            f"**Message:** `{message}`\n"
            f"**Triggers:** In-game chat at 30m, 15m, 5m, 1m, and 0s.\n"
            f"**Time:** <t:{target_time}:T> (<t:{target_time}:R>)\n"
            f"**ID:** `{t_id}`",
            ephemeral=True
        )
        
        # Initial broadcast
        await rcon_util.broadcast(f"[TIMER] '{message}' has been set for {minutes} minutes from now.")

    @timer_group.subcommand(name="list", description="Show all active events and manual timers")
    async def timer_list(self, interaction: nextcord.Interaction):
        now = datetime.now().timestamp()
        
        embed = nextcord.Embed(title="⏰ Active Timers & Countdown", color=0x3498DB)
        
        # Manual Timers
        manual_list = []
        for t_id, t_info in event_data.manual_timers.items():
            diff = t_info["time"] - now
            if diff > 0:
                manual_list.append(f"• `{t_id}`: **{t_info['message']}** - <t:{int(t_info['time'])}:R>")
        
        embed.add_field(name="📌 Manual Timers", value="\n".join(manual_list) if manual_list else "None", inline=False)
        
        # Events
        event_list = []
        for e_id, e_info in event_data.events.items():
            if e_info["status"] == "active":
                event_list.append(f"• **{e_info['name']}** - <t:{int(e_info['time'])}:R>")
        
        embed.add_field(name="📅 Scheduled Events", value="\n".join(event_list) if event_list else "None", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @timer_group.subcommand(name="cancel", description="Cancel a manual timer")
    async def timer_cancel(self, interaction: nextcord.Interaction, timer_id: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        if timer_id in event_data.manual_timers:
            del event_data.manual_timers[timer_id]
            event_data.save_data()
            await interaction.response.send_message(f"✅ Timer `{timer_id}` cancelled.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Timer ID not found. Use `/timer list` to find IDs.", ephemeral=True)

    @nextcord.slash_command(name="event", description="Event management commands")
    async def event_group(self, interaction: nextcord.Interaction):
        pass

    @event_group.subcommand(name="add", description="Create a new server event")
    async def event_add(
        self, 
        interaction: nextcord.Interaction,
        event_type: str = nextcord.SlashOption(
            name="type",
            choices={"Solo": "solo", "Duo": "duo"},
            required=True
        )
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permissions denied.", ephemeral=True)
            return

        # Modal for details
        modal = EventAddModal(self)
        
        # Override callback to handle local data
        async def modal_callback(modal_interaction: nextcord.Interaction):
            name = modal.name_input.value
            date_str = modal.date_input.value
            time_str = modal.time_input.value
            desc = modal.desc_input.value
            prize_str = modal.prize_input.value
            
            prize = 0
            if prize_str.isdigit():
                prize = int(prize_str)

            # Traditional Date Parser
            try:
                # Combine Date and Time
                full_time_str = f"{date_str} {time_str}"
                # Handle DD/MM/YYYY or DD/MM
                fmt = "%d/%m/%Y %H:%M"
                if len(date_str.split('/')) == 2:
                    full_time_str = f"{date_str}/{datetime.now().year} {time_str}"
                
                dt_obj = datetime.strptime(full_time_str, fmt)
                timestamp = int(dt_obj.timestamp())
            except Exception as e:
                await modal_interaction.response.send_message(f"❌ **Invalid Date Format!**\nPlease use `DD/MM/YYYY` (e.g., 03/02/2026) and `HH:MM` (e.g., 22:00).", ephemeral=True)
                return

            embed = nextcord.Embed(
                title=f"📅 New Event: {name}",
                description=desc,
                color=0x3498DB
            )
            embed.add_field(name="🕒 Time", value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)", inline=False)
            embed.add_field(name="👥 Type", value=event_type.capitalize(), inline=True)
            embed.add_field(name="💰 Prize", value=f"{prize} PALDOGS" if prize > 0 else "Bragging Rights", inline=True)
            
            p_name = "👥 Teams" if event_type == "duo" else "📝 Participants"
            embed.add_field(name=p_name, value="No one yet!", inline=False)
            embed.set_footer(text=f"Hosted by {modal_interaction.user.display_name}")
            
            await modal_interaction.response.send_message("Creating event...", ephemeral=True)
            msg = await modal_interaction.channel.send(embed=embed)
            
            # Start view
            view = EventView(msg.id)
            await msg.edit(view=view)
            
            # Save data
            event_data.create_event(msg.id, name, desc, timestamp, event_type, modal_interaction.user.id, prize)
            
            # Initial in-game announcement
            await rcon_util.broadcast(f"[EVENT] New Event Created: '{name}'! Use /event list in Discord to join!")

        modal.callback = modal_callback
        await interaction.response.send_modal(modal)

    @event_group.subcommand(name="refresh", description="Fix/Update an event message (adds missing buttons)")
    async def event_refresh(
        self,
        interaction: nextcord.Interaction,
        event_id: str = nextcord.SlashOption(description="The Message ID of the event")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permissions denied.", ephemeral=True)
            return

        data = event_data.get_event(event_id)
        if not data:
            await interaction.response.send_message("❌ Event ID not found in database.", ephemeral=True)
            return

        try:
            msg = await interaction.channel.fetch_message(int(event_id))
            
            # Update embed to ensure it matched DB
            embed = msg.embeds[0]
            participant_list = format_participants(data["participants"], data["type"])
            
            # Ensure correct fields exist
            found = False
            for i, field in enumerate(embed.fields):
                if "Participants" in field.name or "Teams" in field.name:
                    name = "👥 Teams" if data["type"] == "duo" else "📝 Participants"
                    embed.set_field_at(i, name=name, value=participant_list, inline=False)
                    found = True
                    break
            
            if not found:
                 name = "👥 Teams" if data["type"] == "duo" else "📝 Participants"
                 embed.add_field(name=name, value=participant_list, inline=False)

            # Re-attach the view (The Button)
            view = EventView(event_id)
            await msg.edit(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Event `{event_id}` has been refreshed and buttons restored!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Could not find or edit the original message. Error: {e}", ephemeral=True)

    @event_group.subcommand(name="bump", description="Re-post an event to bring it to the bottom of the chat")
    async def event_bump(
        self,
        interaction: nextcord.Interaction,
        event_id: str = nextcord.SlashOption(description="The Message ID of the event")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permissions denied.", ephemeral=True)
            return

        data = event_data.get_event(event_id)
        if not data:
            await interaction.response.send_message("❌ Event ID not found in database.", ephemeral=True)
            return

        try:
            # 1. Fetch old message to get current embed state
            old_msg = None
            try:
                old_msg = await interaction.channel.fetch_message(int(event_id))
            except:
                pass

            # 2. Prepare the new message content
            if old_msg:
                # Use existing embed to preserve formatting/participant list exactly
                embed = old_msg.embeds[0]
            else:
                # If old message is gone, rebuild embed from DB
                timestamp = int(data["time"])
                embed = nextcord.Embed(
                    title=f"📅 Event: {data['name']}",
                    description=data["description"],
                    color=0x3498DB
                )
                embed.add_field(name="🕒 Time", value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)", inline=False)
                embed.add_field(name="👥 Type", value=data["type"].capitalize(), inline=True)
                embed.add_field(name="💰 Prize", value=f"{data['prize']} PALDOGS" if data['prize'] > 0 else "Bragging Rights", inline=True)
                
                p_name = "👥 Teams" if data["type"] == "duo" else "📝 Participants"
                participant_list = format_participants(data["participants"], data["type"])
                embed.add_field(name=p_name, value=participant_list, inline=False)
                embed.set_footer(text="Bumped Event")

            # 3. Post the new message
            new_msg = await interaction.channel.send(embed=embed, view=EventView(event_id))

            # 4. Update the DB with the new Message ID
            if event_data.update_event_msg_id(event_id, new_msg.id):
                # Update the view attached to the NEW message to use the NEW ID internally
                await new_msg.edit(view=EventView(new_msg.id))
                
                # 5. Delete the old message if it exists
                if old_msg:
                    try: await old_msg.delete()
                    except: pass
                
                await interaction.response.send_message(f"✅ Event bumped! Old ID: `{event_id}` -> New ID: `{new_msg.id}`", ephemeral=True)
            else:
                # If DB update fails, delete the new message we just sent to avoid orphaned data
                await new_msg.delete()
                await interaction.response.send_message("❌ Failed to update database with new Message ID. Bump aborted.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error during bump: {e}", ephemeral=True)

    @event_group.subcommand(name="broadcast", description="Send a custom in-game message to everyone")
    async def event_broadcast(
        self,
        interaction: nextcord.Interaction,
        message: str = nextcord.SlashOption(description="The message to broadcast in-game")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permissions denied.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        success = await rcon_util.broadcast(f"[ADMIN] {message}")
        if success:
            await interaction.followup.send(f"✅ Broadcast sent: `{message}`")
        else:
            await interaction.followup.send("❌ Failed to send broadcast. Check RCON/API status.")

    @event_group.subcommand(name="delete", description="Cancel an active event")
    async def event_delete(
        self,
        interaction: nextcord.Interaction,
        event_id: str = nextcord.SlashOption(description="The Message ID of the event")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permissions denied.", ephemeral=True)
            return

        if event_data.delete_event(event_id):
            try:
                msg = await interaction.channel.fetch_message(int(event_id))
                await msg.delete()
            except:
                pass
            await interaction.response.send_message(f"✅ Event `{event_id}` has been deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Event ID not found.", ephemeral=True)

    @event_group.subcommand(name="modify", description="Modify an event or announce winner")
    async def event_modify(
        self,
        interaction: nextcord.Interaction,
        event_id: str = nextcord.SlashOption(description="The Message ID of the event", required=True),
        action: str = nextcord.SlashOption(
            choices={"Announce Winner": "winner", "Update Time": "time"},
            required=True
        ),
        new_value: str = nextcord.SlashOption(description="New value (if updating time)", required=False)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permissions denied.", ephemeral=True)
            return

        data = event_data.get_event(event_id)
        if not data:
            await interaction.response.send_message("❌ Event ID not found.", ephemeral=True)
            return

        if action == "winner":
            if not data["participants"]:
                await interaction.response.send_message("❌ No participants registered for this event.", ephemeral=True)
                return
            
            view = EventWinnerView(event_id, data["participants"], data["prize"])
            await interaction.response.send_message(f"Select a winner for **{data['name']}**:", view=view, ephemeral=True)

        elif action == "time":
            if not new_value:
                await interaction.response.send_message("❌ Please provide a new time. Examples: `in 2 hours`, `in 30 minutes`, or a Unix Timestamp.", ephemeral=True)
                return
            
            try:
                new_ts = 0
                val_lower = new_value.lower()
                
                if val_lower.startswith("in "):
                    parts = val_lower.split()
                    if len(parts) >= 3:
                        amount = int(parts[1])
                        unit = parts[2]
                        
                        now = datetime.now().timestamp()
                        if "min" in unit:
                            new_ts = int(now + amount * 60)
                        elif "hour" in unit:
                            new_ts = int(now + amount * 3600)
                        elif "day" in unit:
                            new_ts = int(now + amount * 86400)
                        else:
                            new_ts = int(now + amount * 3600) # Default to hours
                    else:
                        raise ValueError("Invalid 'in' format")
                elif new_value.isdigit():
                    new_ts = int(new_value)
                    # If they entered a small number like '10', assume they meant 'in 10 hours'
                    if new_ts < 1000000: 
                        new_ts = int(datetime.now().timestamp() + new_ts * 3600)
                else:
                    raise ValueError("Unknown format")

                data["time"] = new_ts
                data["last_broadcast"] = None # Reset broadcast tracker
                event_data.save_data()
                
                # Update original message
                try:
                    msg = await interaction.channel.fetch_message(int(event_id))
                    embed = msg.embeds[0]
                    for i, field in enumerate(embed.fields):
                        if "Time" in field.name:
                            embed.set_field_at(i, name="🕒 Time", value=f"<t:{new_ts}:F> (<t:{new_ts}:R>)", inline=False)
                            break
                    await msg.edit(embed=embed)
                    await interaction.response.send_message(f"✅ Event time updated! New time: <t:{new_ts}:F>", ephemeral=True)
                except:
                    await interaction.response.send_message(f"✅ Data updated in database, but could not edit original message. New time: <t:{new_ts}:F>", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message("❌ **Invalid time format!**\n\n**Try these:**\n• `in 2 hours`\n• `in 45 minutes`\n• `in 1 day`\n• A Unix Timestamp (e.g. `1738580000`)", ephemeral=True)

    @event_group.subcommand(name="list", description="List all active events")
    async def event_list(self, interaction: nextcord.Interaction):
        active_events = {k: v for k, v in event_data.events.items() if v["status"] == "active"}
        
        if not active_events:
            await interaction.response.send_message("No active events found.", ephemeral=True)
            return

        embed = nextcord.Embed(title="📅 Active Events", color=0x34495E)
        for e_id, e_info in active_events.items():
            embed.add_field(
                name=e_info['name'],
                value=f"ID: `{e_id}`\nTime: <t:{e_info['time']}:R>\nType: {e_info['type'].capitalize()}\nParticipants: {len(e_info['participants'])}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(EventSystem(bot))
