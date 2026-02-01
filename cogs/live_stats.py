import nextcord
import asyncio
from datetime import datetime
from typing import Optional
from utils.database import db
from utils.config_manager import config
from utils.rest_api import rest_api
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
        """Create premium statistics embed with visual elements"""
        # Fetch a larger pool for the leaderboard and filter out max rank (Champion)
        leaderboard_raw = await db.get_leaderboard('palmarks', limit=20)
        leaderboard = [p for p in leaderboard_raw if p.get('rank') != 'Champion'][:5]
        
        # Fetch current online players from REST API
        current_players = []
        player_count = 0
        if rest_api.is_configured():
            player_data = await rest_api.get_player_list()
            if player_data:
                current_players = player_data.get('players', [])
                player_count = len(current_players)
        
        # Dynamic color based on activity
        if player_count > 0:
            color = 0x00FF00  # Green - Players online
        elif len(leaderboard) > 0:
            color = 0xFFFF00  # Yellow - No one online but server has history
        else:
            color = 0xFF6B6B  # Red - Low activity
        
        # Total players count for header
        total_players_registered = await db.get_total_players_count()

        # Create embed with dynamic title
        embed = nextcord.Embed(
            title="📊 ═══ SERVER LIVE DASHBOARD ═══",
            description=(
                f"```ansi\n\u001b[1;36m⚡ Status: {'ONLINE' if player_count > 0 or rest_api.is_configured() else 'OFFLINE'}\u001b[0m\n"
                f"\u001b[1;32m👥 Population: {player_count} Online • {total_players_registered} Registered\u001b[0m\n```"
            ),
            color=color,
            timestamp=datetime.now()
        )
        
        # Current Players Section
        if player_count > 0:
            player_entries = []
            for p in current_players[:15]:
                name = p.get('name', 'Unknown')
                # Add crown emoji for MAX rank players (Champion)
                player_stats = await db.get_player_stats_by_name(name)
                crown = " 👑" if player_stats and player_stats.get('rank') == 'Champion' else ""
                player_entries.append(f"🎮 **{name}**{crown}")
            
            player_names = "\n".join(player_entries)
            if len(current_players) > 15:
                player_names += f"\n*... and {len(current_players) - 15} more*"
            
            embed.add_field(
                name="🟢 ═══ ONLINE PLAYERS ═══",
                value=player_names,
                inline=False
            )
        else:
            embed.add_field(
                name="🛡️ ═══ SERVER STATUS ═══",
                value="*The world is currently quiet. No players online.*",
                inline=False
            )
        
        # Premium leaderboard with visual ranking and progression
        if leaderboard:
            medals = ["🥇", "🥈", "🥉", "🏅", "🎖️"]
            max_palmarks = leaderboard[0].get('palmarks', 1) if leaderboard else 1
            
            leaderboard_lines = []
            for i, player in enumerate(leaderboard):
                medal = medals[i] if i < len(medals) else f"`#{i+1}`"
                rank_emoji = self.get_rank_emoji(player.get('rank', 'Trainer'))
                player_name = player['player_name']
                
                if 'palmarks' in player:
                    dc = player['palmarks']
                    bar = self.create_progress_bar(dc, max_palmarks, 8)
                    
                    # Find player by name to get steam_id and other stats
                    stats = await db.get_player_stats_by_name(player_name)
                    lvl_info = ""
                    
                    if stats:
                        level = stats.get('level', 1)
                        progress = await rank_system.get_progress_to_next_rank(stats['steam_id'])
                        
                        if progress:
                            percentage = progress['percentage']
                            # Create mini progress bar for Level
                            lvl_bar = self.create_progress_bar(percentage, 100, 6)
                            lvl_info = f"\n    `{lvl_bar}` Lv.{level} ({percentage}% to Lv.{level+1})"
                    
                    rank_name = player.get('rank', 'Trainer')
                    leaderboard_lines.append(
                        f"{medal} {rank_emoji} **{player_name}** (`{rank_name}`)\n"
                        f"    `{bar}` {dc:,} PALDOGS{lvl_info}"
                    )
            
            leaderboard_text = "\n".join(leaderboard_lines) if leaderboard_lines else "```No players yet```"
            
            embed.add_field(
                name="🏆 ═══ TOP PLAYERS ═══",
                value=leaderboard_text,
                inline=False
            )
        
        # Footer with live indicator
        embed.set_footer(
            text="🟢 LIVE • Updates every 5 minutes • Powered by Paltastic",
            icon_url="https://i.imgur.com/AfFp7pu.png"
        )
        
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
