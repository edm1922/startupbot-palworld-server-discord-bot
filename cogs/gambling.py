import nextcord
from nextcord.ext import commands, tasks
from nextcord.ui import View, Button, Modal, TextInput
import random
import asyncio
import json
import os
import time
from utils.database import db
from utils.rcon_utility import rcon_util
from utils.rest_api import rest_api
from utils.config_manager import config
from cogs.rank_system import rank_system
from cogs.pal_system import pal_system

class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rewards_file = os.path.join("data", "gambling_rewards.json")
        self.rewards = {"wheel": [], "spin_cost": 500}
        self.load_rewards()
        
        from utils.config_manager import config
        self.table_message_id = config.get('gambling_table_message_id')
        self.table_message = None
        self.last_results = []
        self.recent_activity = [] # [ {"user": "User", "prize": "Prize", "time": timestamp} ]
        self.is_spinning = False
        self.burst_tracker = {}
        self.burst_cfg = {"max_rolls": 3, "cooldown_seconds": 60}
        self.global_roll_count = 0
        self.global_cooldown_until = 0
        self.spin_lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent view once bot is ready
        self.bot.add_view(LuckyWheelView(self))
        print("🎰 Gambling Cog: Lucky Wheel persistent view registered.")

    def load_rewards(self):
        if os.path.exists(self.rewards_file):
            try:
                with open(self.rewards_file, "r", encoding='utf-8') as f:
                    self.rewards = json.load(f)
            except Exception as e:
                print(f"❌ Error loading gambling rewards: {e}")
        else:
            self.rewards = {
                "wheel": [
                    {"id": "PALDOGS_SMALL", "name": "500 PALDOGS", "type": "currency", "amount": 500, "weight": 50}
                ], 
                "spin_cost": 500,
                "daily_limit": 25,
                "last_grand_winner": "None",
                "last_grand_prize": "None"
            }

    def save_rewards(self):
        try:
            with open(self.rewards_file, "w", encoding='utf-8') as f:
                json.dump(self.rewards, f, indent=4)
        except Exception as e:
            print(f"❌ Error saving gambling rewards: {e}")

    @nextcord.slash_command(
        name="gamble", 
        description="Casino games",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def gamble_group(self, interaction: nextcord.Interaction):
        pass

    @gamble_group.subcommand(name="wheel", description="🎰 Spin the Lucky Wheel!")
    async def spin_wheel_command(self, interaction: nextcord.Interaction):
        await self.process_wheel_spin(interaction)

    async def process_wheel_spin(self, interaction: nextcord.Interaction):
        # 1. Immediate Defer to avoid "Interaction failed"
        try:
            await interaction.response.defer(ephemeral=False)
        except:
            return

        now = time.time()
        user_id = interaction.user.id
        
        # 2. Global Cooldown Check
        global_max = 10
        global_cd = 60
        if now < self.global_cooldown_until:
            remaining = int(self.global_cooldown_until - now)
            await interaction.followup.send(f"⌛ **GLOBAL REST PERIOD!** The bot is resting.\nPlease try again in **{remaining}** seconds.", ephemeral=True)
            return

        # 3. Fast Stats/Link Checks
        stats = await db.get_player_by_discord(user_id)
        if not stats:
            await interaction.followup.send("❌ Link your account first with `/link`!", ephemeral=True)
            return

        from utils.config_manager import config
        gambling_channel_id = config.get('gambling_channel_id')
        if gambling_channel_id and interaction.channel_id != gambling_channel_id:
            await interaction.followup.send(f"⚠️ This command can only be used in <#{gambling_channel_id}>!", ephemeral=True)
            return

        steam_id = stats['steam_id']
        base_cost = self.rewards.get('spin_cost', 500)
        wheel_level = await db.get_wheel_level(steam_id)
        current_cost = base_cost + (wheel_level * 250)
        
        if stats['palmarks'] < current_cost:
            await interaction.followup.send(
                f"❌ You need **{current_cost:,} PALDOGS** for your next spin! (Current Level: {wheel_level})\n"
                f"💡 *Use the **[ 🔄 Reset Progress ]** button below to return to the 500 cost.*", 
                ephemeral=True
            )
            return

        # 4. Daily Limit Check
        daily_count = await db.get_daily_usage(steam_id, 'wheel_spins')
        daily_limit = self.rewards.get('daily_limit', 25)
        if daily_count >= daily_limit:
            await interaction.followup.send(f"⚠️ **DAILY LIMIT REACHED!** You have already spun the wheel **{daily_limit}** times today.", ephemeral=True)
            return

        # 5. Lock and Spin
        if self.spin_lock.locked():
             await interaction.followup.send("⚠️ The wheel is busy with another player! Please wait a moment.", ephemeral=True)
             return

        async with self.spin_lock:
            try:
                self.is_spinning = True
                
                # Deduct cost first
                await db.add_palmarks(steam_id, -current_cost, f"Spin the Wheel (Level {wheel_level})")
                
                # Update trackers
                tracker = self.burst_tracker.get(user_id, {"count": 0, "cooldown_until": 0})
                tracker["count"] += 1
                if tracker["count"] >= self.burst_cfg['max_rolls']:
                    tracker["cooldown_until"] = now + self.burst_cfg['cooldown_seconds']
                    tracker["count"] = 0
                self.burst_tracker[user_id] = tracker

                self.global_roll_count += 1
                if self.global_roll_count >= global_max:
                    self.global_cooldown_until = now + global_cd
                    self.global_roll_count = 0
                    asyncio.create_task(rcon_util.broadcast("💤 [CASINO] WHEEL LIMIT REACHED. RESTING..."))

                # Increment daily spins and progressive level
                await db.increment_daily_usage(steam_id, 'wheel_spins')
                await db.increment_wheel_level(steam_id)

                # Start the animation
                embed = nextcord.Embed(title="🎰 Lucky Wheel - Spinning...", color=0xFFD700)
                embed.description = "🔄 *The wheel is starting to turn...*"
                embed.set_image(url="https://media1.tenor.com/m/HGpVsyfgOgMAAAAC/wheel-of.gif")
                msg = await interaction.followup.send(embed=embed)

                current_multiplier = 1
                spin_round = 1
                
                # Display luck bonus if applicable
                luck_text = f"\n✨ **Luck Bonus:** +{wheel_level * 0.2:.1f} per Legend!" if wheel_level > 0 else ""
                
                while True:
                    # Animation frames
                    frames = ["🔴 🟡 🟢 🔵 🟣", "🟣 🔴 🟡 🟢 🔵", "🔵 🟣 🔴 🟡 🟢", " 🔵 🟣 🔴 🟡", " 🟢 🔵 🟣 🔴"]
                    spin_label = "RE-SPINNING" if spin_round > 1 else "SPINNING"
                    multi_text = f"  **x{current_multiplier} BOOST ACTIVE!**" if current_multiplier > 1 else ""
                    
                    for i in range(3):
                        embed.description = f"🔄 **{spin_label}** 🔄{multi_text}{luck_text}\n`{frames[i % len(frames)]}`"
                        await msg.edit(embed=embed)
                        await asyncio.sleep(1)

                    # Roll result with progression bonus
                    prizes = []
                    for p in self.rewards.get("wheel", []):
                        if p.get('weight', 0) <= 0: continue
                        p_copy = p.copy()
                        # Apply luck bonus to explicit Grand Prizes
                        if p_copy.get('grand_prize'):
                            p_copy['weight'] = p_copy.get('weight', 0) + (wheel_level * 0.2)
                        prizes.append(p_copy)

                    if not prizes:
                        await msg.edit(content="❌ No prizes configured in the wheel!")
                        return

                    weights = [p['weight'] for p in prizes]
                    result = random.choices(prizes, weights=weights, k=1)[0]

                    # Multiplier check
                    if result.get('type') == 'multiplier':
                        current_multiplier = result['amount']
                        spin_round += 1
                        embed.title = f"🎰 Lucky Wheel - MULTIPLIER! (x{current_multiplier})"
                        embed.description = f"🎊 **HOLY COW!** You landed on a **x{current_multiplier} Multiplier**!\n\n🚀 Re-spinning for a **BOOSTED** prize..."
                        embed.color = 0xFFAA00
                        await msg.edit(embed=embed)
                        await asyncio.sleep(2)
                        continue 
                    
                    # Final result processing
                    win_text = ""
                    color = 0x00FF00
                    final_amount = result.get('amount', 1)
                    
                    if current_multiplier > 1:
                        if result['type'] in ["pal", "template_pal"]:
                            await db.add_palmarks(steam_id, 100000, "Lucky Wheel Multi-Bonus")
                            win_text = f"💰 **MULTIPLIER BONUS!**\nWin: **100,000 PALDOGS** (Gamble x{current_multiplier}!)"
                            color = 0xFFFF00
                        else:
                            final_amount = result['amount'] * current_multiplier
                            if result['type'] == "currency":
                                await db.add_palmarks(steam_id, final_amount, "Lucky Wheel Multi-Win")
                                win_text = f"💰 **BOOSTED WIN!** You won **{final_amount:,} PALDOGS**!"
                            elif result['type'] == "exp":
                                await db.add_experience(steam_id, final_amount)
                                win_text = f"🆙 **BOOSTED WIN!** You won **{final_amount:,} EXP**!"
                            elif result['type'] in ["item", "pal", "template_pal"]:
                                await db.add_to_inventory(steam_id, result['id'], final_amount, "Wheel Multi-Win", result['type'])
                                win_text = f"🎁 **BOOSTED WIN!** You won **{final_amount:,}x {result['name']}**!"
                    else:
                        if result['type'] == "currency":
                            await db.add_palmarks(steam_id, final_amount, "Lucky Wheel Win")
                            win_text = f"💰 **You won {final_amount:,} PALDOGS!**"
                        elif result['type'] == "exp":
                            await db.add_experience(steam_id, final_amount)
                            win_text = f"🆙 **You won {final_amount:,} EXP!**"
                        else:
                            await db.add_to_inventory(steam_id, result['id'], final_amount, "Wheel Win", result['type'])
                            win_text = f"🎁 **You won {result['name']}!**\n*Check `/inventory` to claim.*"
                            if "pal" in result['type']: color = 0xFF00FF

                    embed.title = "🎰 Lucky Wheel - Result"
                    embed.color = color
                    embed.description = f"Congratulations {interaction.user.mention}!\n\n{win_text}"
                    embed.set_footer(text=f"Spent {current_cost:,} | Progressive Level: {wheel_level} -> {wheel_level+1}")
                    await msg.edit(embed=embed)
                    
                    # Record Activity
                    activity_entry = {
                        "user": interaction.user.display_name,
                        "prize": result['name'],
                        "time": time.time(),
                        "multiplier": current_multiplier
                    }
                    self.recent_activity.insert(0, activity_entry)
                    self.recent_activity = self.recent_activity[:10]
                    
                    # Update main UI table
                    asyncio.create_task(self.update_wheel_table(interaction.channel))
                    break

                # Post-spin cleanup (logs, grand prizes)
                display_name = f"{result['name']} (x{current_multiplier})" if current_multiplier > 1 else result['name']
                self.last_results.insert(0, display_name)
                self.last_results = self.last_results[:10]

                if result.get('grand_prize'):
                    self.rewards['last_grand_winner'] = interaction.user.display_name
                    self.rewards['last_grand_prize'] = result['name']
                    self.rewards['wheel'] = [p for p in self.rewards['wheel'] if p['id'] != result['id']]
                    self.save_rewards()
                    asyncio.create_task(self.update_wheel_table(interaction.channel))

                await asyncio.sleep(15)
                try: await msg.delete()
                except: pass

            except Exception as e:
                print(f"❌ Error during wheel spin: {e}")
                await interaction.followup.send("❌ An error occurred during the spin. Please contact admin.", ephemeral=True)
            finally:
                self.is_spinning = False

    def _get_pal_real_name(self, pal_id):
        pal_info = pal_system.get_pal(pal_id)
        if not pal_info: return pal_id
        try:
            data = json.loads(pal_info["json"])
            return data.get("Nickname") or data.get("PalID") or pal_id
        except:
            return pal_id

    def _get_pal_stats_summary(self, pal_id, short=False):
        pal_info = pal_system.get_pal(pal_id)
        if not pal_info:
            return "No template found"
        
        try:
            data = json.loads(pal_info["json"])
            souls = data.get("PalSouls", {})
            ivs = data.get("IVs", {})
            
            s_h = souls.get("Health", 0)
            s_a = souls.get("Attack", 0)
            s_d = souls.get("Defense", 0)
            
            i_h = ivs.get("Health", 0)
            i_a_m = ivs.get("AttackMelee", 0)
            i_a_s = ivs.get("AttackShot", 0)
            i_d = ivs.get("Defense", 0)
            
            if short:
                return f"❤️{s_h}/{i_h} ⚔️{s_a}/{i_a_s} 🛡️{s_d}/{i_d}"
            return f"**Souls**: ❤️{s_h} ⚔️{s_a} 🛡️{s_d} | **IVs**: ❤️{i_h} ⚔️{i_a_m}/{i_a_s} 🛡️{i_d}"
        except:
            return "Error parsing stats"

    async def _deliver_prize(self, interaction: nextcord.Interaction, stats, item_data):
        """Unified delivery logic for Wheel and Inventory"""
        success = False
        resp = "Unknown Error"
        
        item_type = item_data.get('type', 'item')
        item_id = item_data['item_id']
        amount = item_data.get('amount', 1)
        steam_id = stats['steam_id']
        
        # 1. TEMPLATE PAL CHECK (Highest Priority)
        # Check if this ID exists in our custom_pals.json
        pal_def = pal_system.get_pal(item_id)
        
        if pal_def or item_type == 'template_pal':
            # Auto-sync template file if directory is configured
            template_dir = config.get('pal_template_dir')
            if template_dir and os.path.exists(template_dir):
                try:
                    # Use actual ID from definition if it differs (e.g. case sensitivity)
                    # But we usually use lowercase in custom_pals keys.
                    file_path = os.path.join(template_dir, f"{item_id.lower()}.json")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(json.loads(pal_def['json']), f, indent=4)
                except Exception as e:
                    print(f"⚠️ Failed to auto-sync template '{item_id}' during delivery: {e}")
            
            success, resp = await rcon_util.give_pal_template(steam_id, item_id)
        
        # 2. STANDARD PAL
        elif item_type == 'pal':
            success, resp = await rcon_util.give_pal_standard(steam_id, item_id)
            
        # 3. STANDARD ITEM
        else:
            success, resp = await rcon_util.give_item(steam_id, item_id, amount)

        if success:
            # Mark as claimed if it came from the DB
            if 'id' in item_data:
                await db.mark_item_claimed(item_data['id'])
            
            reveal_msg = f"✅ Successfully delivered **{item_id}**!"
            if item_type == 'template_pal':
                real_name = self._get_pal_real_name(item_id)
                reveal_msg = f"✨ **IDENTITY REVEALED!** You claimed the legendary **{real_name}**!"
            
            return True, reveal_msg
        else:
            return False, f"❌ Delivery failed: {resp if resp else 'Server offline/timeout'}"

    @nextcord.slash_command(
        name="gamble_admin", 
        description="Admin commands for Casino",
        default_member_permissions=nextcord.Permissions(administrator=True)
    )
    async def admin_group(self, interaction: nextcord.Interaction):
        pass

    @admin_group.subcommand(name="setup_wheel", description="Initialize/Update the permanent Lucky Wheel UI")
    async def setup_wheel_ui(self, interaction: nextcord.Interaction):
        from utils.config_manager import config
        target_cid = config.get('gambling_channel_id')
        if not target_cid:
            await interaction.response.send_message("❌ Channel not configured! Use `/setup_channels` first.", ephemeral=True)
            return
            
        channel = self.bot.get_channel(target_cid)
        if not channel:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return
            
        await self.update_wheel_table(channel)
        await interaction.response.send_message("✅ Lucky Wheel UI initialized/updated!", ephemeral=True)

    async def update_wheel_table(self, channel):
        embed = nextcord.Embed(title="🎰 Palworld Casino - Lucky Wheel", color=0xFFD700)
        
        legendary_items = [
            p for p in self.rewards.get('wheel', []) 
            if p.get('grand_prize')
        ]
        grand_count = len(legendary_items)
        
        jackpot_pool = ""
        if grand_count > 0:
            for i, p in enumerate(legendary_items[:5]): # Show up to 5 featured
                stats = self._get_pal_stats_summary(p['id'], short=True)
                jackpot_pool += f"🌟 **Mysterious Jackpot #{i+1}**\n└ `{stats}`\n"
            if grand_count > 5:
                jackpot_pool += f"*+ {grand_count-5} more hidden legendaries...*\n"
        else:
            jackpot_pool = "▫️ *The Legendaries have all been won. Wait for a reset!*"

        last_winner = self.rewards.get('last_grand_winner', 'None')
        winner_text = f"🏆 **LATEST JACKPOT WINNER:**\n👤 `{last_winner}` recently hit the Jackpot!\n\n" if last_winner != "None" else ""

        # Recent Activity Log
        activity_text = ""
        if self.recent_activity:
            for act in self.recent_activity:
                multi = f" (x{act['multiplier']})" if act['multiplier'] > 1 else ""
                activity_text += f"• `{act['user']}` won **{act['prize']}**{multi}\n"
        else:
            activity_text = "▫️ *No recent activity yet today.*"

        embed.description = (
            f"{winner_text}"
            "Welcome to the Lucky Wheel! Every spin is a **guaranteed win**.\n\n"
            "**Featured Jackpot Pool:**\n"
            f"{jackpot_pool}\n"
            "📜 **RECENT ACTIVITY:**\n"
            f"{activity_text}\n"
            "**How to Play:**\n"
            "1. Click the **[ 🎰 Spin for 500 ]** button below.\n"
            "2. Wait for the wheel to stop spinning.\n"
            "3. Prizes are delivered to your **`/inventory`** instantly!\n\n"
            "📈 **PROGRESIVE SYSTEM:**\n"
            "• Each spin increases your **Lucky Weight** by **+0.2**.\n"
            "• Your next spin cost increases by **250 PALDOGS**.\n"
            "• High risk, high reward! Reset anytime at the original cost.\n\n"
            "📍 *Prizes include: Mysterious Pals, Paldog Stashes, EXP, and Rare items.*"
        )
        embed.set_thumbnail(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExaXB5ZDg0d3N3aW9xN3cxb2kyd2NmZWh6a2J1YWU5M3dzOTM3b3c3eCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/flw1xlTYMBVFKBHzPz/giphy.gif")
        
        from utils.config_manager import config
        msg_id = config.get('gambling_table_message_id')
        view = LuckyWheelView(self)
        
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return
            except nextcord.NotFound:
                # Message was deleted, clear it so we create a new one
                config.set('gambling_table_message_id', None)
            except Exception as e:
                print(f"⚠️ Error updating wheel table: {e}")

        # Create new if doesn't exist
        msg = await channel.send(embed=embed, view=view)
        config.set('gambling_table_message_id', msg.id)

    @admin_group.subcommand(name="add_grand_prize", description="Add a new Grand Prize to the wheel")
    async def add_grand_prize_cmd(
        self,
        interaction: nextcord.Interaction,
        id: str = nextcord.SlashOption(description="Internal ID (e.g. Shadowbeak)"),
        name: str = nextcord.SlashOption(description="Display Name (e.g. 🔥 Shiny Shadowbeak)"),
        type: str = nextcord.SlashOption(choices={"Pal": "pal", "Template Pal": "template_pal", "Item": "item", "Currency": "currency", "EXP": "exp"}),
        amount: int = nextcord.SlashOption(default=1),
        weight: float = nextcord.SlashOption(default=1.0, description="Win weight (allows decimals e.g. 0.5)")
    ):
            
        new_prize = {
            "id": id,
            "name": name,
            "type": type,
            "amount": amount,
            "weight": weight,
            "grand_prize": True
        }
        
        self.rewards['wheel'].insert(0, new_prize)
        self.save_rewards()
        
        # Update UI
        from utils.config_manager import config
        target_cid = config.get('gambling_channel_id')
        if target_cid:
            channel = self.bot.get_channel(target_cid)
            if channel: await self.update_wheel_table(channel)
            
        await interaction.response.send_message(f"✅ Added **{name}** as a new Grand Prize!", ephemeral=True)

    @admin_group.subcommand(name="reset_winners", description="Clear the 'Last Grand Winner' history")
    async def reset_winners_cmd(self, interaction: nextcord.Interaction):
            
        self.rewards['last_grand_winner'] = "None"
        self.rewards['last_grand_prize'] = "None"
        self.save_rewards()
        
        # Update UI
        from utils.config_manager import config
        target_cid = config.get('gambling_channel_id')
        if target_cid:
            channel = self.bot.get_channel(target_cid)
            if channel: await self.update_wheel_table(channel)
            
        await interaction.response.send_message("✅ Grand Winner history has been cleared!", ephemeral=True)

    @admin_group.subcommand(name="reload", description="♻️ Reload rewards from JSON")
    async def reload_rewards(self, interaction: nextcord.Interaction):
        self.load_rewards()
        await interaction.response.send_message("✅ Rewards reloaded from `gambling_rewards.json`.", ephemeral=True)

    @admin_group.subcommand(name="set_daily_limit", description="📅 Set daily spin limit per player")
    async def set_daily_limit(self, interaction: nextcord.Interaction, limit: int = nextcord.SlashOption(min_value=1)):
        self.rewards['daily_limit'] = limit
        self.save_rewards()
        await interaction.response.send_message(f"✅ Daily spin limit set to **{limit}** spins per player.", ephemeral=True)

    @admin_group.subcommand(name="sync_templates", description="Sync Pal templates from a folder to gambling rewards")
    async def sync_templates_cmd(
        self,
        interaction: nextcord.Interaction,
        directory_path: str = nextcord.SlashOption(description="Full path to PalDefender Templates folder"),
        default_weight: float = nextcord.SlashOption(default=1.0, description="Default weight for new rewards")
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.send("❌ Admin only.", ephemeral=True)

        # Normalize path
        directory_path = directory_path.strip().strip('"')
        
        if not os.path.exists(directory_path):
            return await interaction.send(f"❌ Directory not found: `{directory_path}`", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        count = 0
        updated = 0
        
        for filename in os.listdir(directory_path):
            if filename.endswith(".json"):
                file_path = os.path.join(directory_path, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        pal_data = json.load(f)
                        
                    pal_id = filename[:-5].lower() # use filename as ID
                    
                    # 1. Add/Update in pal_system
                    raw_json = json.dumps(pal_data)
                    pal_system.add_pal(pal_id, raw_json, description=f"Imported from {filename}")
                    
                    # 2. Add to gambling rewards if not present
                    existing = next((p for p in self.rewards["wheel"] if p["id"] == pal_id), None)
                    if not existing:
                        new_prize = {
                            "id": pal_id,
                            "name": pal_data.get("Nickname", pal_data.get("PalID", pal_id)),
                            "type": "template_pal",
                            "amount": 1,
                            "weight": default_weight
                        }
                        self.rewards["wheel"].append(new_prize)
                        count += 1
                    else:
                        updated += 1
                except Exception as e:
                    print(f"Error importing {filename}: {e}")

        self.save_rewards()
        await interaction.followup.send(f"✅ Synced **{count}** new Pals and updated **{updated}** in system. New Pals added to wheel with weight `{default_weight}`.", ephemeral=True)

    @admin_group.subcommand(name="manage_rewards", description="📋 List and adjust weights for all wheel rewards")
    async def manage_rewards_cmd(self, interaction: nextcord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.send("❌ Admin only.", ephemeral=True)
            
        prizes = self.rewards.get("wheel", [])
        if not prizes:
            return await interaction.send("❌ No rewards configured.", ephemeral=True)
            
        view = RewardManagerView(self, prizes)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)

    @admin_group.subcommand(name="test_deliver", description="Test instant delivery of a specific wheel prize (Admin)")
    async def test_deliver(
        self,
        interaction: nextcord.Interaction,
        prize_id: str = nextcord.SlashOption(description="The ID of the prize to test", autocomplete=True),
        player_name: str = nextcord.SlashOption(description="Player to deliver to (defaults to you)", required=False, autocomplete=True)
    ):

        await interaction.response.defer(ephemeral=True)
        
        # Determine target player
        if player_name:
            stats = await db.get_player_stats_by_name(player_name)
        else:
            stats = await db.get_player_by_discord(interaction.user.id)
            
        if not stats:
            await interaction.followup.send(f"❌ Player '{player_name or interaction.user.display_name}' not found or not linked.", ephemeral=True)
            return

        # Find the prize in the wheel
        prize = next((p for p in self.rewards.get('wheel', []) if p['id'] == prize_id), None)
        if not prize:
            await interaction.followup.send(f"❌ Prize ID '{prize_id}' not found in current wheel pool.", ephemeral=True)
            return

        steam_id = stats['steam_id']
        item_type = prize.get('type', 'item')
        item_id = prize['id']
        amount = prize.get('amount', 1)
        
        server_info = rcon_util._get_server_info()
        if not server_info:
            await interaction.followup.send("❌ RCON is not configured.", ephemeral=True)
            return

        if prize['type'] == 'currency':
            amount = prize.get('amount', 500)
            await db.add_palmarks(steam_id, amount, "Test Delivery")
            success = True
            resp = f"Added {amount:,} PALDOGS to database."
        elif prize['type'] == 'exp':
            amount = prize.get('amount', 1000)
            success = await rcon_util.give_exp(steam_id, amount)
            resp = "Sent EXP command via RCON." if success else "Failed to send EXP command."
        else:
            # Map prize dict to item_data format expected by helper
            item_data = {
                'item_id': prize['id'],
                'type': prize.get('type', 'item'),
                'amount': prize.get('amount', 1)
            }
            success, resp = await self._deliver_prize(interaction, stats, item_data)
        
        if success:
            await interaction.followup.send(f"✅ **Test Successful!**\nPrize: **{prize['name']}**\nTarget: `{stats['player_name']}`\nServer Response: `{resp if resp else 'Success (No response)'}`", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Test Failed!**\nServer Response: `{resp if resp else 'No response/Timeout'}`\n*Ensure the player is online!*", ephemeral=True)

    @test_deliver.on_autocomplete("prize_id")
    async def prize_id_autocomplete(self, interaction: nextcord.Interaction, current: str):
        prizes = self.rewards.get('wheel', [])
        choices = {p['name'][:100]: p['id'] for p in prizes if current.lower() in p['name'].lower() or current.lower() in p['id'].lower()}
        await interaction.response.send_autocomplete(choices)

    @test_deliver.on_autocomplete("player_name")
    async def player_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = await db.get_player_names_autocomplete(current)
        await interaction.response.send_autocomplete(choices)

    @admin_group.subcommand(name="purge", description="🗑️ Clear all chatter from the gambling channels (Admin)")
    async def purge_chatter(self, interaction: nextcord.Interaction):

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=100, check=lambda m: m.author.id != self.bot.user.id)
        await interaction.followup.send(f"✅ Cleaned up **{len(deleted)}** messages.", ephemeral=True)

    @nextcord.slash_command(name="inventory", description="View and claim your won items")
    async def inventory(self, interaction: nextcord.Interaction):
        await interaction.response.defer(ephemeral=True)
        items = await db.get_unclaimed_items(interaction.user.id)
        if not items:
            await interaction.followup.send("📦 Your virtual inventory is empty.", ephemeral=True)
            return
        view = InventoryView(self, items, interaction.user.display_name)
        await interaction.followup.send(embed=view.get_embed(), view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        from utils.config_manager import config
        wheel_cid = config.get('gambling_channel_id')
        if message.channel.id == wheel_cid:
            await asyncio.sleep(5)
            try: 
                # Re-fetch or check if still alive to avoid 404
                await message.delete()
            except nextcord.NotFound:
                pass # Already deleted
            except Exception:
                pass

    async def reset_progress(self, interaction: nextcord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats:
            await interaction.followup.send("❌ Link your account first with `/link`!", ephemeral=True)
            return
        
        steam_id = stats['steam_id']
        await db.reset_wheel_level(steam_id)
        await interaction.followup.send("✅ **PROGRESS RESET!** Your wheel level and cost have returned to base defaults.", ephemeral=True)

class LuckyWheelView(View):
    def __init__(self, gambling_cog):
        super().__init__(timeout=None) # Persistent
        self.gambling_cog = gambling_cog

    @nextcord.ui.button(label="🎰 Spin", style=nextcord.ButtonStyle.primary, custom_id="persistent_spin_button")
    async def spin_button(self, button, interaction: nextcord.Interaction):
        await self.gambling_cog.process_wheel_spin(interaction)

    @nextcord.ui.button(label="🔄 Reset Progress", style=nextcord.ButtonStyle.secondary, custom_id="reset_wheel_progress")
    async def reset_button(self, button, interaction: nextcord.Interaction):
        await self.gambling_cog.reset_progress(interaction)

class InventoryView(View):
    def __init__(self, gambling_cog, items, user_name):
        super().__init__(timeout=120)
        self.gambling_cog = gambling_cog
        self.items = items
        self.user_name = user_name
        self.current_page = 0
        self.update_view()

    def get_embed(self):
        start = self.current_page * 5
        total = len(self.items)
        page_items = self.items[start:start+5]
        
        embed = nextcord.Embed(
            title=f"📦 {self.user_name}'s Inventory", 
            description=f"You have **{total}** items waiting to be claimed.",
            color=0x3498db
        )
        
        if not self.items:
            embed.description = "📦 Your virtual inventory is empty."
            return embed

        for i, item in enumerate(page_items):
            is_template = "template_pal" in str(item.get('type', ''))
            type_icon = "❓" if is_template else ("🐾" if "pal" in str(item.get('type', '')) else "🎁")
            
            display_name = item['item_id']
            stats_line = f"Type: `{item['type']}`"
            
            if is_template:
                display_name = f"Mysterious Pal Reward"
                stats_preview = self.gambling_cog._get_pal_stats_summary(item['item_id'], short=True)
                stats_line = f"Type: `Template Pal` | Stats: `{stats_preview}`"

            amt = f" x{item['amount']}" if item.get('amount', 1) > 1 else ""
            embed.add_field(
                name=f"{i+1+start}. {type_icon} {display_name}{amt}", 
                value=stats_line, 
                inline=False
            )
        
        embed.set_footer(text=f"Page {self.current_page + 1} of {(total-1)//5 + 1} • Items are delivered via RCON (must be online)")
        return embed

    def update_view(self):
        self.clear_items()
        start = self.current_page * 5
        end = start + 5
        page_items = self.items[start:end]
        
        for i, item in enumerate(page_items):
            # Claim button
            claim_label = f"Claim #{i+1+start}"
            claim_btn = Button(label=claim_label, style=nextcord.ButtonStyle.success, row=i)
            claim_btn.callback = self.create_claim_callback(item)
            self.add_item(claim_btn)
            
            # Delete button
            del_label = f"🗑️ Delete #{i+1+start}"
            del_btn = Button(label=del_label, style=nextcord.ButtonStyle.danger, row=i)
            del_btn.callback = self.create_delete_callback(item)
            self.add_item(del_btn)

        # Navigation row
        if len(self.items) > 5:
            prev_btn = Button(label="◀️ Previous", style=nextcord.ButtonStyle.secondary, disabled=(self.current_page == 0))
            async def prev_cb(interaction):
                self.current_page -= 1
                self.update_view()
                await interaction.response.edit_message(embed=self.get_embed(), view=self)
            prev_btn.callback = prev_cb
            self.add_item(prev_btn)

            next_btn = Button(label="Next ▶️", style=nextcord.ButtonStyle.secondary, disabled=(end >= len(self.items)))
            async def next_cb(interaction):
                self.current_page += 1
                self.update_view()
                await interaction.response.edit_message(embed=self.get_embed(), view=self)
            next_btn.callback = next_cb
            self.add_item(next_btn)

    def create_claim_callback(self, item_data):
        async def callback(interaction: nextcord.Interaction):
            await interaction.response.defer(ephemeral=True)
            stats = await db.get_player_by_discord(interaction.user.id)
            if not stats: return
            
            online_players = await rest_api.get_player_list()
            
            # Safety check: If server is offline/API fails, online_players will be None
            if not online_players:
                await interaction.followup.send("⚠️ The server appears to be **OFFLINE**. Please try again when the server is online.", ephemeral=True)
                return

            is_online = any(str(p.get('userId', '')).replace('steam_', '') == stats['steam_id'].replace('steam_', '') or 
                            str(p.get('playerId', '')).replace('steam_', '') == stats['steam_id'].replace('steam_', '') 
                            for p in online_players.get('players', []))
            
            if not is_online:
                await interaction.followup.send("⚠️ You must be **ONLINE** on the server to claim your reward.", ephemeral=True)
                return
                
            success, msg = await self.gambling_cog._deliver_prize(interaction, stats, item_data)
            
            if success:
                await interaction.followup.send(msg, ephemeral=True)
                
                # Update local list and maintain page
                self.items = [i for i in self.items if i['id'] != item_data['id']]
                if self.current_page * 5 >= len(self.items) and self.current_page > 0:
                    self.current_page -= 1
                
                self.update_view()
                try:
                    await interaction.edit_original_message(embed=self.get_embed(), view=self)
                except:
                    pass
            else:
                await interaction.followup.send(msg, ephemeral=True)
        return callback

    def create_delete_callback(self, item_data):
        async def callback(interaction: nextcord.Interaction):
            await db.delete_inventory_item(item_data['id'])
            
            # Update local list and maintain page
            self.items = [i for i in self.items if i['id'] != item_data['id']]
            if self.current_page * 5 >= len(self.items) and self.current_page > 0:
                self.current_page -= 1
            
            self.update_view()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
            await interaction.followup.send("🗑️ Reward permanently deleted from your inventory.", ephemeral=True)
        return callback

class RewardManagerView(nextcord.ui.View):
    def __init__(self, cog, items, current_page=0):
        super().__init__(timeout=300)
        self.cog = cog
        self.items = items
        self.current_page = current_page
        self.items_per_page = 5
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]
        
        # Add buttons for each item in current page to edit weight
        for i, item in enumerate(page_items):
            # Edit Button
            edit_btn = nextcord.ui.Button(label=f"Edit {item['name'][:15]}", style=nextcord.ButtonStyle.secondary, row=i)
            edit_btn.callback = self.create_edit_callback(item)
            self.add_item(edit_btn)
            
            # Toggle Grand Prize Button
            is_grand = item.get('grand_prize', False)
            toggle_label = "🌟 Grand" if is_grand else "▫️ Normal"
            toggle_style = nextcord.ButtonStyle.success if is_grand else nextcord.ButtonStyle.gray
            toggle_btn = nextcord.ui.Button(label=toggle_label, style=toggle_style, row=i)
            toggle_btn.callback = self.create_toggle_callback(item)
            self.add_item(toggle_btn)
            
        # Navigation buttons
        nav_row = 4
        if self.current_page > 0:
            prev_btn = nextcord.ui.Button(label="⬅️ Previous", style=nextcord.ButtonStyle.primary, row=nav_row)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)
            
        if end < len(self.items):
            next_btn = nextcord.ui.Button(label="Next ➡️", style=nextcord.ButtonStyle.primary, row=nav_row)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

    def create_edit_callback(self, item):
        async def callback(interaction: nextcord.Interaction):
            modal = WeightEditModal(self.cog, item, self)
            await interaction.response.send_modal(modal)
        return callback

    def create_toggle_callback(self, item):
        async def callback(interaction: nextcord.Interaction):
            # Toggle in memory
            for prize in self.cog.rewards["wheel"]:
                if prize["id"] == item["id"]:
                    prize["grand_prize"] = not prize.get("grand_prize", False)
                    # Sync local item ref too
                    item["grand_prize"] = prize["grand_prize"]
                    break
            
            self.cog.save_rewards()
            self.update_buttons() # Refresh button labels/colors
            
            # Update UI message
            status = "GRAND PRIZE" if item["grand_prize"] else "NORMAL REWARD"
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
            await interaction.followup.send(f"✅ **{item['name']}** is now a **{status}**!", ephemeral=True)
        return callback

    async def prev_page(self, interaction: nextcord.Interaction):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_page(self, interaction: nextcord.Interaction):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    def get_embed(self):
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]
        
        embed = nextcord.Embed(
            title="🎡 Gambling Reward Pool Management",
            description=f"Showing items {start+1} to {min(end, len(self.items))} of {len(self.items)}",
            color=nextcord.Color.blue()
        )
        
        for item in page_items:
            is_grand = "🌟 **GRAND PRIZE**" if item.get('grand_prize') else "▫️ Normal Reward"
            details = f"ID: `{item['id']}` | Weight: **{item['weight']}** | {is_grand}\nType: `{item['type']}`"
            if item['type'] == 'template_pal':
                stats = self.cog._get_pal_stats_summary(item['id'])
                details += f"\n{stats}"
            
            embed.add_field(name=item['name'], value=details, inline=False)
            
        embed.set_footer(text=f"Page {self.current_page + 1} | Total weights: {sum(i.get('weight', 0) for i in self.items):.2f}")
        return embed

class WeightEditModal(nextcord.ui.Modal):
    def __init__(self, cog, item, parent_view):
        super().__init__(title=f"Edit Weight: {item['name'][:30]}")
        self.cog = cog
        self.item = item
        self.parent_view = parent_view
        
        self.weight_input = nextcord.ui.TextInput(
            label="New Weight",
            placeholder=f"Current: {item['weight']}",
            default_value=str(item['weight']),
            min_length=1,
            max_length=10
        )
        self.add_item(self.weight_input)

    async def callback(self, interaction: nextcord.Interaction):
        try:
            new_weight = float(self.weight_input.value)
            if new_weight < 0:
                return await interaction.send("Weight must be positive!", ephemeral=True)
            
            # Update the weight in the cog's rewards
            for prize in self.cog.rewards["wheel"]:
                if prize["id"] == self.item["id"]:
                    prize["weight"] = new_weight
                    break
            
            self.cog.save_rewards()
            
            # Refresh the view
            # self.parent_view.update_buttons() # Not strictly necessary if only one item changes but good for consistency
            await interaction.response.edit_message(embed=self.parent_view.get_embed(), view=self.parent_view)
            await interaction.followup.send(f"✅ Updated weight for **{self.item['name']}** to **{new_weight}**", ephemeral=True)
            
        except ValueError:
            await interaction.send("❌ Invalid weight! Please enter a number (decimals allowed).", ephemeral=True)

def setup(bot):
    bot.add_cog(Gambling(bot))
