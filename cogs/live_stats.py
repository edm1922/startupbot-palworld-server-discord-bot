import nextcord
import asyncio
from datetime import datetime
from typing import Optional
from utils.database import db
from utils.config_manager import config
from utils.rest_api import rest_api
from utils.server_utils import get_server_state, ServerState
from cogs.rank_system import rank_system

class LiveStatsDisplay:
    """Manages live statistics display in Discord channel"""
    
    def __init__(self, bot):
        self.bot = bot
        self.stats_message_id = config.get('stats_message_id', None)
        self.stats_channel_id = config.get('stats_channel_id', None)
        self.update_interval = 300  # 5 minutes (in seconds)
        self.running = False
    
    def set_channel(self, channel_id: int):
        """Set the stats channel"""
        self.stats_channel_id = channel_id
        # Load existing message ID from config
        self.stats_message_id = config.get('stats_message_id', None)
    
    def create_progress_bar(self, current: int, maximum: int, length: int = 10) -> str:
        """Create a visual progress bar"""
        if maximum == 0:
            return "░" * length
        filled = int((current / maximum) * length)
        return "█" * filled + "░" * (length - filled)
    
    async def create_stats_embed(self) -> nextcord.Embed:
        """Create an ultra-minimalist, high-end dashboard embed"""
        # Fetch leaderboard data
        leaderboard_raw = await db.get_leaderboard('palmarks', limit=10)
        leaderboard = [p for p in leaderboard_raw if p.get('rank') != 'Champion'][:5]
        
        # Fetch current online players
        current_players = []
        player_count = 0
        if rest_api.is_configured():
            player_data = await rest_api.get_player_list()
            if player_data:
                current_players = player_data.get('players', [])
                player_count = len(current_players)
        
        # Get server state
        server_state = get_server_state()
        state_info = {
            ServerState.OFFLINE: ("OFFLINE", 0xFF4B2B, "🔴", "31", "41"),
            ServerState.STARTING: ("STARTING", 0xFFA500, "🟠", "33", "43"),
            ServerState.ONLINE: ("ONLINE", 0x33FF33, "🟢", "32", "42"),
            ServerState.STOPPING: ("STOPPING", 0xFF4B2B, "🔴", "31", "41")
        }
        status_text, color, dot, fg, bg = state_info.get(server_state, ("UNKNOWN", 0x808080, "⚪", "37", "40"))
        
        total_players = await db.get_total_players_count()

        # Build Title & Description
        embed = nextcord.Embed(title="Palworld • Server Dashboard", color=color, timestamp=datetime.now())
        
        # Top Note (Online Players)
        if player_count > 0:
            names = []
            for p in current_players:
                n = p.get('name', 'Unknown')
                stats = await db.get_player_stats_by_name(n)
                tag = "⭐" if stats and stats.get('rank') == 'Champion' else ""
                names.append(f"`{n}{tag}`")
            embed.description = f"Currently active: {', '.join(names)}"
        else:
            embed.description = "The world is currently quiet. No players online."

        # Two-Column Status Blocks (ANSI)
        # Status Box
        status_box = f"```ansi\n\u001b[1;37m\u001b[{bg}m {status_text} \u001b[0m\n```"
        embed.add_field(name=f"{dot} Status", value=status_box, inline=True)
        
        # Population Box
        pop_box = f"```ansi\n\u001b[1;37m\u001b[40m {player_count} Online • {total_players} Registered \u001b[0m\n```"
        embed.add_field(name="🌐 Population", value=pop_box, inline=True)

        # Leaderboard Section
        if leaderboard:
            lb_lines = []
            medals = ["🥇", "🥈", "🥉", "🏅", "🎖️"]
            for i, p in enumerate(leaderboard):
                medal = medals[i]
                rank_icon = self.get_rank_emoji(p.get('rank', 'Trainer'))
                p_name = p['player_name']
                pm = p.get('palmarks', 0)
                
                stats = await db.get_player_stats_by_name(p_name)
                lvl = stats.get('level', 1) if stats else 1
                
                # Single-line clean format
                lb_lines.append(f"{medal} {rank_icon} **{p_name}** • {pm:,} PD • Lv.{lvl}")
            
            embed.add_field(name="= Top Players —", value="\n".join(lb_lines), inline=False)

        # 3. LATEST GLOBAL ACTIVITY (Integrated back into minimalist design)
        try:
            with db.lock:
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.player_name, r.reward_type, r.description 
                    FROM reward_history r
                    JOIN players p ON r.steam_id = p.steam_id
                    ORDER BY r.timestamp DESC LIMIT 3
                ''')
                activities = cursor.fetchall()
                if activities:
                    act_lines = []
                    for act in activities:
                        desc = act['description'].replace("Chest Open: ", "opened a ")
                        act_lines.append(f"🕒 **{act['player_name']}** {desc}")
                    embed.add_field(name="= Recent Activity —", value="\n".join(act_lines), inline=False)
        except Exception:
            pass

        # Footer Fields
        embed.add_field(name="= Live updates every 5 minutes", value="• Powered by Paltastic", inline=False)
        
        return embed
    
    def get_rank_emoji(self, rank: str) -> str:
        """Get emoji for rank"""
        rank_emojis = {
            'Trainer': '🎓',
            'Elite Trainer': '🎖️',
            'Gym Leader': '⭐',
            'Ace Trainer': '🔥',
            'Pal Master': '🧿',
            'Champion': '👑'
        }
        return rank_emojis.get(rank, '🎓')
    
    async def update_stats_message(self):
        """Update the stats message"""
        if not self.stats_channel_id:
            print("⚠️ Stats channel not configured")
            return
        
        try:
            channel = self.bot.get_channel(self.stats_channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(self.stats_channel_id)
                except Exception:
                    print(f"⚠️ Stats channel {self.stats_channel_id} not found in cache or via API")
                    return
            
            embed = await self.create_stats_embed()
            
            # If message exists, edit it; otherwise create new
            if self.stats_message_id:
                try:
                    message = await channel.fetch_message(self.stats_message_id)
                    await message.edit(embed=embed)
                    print(f"✅ Updated stats message at {datetime.now().strftime('%H:%M:%S')}")
                except nextcord.NotFound:
                    # Message was deleted, create new one
                    message = await channel.send(embed=embed)
                    self.stats_message_id = message.id
                    config.set('stats_message_id', message.id)
                    print(f"✅ Created new stats message (old one was deleted)")
            else:
                # Create new message
                message = await channel.send(embed=embed)
                self.stats_message_id = message.id
                config.set('stats_message_id', message.id)
                print(f"✅ Created stats message with ID: {self.stats_message_id}")
        
        except Exception as e:
            print(f"❌ Error updating stats message: {e}")
    
    async def start_auto_update(self):
        """Start automatic stats updates"""
        if self.running:
            print("⚠️ Stats auto-update already running")
            return
        
        self.running = True
        print(f"🔄 Starting stats auto-update (every {self.update_interval}s)")
        
        while self.running:
            try:
                await self.update_stats_message()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                print(f"❌ Error in stats auto-update loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    def stop_auto_update(self):
        """Stop automatic stats updates"""
        self.running = False
        print("🛑 Stopped stats auto-update")
    
    async def force_update(self):
        """Force an immediate stats update"""
        await self.update_stats_message()


# Helper function to format time
def format_playtime(seconds: int) -> str:
    """Format seconds into human-readable playtime"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
