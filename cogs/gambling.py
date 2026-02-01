import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button
import random
import asyncio
from utils.database import db
from utils.rcon_utility import rcon_util
from utils.rest_api import rest_api
from cogs.rank_system import rank_system

import json
import os
import random
import asyncio
from nextcord.ext import tasks

# Roulette Data
ROULETTE_NUMBERS = {
    0: "green",
    1: "red", 2: "black", 3: "red", 4: "black", 5: "red", 6: "black",
    7: "red", 8: "black", 9: "red", 10: "black", 11: "black", 12: "red",
    13: "black", 14: "red", 15: "black", 16: "red", 17: "black", 18: "red",
    19: "red", 20: "black", 21: "red", 22: "black", 23: "red", 24: "black",
    25: "red", 26: "black", 27: "red", 28: "black", 29: "black", 30: "red",
    31: "black", 32: "red", 33: "black", 34: "red", 35: "black", 36: "red"
}

class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rewards_file = os.path.join("data", "gambling_rewards.json")
        self.rewards = {"roulette": [], "win_chance": 0.7}
        self.load_rewards()
        
        from utils.config_manager import config
        self.table_message_id = config.get('gambling_table_message_id')
        self.table_message = None
        self.last_results = []
        self.is_spinning = False
        self.countdown = 0
        self.active_bets = {}

    def load_rewards(self):
        if os.path.exists(self.rewards_file):
            try:
                with open(self.rewards_file, "r") as f:
                    self.rewards = json.load(f)
            except Exception as e:
                print(f"❌ Error loading gambling rewards: {e}")
        else:
            self.rewards = {"roulette": [{"id": "PalSphere", "name": "Pal Sphere", "amount": 5, "weight": 50}], "win_chance": 0.7}

    @nextcord.slash_command(name="gamble", description="Casino games")
    async def gamble_group(self, interaction: nextcord.Interaction):
        pass

    @gamble_group.subcommand(name="roulette", description="Place a bet on the Roulette table")
    async def roulette(
        self,
        interaction: nextcord.Interaction,
        amount: int = nextcord.SlashOption(description="Amount of PALDOGS to bet", min_value=10),
        choice: str = nextcord.SlashOption(
            description="What to bet on",
            choices={
                "Red (2x)": "red",
                "Black (2x)": "black",
                "Even (2x)": "even",
                "Odd (2x)": "odd",
                "Specific Number (36x)": "number"
            }
        ),
        number: int = nextcord.SlashOption(
            description="If betting on a Specific Number, enter it here (0-36)",
            min_value=0,
            max_value=36,
            required=False
        )
    ):
        await self.place_record_bet(interaction, amount, choice, number)

    async def roulette_loop(self, channel):
        while self.countdown > 0:
            await self.update_table_message(channel)
            await asyncio.sleep(5)
            self.countdown -= 5
        
        self.is_spinning = True
        await self.update_table_message(channel)
        
        # Spinning delay
        await asyncio.sleep(5)
        
        # Roll result
        number = random.randint(0, 36)
        color = ROULETTE_NUMBERS[number]
        
        results_msg = []
        total_prizes = 0
        
        # Process winners
        for steam_id, bets in self.active_bets.items():
            player_total_win = 0
            player_won_items = []
            player_name = bets[0]['name']
            
            for b in bets:
                won = False
                multiplier = 0
                
                # Logic
                if b['choice'] == color: # red/black
                    won = True
                    multiplier = 2
                elif b['choice'] == "even" and number != 0 and number % 2 == 0:
                    won = True
                    multiplier = 2
                elif b['choice'] == "odd" and number != 0 and number % 2 != 0:
                    won = True
                    multiplier = 2
                elif b['choice'].isdigit() and int(b['choice']) == number:
                    won = True
                    multiplier = 36
                
                if won:
                    win_paldogs = int(b['amount'] * multiplier)
                    player_total_win += win_paldogs
                    
                    # Plus an item!
                    items = self.rewards.get("roulette", [])
                    if items:
                        weights = [r['weight'] for r in items]
                        reward = random.choices(items, weights=weights, k=1)[0]
                        await db.add_to_inventory(steam_id, reward['id'], reward['amount'], "Roulette Win")
                        player_won_items.append(f"{reward['amount']}x {reward['name']}")

            if player_total_win > 0:
                await db.add_palmarks(steam_id, player_total_win, f"Roulette Win: {number}")
                total_prizes += player_total_win
                item_text = f" + [{', '.join(player_won_items)}]" if player_won_items else ""
                results_msg.append(f"🏆 **{player_name}** won **{player_total_win:,} PALDOGS**{item_text}!")

        # Final Embed Configuration
        color_emoji = "🔴" if color == "red" else ("⚫" if color == "black" else "🟢")
        result_text = f"{color_emoji} **{number} ({color.upper()})**"
        self.last_results.insert(0, result_text)
        self.last_results = self.last_results[:10]

        embed = nextcord.Embed(title="🎡 Roulette Result", color=0x00FF00 if color == "red" else 0x000000)
        desc = f"The wheel landed on: {result_text}\n\n"
        
        if results_msg:
            desc += "__**Winners:**__\n" + "\n".join(results_msg)
        else:
            desc += "No winners this round... 💸"
            embed.color = 0xFF0000
        
        embed.description = desc
        embed.add_field(name="History", value=" | ".join(self.last_results), inline=False)
        embed.set_footer(text="Resetting for next round in 10s...")

        # Edit the existing table directly
        if self.table_message:
            await self.table_message.edit(embed=embed)
        
        # Reset and wait before showing "Open for Bets" again
        await asyncio.sleep(10)
        self.active_bets = {}
        self.is_spinning = False
        self.countdown = 0
        await self.update_table_message(channel)

    async def update_table_message(self, channel):
        # Calculate total bets
        total_players = len(self.active_bets)
        total_paldogs = sum(sum(b['amount'] for b in blist) for blist in self.active_bets.values())
        
        embed = nextcord.Embed(title="🎡 Palworld Casino - Roulette", color=0xFFD700)
        
        status = "🟢 OPEN FOR BETS" if not self.is_spinning else "🔴 SPINNING..."
        if self.countdown > 0:
            status += f" (Spinning in {self.countdown}s)"
            
        embed.add_field(name="Status", value=f"**{status}**", inline=False)
        embed.add_field(name="Active Bets", value=f"👤 {total_players} Players\n💰 {total_paldogs:,} Total PALDOGS", inline=True)
        
        if self.last_results:
            embed.add_field(name="History", value=" | ".join(self.last_results), inline=False)
            
        embed.set_footer(text="Use /gamble bet to join! | Red: 2x, Black: 2x, Even/Odd: 2x, Number: 36x")
        
        if not self.table_message and self.table_message_id:
            try:
                self.table_message = await channel.fetch_message(self.table_message_id)
            except:
                self.table_message = None

        view = RouletteTableView(self)
        if not self.table_message:
            self.table_message = await channel.send(embed=embed, view=view)
            self.table_message_id = self.table_message.id
            from utils.config_manager import config
            config.set('gambling_table_message_id', self.table_message.id)
        else:
            try:
                await self.table_message.edit(embed=embed, view=view)
            except:
                self.table_message = await channel.send(embed=embed, view=view)
                self.table_message_id = self.table_message.id
                from utils.config_manager import config
                config.set('gambling_table_message_id', self.table_message.id)

    async def place_record_bet(self, interaction, amount, choice, number=None):
        """Helper to process both slash and button bets"""
        if self.is_spinning:
            if interaction.response.is_done():
                await interaction.followup.send("⚠️ The wheel is already spinning!", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ The wheel is already spinning!", ephemeral=True)
            return

        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats:
            msg = "❌ Link your account first with `/link`!"
            if interaction.response.is_done(): await interaction.followup.send(msg, ephemeral=True)
            else: await interaction.response.send_message(msg, ephemeral=True)
            return
            
        if stats['palmarks'] < amount:
            msg = f"❌ Insufficient PALDOGS! Balance: **{stats['palmarks']:,}**"
            if interaction.response.is_done(): await interaction.followup.send(msg, ephemeral=True)
            else: await interaction.response.send_message(msg, ephemeral=True)
            return

        final_choice = str(number) if number is not None else choice

        # Deduct and track
        await db.add_palmarks(stats['steam_id'], -amount, f"Table Bet: {final_choice}")
        
        steam_id = stats['steam_id']
        if steam_id not in self.active_bets:
            self.active_bets[steam_id] = []
        
        self.active_bets[steam_id].append({
            "amount": amount,
            "choice": final_choice,
            "user": interaction.user,
            "name": stats['player_name']
        })

        # Start countdown if first bet
        if self.countdown <= 0:
            self.countdown = 30
            asyncio.create_task(self.roulette_loop(interaction.channel))

        # Send confirmation
        resp_choice = f"Number {number}" if number is not None else choice.upper()
        resp = f"✅ Bet recorded: **{amount:,} PALDOGS** on **{resp_choice}**."
        
        if interaction.response.is_done():
            msg = await interaction.followup.send(resp)
            await asyncio.sleep(5)
            try: await msg.delete()
            except: pass
        else:
            await interaction.response.send_message(resp)
            await asyncio.sleep(5)
            try: await interaction.delete_original_message()
            except: pass

    @gamble_group.subcommand(name="blackjack", description="Play a game of Blackjack against the Dealer")
    async def blackjack(
        self,
        interaction: nextcord.Interaction,
        bet: int = nextcord.SlashOption(description="Amount of PALDOGS to bet", min_value=10)
    ):
        from utils.config_manager import config
        blackjack_channel_id = config.get('blackjack_channel_id')
        if blackjack_channel_id and interaction.channel_id != blackjack_channel_id:
            await interaction.response.send_message(f"⚠️ This command can only be used in <#{blackjack_channel_id}>!", ephemeral=True)
            return

        await interaction.response.defer()
        
        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats:
            await interaction.followup.send("❌ Link your account first!", ephemeral=True)
            return
            
        if stats['palmarks'] < bet:
            await interaction.followup.send(f"❌ Insufficient PALDOGS!", ephemeral=True)
            return

        # Start a multiplayer lobby
        view = BlackjackView(interaction.user, bet, stats['steam_id'], self.bot)
        await view.start_lobby(interaction)

    @gamble_group.subcommand(name="setup_roulette", description="Initialize the permanent Roulette Table visuals")
    async def setup_roulette(self, interaction: nextcord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
            
        from utils.config_manager import config
        target_cid = config.get('gambling_channel_id')
        if not target_cid:
            await interaction.response.send_message("❌ Gambling channel not configured! Use `/setup_channels` first.", ephemeral=True)
            return
            
        channel = self.bot.get_channel(target_cid)
        if not channel:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return
            
        self.table_message = None
        await self.update_table_message(channel)
        await interaction.response.send_message("✅ Roulette table initialized!", ephemeral=True)

    @gamble_group.subcommand(name="setup_blackjack", description="Initialize permanent Blackjack visuals")
    async def setup_blackjack_ui(self, interaction: nextcord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
            
        from utils.config_manager import config
        target_cid = config.get('blackjack_channel_id')
        if not target_cid:
            await interaction.response.send_message("❌ Blackjack channel not configured!", ephemeral=True)
            return
            
        channel = self.bot.get_channel(target_cid)
        if not channel:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return
            
        embed = nextcord.Embed(title="🃏 Palworld Casino - Blackjack", color=0x34495e)
        embed.description = (
            "Play Blackjack against the Dealer! Win PALDOGS and level up.\n\n"
            "**Rules:**\n"
            "• Win: 2x Payout\n"
            "• Blackjack: 2.5x Payout\n"
            "• Tie: Push (Bet returned)\n\n"
            "**Command:**\n"
            "`/gamble blackjack <amount>`"
        )
        embed.set_thumbnail(url="https://i.imgur.com/W2VThg9.png") # Generic chip icon
        
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Blackjack UI initialized!", ephemeral=True)

    @gamble_group.subcommand(name="reload", description="Reload gambling prizes from JSON (Admin)")
    async def reload_gambling(self, interaction: nextcord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
            
        self.load_rewards()
        await interaction.response.send_message("✅ Gambling rewards reloaded!", ephemeral=True)

    @gamble_group.subcommand(name="purge", description="🗑️ Clear all chatter from the gambling channels (Admin)")
    async def purge_chatter(self, interaction: nextcord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        # We only delete messages that ARE NOT the persistent table/hubs
        deleted = await interaction.channel.purge(limit=100, check=lambda m: m.id != self.table_message_id and m.author.id != self.bot.user.id)
        
        await interaction.followup.send(f"✅ Cleaned up **{len(deleted)}** messages from this channel.", ephemeral=True)

    @nextcord.slash_command(name="inventory", description="View and claim your won items")
    async def inventory(self, interaction: nextcord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        items = await db.get_unclaimed_items(interaction.user.id)
        if not items:
            await interaction.followup.send("📦 Your virtual inventory is empty.", ephemeral=True)
            return
            
        embed = nextcord.Embed(title="📦 Your Virtual Inventory", description="Claim these items while you are online in Palworld.", color=0x3498db)
        
        view = InventoryView(items)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class InventoryView(View):
    def __init__(self, items):
        super().__init__(timeout=60)
        self.items = items
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        
        # Show up to 5 items per page with claim buttons
        start = self.current_page * 5
        end = start + 5
        page_items = self.items[start:end]
        
        for item in page_items:
            btn = Button(
                label=f"Claim {item['amount']}x {item['item_id']} (from {item['source']})",
                style=nextcord.ButtonStyle.success,
                custom_id=f"claim_{item['id']}"
            )
            btn.callback = self.create_claim_callback(item)
            self.add_item(btn)
            
        if len(self.items) > 5:
            # Add navigation if needed
            pass

    def create_claim_callback(self, item_data):
        async def callback(interaction: nextcord.Interaction):
            await interaction.response.defer(ephemeral=True)
            
            # Check if online
            stats = await db.get_player_by_discord(interaction.user.id)
            if not stats: return
            
            online_players = await rest_api.get_player_list()
            is_online = False
            target_uid = stats['steam_id'].replace('steam_', '')
            
            if online_players:
                for p in online_players.get('players', []):
                    if str(p.get('userId', '')).replace('steam_', '') == target_uid:
                        is_online = True
                        break
            
            if not is_online:
                await interaction.followup.send("⚠️ You must be **ONLINE** to claim items.", ephemeral=True)
                return
                
            # Deliver
            success = await rcon_util.give_item(stats['steam_id'], item_data['item_id'], item_data['amount'])
            if success:
                await db.mark_item_claimed(item_data['id'])
                await interaction.followup.send(f"✅ Delivered **{item_data['amount']}x {item_data['item_id']}** to your inventory!", ephemeral=True)
                # Refresh view
                self.items = [i for i in self.items if i['id'] != item_data['id']]
                if not self.items:
                    await interaction.edit_original_message(content="📦 Your virtual inventory is now empty.", view=None)
                else:
                    self.update_buttons()
                    await interaction.edit_original_message(view=self)
            else:
                await interaction.followup.send("❌ Failed to deliver item. Is RCON working?", ephemeral=True)
                
        return callback

def setup(bot):
    bot.add_cog(Gambling(bot))

class BlackjackView(View):
    def __init__(self, initiator, bet, steam_id, bot):
        super().__init__(timeout=180)
        self.initiator = initiator
        self.bot = bot
        self.deck = self.create_deck()
        self.dealer_hand = []
        self.game_started = False
        self.players = [{
            'user': initiator,
            'steam_id': steam_id,
            'bet': bet,
            'hand': [],
            'status': 'waiting',  # waiting, playing, stood, bust, blackjack
            'name': initiator.display_name
        }]
        self.current_player_idx = 0
        self.message = None

    def create_deck(self):
        suits = ['♠️', '♥️', '♦️', '♣️']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [{'rank': r, 'suit': s} for s in suits for r in ranks]
        random.shuffle(deck)
        return deck

    def calculate_value(self, hand):
        value = 0
        aces = 0
        for card in hand:
            if card['rank'] in ['J', 'Q', 'K']:
                value += 10
            elif card['rank'] == 'A':
                aces += 1
                value += 11
            else:
                value += int(card['rank'])
        
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    def format_hand(self, hand, hide_first=False):
        if not hand: return "`[ Empty ]`"
        
        cards = []
        for i, c in enumerate(hand):
            if i == 0 and hide_first:
                cards.append("`[ ? ]`")
            else:
                # Mapping suit for better visuals if needed, but current emojis are fine
                cards.append(f"`[ {c['rank']}{c['suit']} ]`")
        
        return " ".join(cards)

    def get_value_label(self, hand):
        """Returns a string like '18' or 'Soft 18'"""
        val = 0
        aces = 0
        for card in hand:
            if card['rank'] in ['J', 'Q', 'K']: val += 10
            elif card['rank'] == 'A':
                aces += 1
                val += 11
            else: val += int(card['rank'])
        
        is_soft = False
        while val > 21 and aces:
            val -= 10
            aces -= 1
        
        # It's 'Soft' if we still have an Ace being counted as 11
        if aces > 0 and val <= 21:
            is_soft = True
            
        return f"Soft {val}" if is_soft else str(val)

    async def start_lobby(self, interaction):
        self.message = await interaction.followup.send(embed=self.make_lobby_embed(), view=self)

    def make_lobby_embed(self):
        embed = nextcord.Embed(title="🃏 Blackjack Table - Waiting for Players", color=0x34495e)
        player_list = "\n".join([f"🪑 Seat {i+1}: **{p['name']}** ({p['bet']:,} PALDOGS)" for i, p in enumerate(self.players)])
        empty_seats = 4 - len(self.players)
        if empty_seats > 0:
            player_list += f"\n" + "\n".join([f"🪑 Seat {len(self.players)+i+1}: *Empty*" for i in range(empty_seats)])
        
        embed.description = f"Up to 4 players can join this table. All players will play with the same deck against the dealer!\n\n{player_list}"
        embed.set_footer(text=f"Initiator: {self.initiator.display_name} | Max 4 Seats")
        return embed

    @nextcord.ui.button(label="Join Seat", style=nextcord.ButtonStyle.success)
    async def join_seat(self, button, interaction: nextcord.Interaction):
        if self.game_started: return
        if any(p['user'].id == interaction.user.id for p in self.players):
            await interaction.response.send_message("❌ You are already seated!", ephemeral=True)
            return
        if len(self.players) >= 4:
            await interaction.response.send_message("❌ This table is full!", ephemeral=True)
            return

        # Need to verify funds (since we use the initiator's bet for simplicity or allow custom)
        # For simplicity, we use the same bet as the initiator
        bet = self.players[0]['bet']
        stats = await db.get_player_by_discord(interaction.user.id)
        if not stats or stats['palmarks'] < bet:
            await interaction.response.send_message(f"❌ You need at least {bet:,} PALDOGS to join!", ephemeral=True)
            return

        self.players.append({
            'user': interaction.user,
            'steam_id': stats['steam_id'],
            'bet': bet,
            'hand': [],
            'status': 'waiting',
            'name': interaction.user.display_name
        })
        await interaction.response.edit_message(embed=self.make_lobby_embed(), view=self)

    @nextcord.ui.button(label="Start Game", style=nextcord.ButtonStyle.primary)
    async def start_game(self, button, interaction: nextcord.Interaction):
        if self.game_started: return
        if interaction.user.id != self.initiator.id:
            await interaction.response.send_message("❌ Only the initiator can start!", ephemeral=True)
            return

        self.game_started = True
        self.clear_items() # Remove Join/Start buttons
        
        # Deduct all bets securely
        for p in self.players:
            await db.add_palmarks(p['steam_id'], -p['bet'], f"Blackjack Table Bet")

        # Initial Deal
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        for p in self.players:
            p['hand'] = [self.deck.pop(), self.deck.pop()]
            p['status'] = 'playing'
            if self.calculate_value(p['hand']) == 21:
                p['status'] = 'blackjack'

        # Next player logic
        await self.next_turn(interaction)

    async def next_turn(self, interaction):
        # Find first player who is still 'playing'
        while self.current_player_idx < len(self.players):
            p = self.players[self.current_player_idx]
            if p['status'] == 'playing':
                break
            self.current_player_idx += 1
        
        if self.current_player_idx >= len(self.players):
            # Everyone finished, dealer's turn
            await self.dealer_turn(interaction)
        else:
            await self.show_game_state(interaction)

    async def show_game_state(self, interaction):
        p = self.players[self.current_player_idx]
        embed = nextcord.Embed(title="🃏 Blackjack Table - In Progress", color=0x34495e)
        
        dealer_val = self.get_value_label(self.dealer_hand) if False else "?" # Just for future logic
        embed.add_field(name="💼 Dealer", value=f"{self.format_hand(self.dealer_hand, True)}\n**Value:** ?", inline=False)
        for i, ply in enumerate(self.players):
            status_tag = f" ({ply['status'].upper()})" if ply['status'] != 'playing' else " 👈 **CURRENT TURN**"
            name = f"👤 {ply['name']}"
            if i == self.current_player_idx:
                name = f"🔥 __**{ply['name']}**__"
                
            # Privacy: Hide cards in public view until the end
            hand_display = "🎴 `[ ?? ]` `[ ?? ]`"
            val_display = "?"
            
            if ply['status'] == 'bust': 
                hand_display = f"💥 **BUST**\n{self.format_hand(ply['hand'])}"
                val_display = str(self.calculate_value(ply['hand']))
            elif ply['status'] == 'blackjack': 
                hand_display = f"🃏 **BLACKJACK!**\n{self.format_hand(ply['hand'])}"
                val_display = "21"
            elif ply['status'] == 'stood':
                hand_display = "📥 **STOOD** (Cards Hidden)"
                val_display = "?"
            
            embed.add_field(name=f"{name}{status_tag}", value=f"{hand_display}\n**Value:** {val_display}", inline=True)

        # Update controls
        self.clear_items()
        
        # Privacy Button
        peek_btn = nextcord.ui.Button(label="View My Cards", style=nextcord.ButtonStyle.success)
        async def peek_callback(inner_inter):
            # Find the specific player in the lobby
            target_player = next((pl for pl in self.players if pl['user'].id == inner_inter.user.id), None)
            if not target_player:
                await inner_inter.response.send_message("❌ You are not playing in this game!", ephemeral=True)
                return
            
            p_val = self.get_value_label(target_player['hand'])
            await inner_inter.response.send_message(
                f"🃏 **Your Hand:** {self.format_hand(target_player['hand'])}\n"
                f"🔢 **Value:** {p_val}", 
                ephemeral=True
            )
        peek_btn.callback = peek_callback
        self.add_item(peek_btn)

        # Game Controls (Only for current player)
        hit_btn = nextcord.ui.Button(label="Hit", style=nextcord.ButtonStyle.primary)
        stand_btn = nextcord.ui.Button(label="Stand", style=nextcord.ButtonStyle.secondary)
        
        async def hit_callback(inner_inter):
            if inner_inter.user.id != p['user'].id: 
                await inner_inter.response.send_message("⚠️ It's not your turn!", ephemeral=True)
                return
            p['hand'].append(self.deck.pop())
            if self.calculate_value(p['hand']) > 21:
                p['status'] = 'bust'
                self.current_player_idx += 1
                await self.next_turn(inner_inter)
            else:
                await self.show_game_state(inner_inter)

        async def stand_callback(inner_inter):
            if inner_inter.user.id != p['user'].id: 
                await inner_inter.response.send_message("⚠️ It's not your turn!", ephemeral=True)
                return
            p['status'] = 'stood'
            self.current_player_idx += 1
            await self.next_turn(inner_inter)

        hit_btn.callback = hit_callback
        stand_btn.callback = stand_callback
        self.add_item(hit_btn)
        self.add_item(stand_btn)

        if interaction.response.is_done():
            await interaction.edit_original_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def dealer_turn(self, interaction):
        self.clear_items()
        while self.calculate_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        
        d_val = self.calculate_value(self.dealer_hand)
        
        embed = nextcord.Embed(title="🃏 Blackjack Table - Results", color=0x2c3e50)
        dealer_text = f"{self.format_hand(self.dealer_hand)}\nValue: {d_val}"
        if d_val > 21: dealer_text += " **(BUST)**"
        embed.add_field(name="💼 Dealer", value=dealer_text, inline=False)

        for p in self.players:
            p_val = self.get_value_label(p['hand'])
            multiplier = 0
            res_text = ""
            
            # Determine result
            p_int_val = self.calculate_value(p['hand'])
            if p['status'] == 'blackjack':
                res_text = "WON (Blackjack!)"
                multiplier = 2.5
            elif p['status'] == 'bust':
                res_text = "BUSTED"
                multiplier = 0
            elif d_val > 21:
                res_text = "WON (Dealer Bust)"
                multiplier = 2
            elif d_val > p_int_val:
                res_text = "LOST"
                multiplier = 0
            elif d_val < p_int_val:
                res_text = "WON"
                multiplier = 2
            else:
                res_text = "TIE (Push)"
                multiplier = 1
                
            win_amt = int(p['bet'] * multiplier)
            if win_amt > 0:
                await db.add_palmarks(p['steam_id'], win_amt, f"BJ Table: {res_text}")
                res_text += f" (+{win_amt:,})"
            
            embed.add_field(name=f"👤 {p['name']}", value=f"{self.format_hand(p['hand'])}\nValue: {p_val}\n**{res_text}**", inline=True)

        if interaction.response.is_done():
            await interaction.edit_original_message(embed=embed, view=None)
        else:
            await interaction.response.edit_message(embed=embed, view=None)

        # Cleanup
        await asyncio.sleep(20)
        try:
            await self.message.delete()
        except:
            pass

    @commands.Cog.listener()
    async def on_message(self, message):
        """Automatically clean up user chatter in casino channels"""
        if message.author.bot:
            return
            
        from utils.config_manager import config
        roulette_cid = config.get('gambling_channel_id')
        blackjack_cid = config.get('blackjack_channel_id')
        
        if message.channel.id in [roulette_cid, blackjack_cid]:
            # Wait 5 seconds so they can see their message, then delete it
            await asyncio.sleep(5)
            try:
                await message.delete()
            except:
                pass

def setup(bot):
    bot.add_cog(Gambling(bot))

class RouletteBetModal(nextcord.ui.Modal):
    def __init__(self, choice, gambling_cog):
        super().__init__(title=f"Bet on {choice.upper()}")
        self.choice = choice
        self.gambling_cog = gambling_cog
        self.amount = nextcord.ui.TextInput(
            label="Amount of PALDOGS",
            placeholder="Min 10",
            min_length=1,
            max_length=10,
            required=True
        )
        self.add_item(self.amount)

    async def callback(self, interaction: nextcord.Interaction):
        try:
            amt = int(self.amount.value)
            if amt < 10:
                await interaction.response.send_message("❌ Minimum bet is 10!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Enter a valid number!", ephemeral=True)
            return
        
        await self.gambling_cog.place_record_bet(interaction, amt, self.choice)

class RouletteNumberModal(nextcord.ui.Modal):
    def __init__(self, gambling_cog):
        super().__init__(title="Bet on Specific Number")
        self.gambling_cog = gambling_cog
        self.number = nextcord.ui.TextInput(label="Number (0-36)", placeholder="Enter 0-36", min_length=1, max_length=2, required=True)
        self.amount = nextcord.ui.TextInput(label="Bet Amount", placeholder="Min 10", min_length=1, max_length=10, required=True)
        self.add_item(self.number)
        self.add_item(self.amount)

    async def callback(self, interaction: nextcord.Interaction):
        try:
            num = int(self.number.value)
            amt = int(self.amount.value)
            if not 0 <= num <= 36:
                await interaction.response.send_message("❌ Number must be 0-36!", ephemeral=True)
                return
            if amt < 10:
                await interaction.response.send_message("❌ Minimum bet is 10!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Enter valid numbers!", ephemeral=True)
            return
        
        await self.gambling_cog.place_record_bet(interaction, amt, "number", num)

class RouletteTableView(View):
    def __init__(self, gambling_cog):
        super().__init__(timeout=None)
        self.gambling_cog = gambling_cog

    @nextcord.ui.button(label="Bet Red 🔴", style=nextcord.ButtonStyle.danger)
    async def bet_red(self, button, interaction):
        await interaction.response.send_modal(RouletteBetModal("red", self.gambling_cog))

    @nextcord.ui.button(label="Bet Black ⚫", style=nextcord.ButtonStyle.secondary)
    async def bet_black(self, button, interaction):
        await interaction.response.send_modal(RouletteBetModal("black", self.gambling_cog))

    @nextcord.ui.button(label="Bet Even", style=nextcord.ButtonStyle.primary)
    async def bet_even(self, button, interaction):
        await interaction.response.send_modal(RouletteBetModal("even", self.gambling_cog))

    @nextcord.ui.button(label="Bet Odd", style=nextcord.ButtonStyle.primary)
    async def bet_odd(self, button, interaction):
        await interaction.response.send_modal(RouletteBetModal("odd", self.gambling_cog))

    @nextcord.ui.button(label="Bet Number 🔢", style=nextcord.ButtonStyle.success)
    async def bet_number(self, button, interaction):
        await interaction.response.send_modal(RouletteNumberModal(self.gambling_cog))
