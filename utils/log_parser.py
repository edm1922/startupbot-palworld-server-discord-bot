import re
import os
from datetime import datetime
from typing import Dict, Optional, Tuple
from utils.database import db
from utils.rcon_utility import rcon_util
from cogs.rank_system import rank_system

class PalDefenderLogParser:
    """Parser for PalDefender log files to extract player activities"""
    
    def __init__(self):
        # Regex patterns for log parsing
        self.patterns = {
            'login': re.compile(r"\[.*?\]\[info\] '(.+?)' \(UserId=(steam_\d+), IP=(.+?)\) has logged in.*"),
            'logout': re.compile(r"\[.*?\]\[info\] '(.+?)' \(UserId=(steam_\d+), IP=(.+?)\) has logged out.*"),
            'building': re.compile(r"\[.*?\]\[info\] '(.+?)' \(UserId=(steam_\d+), IP=.+?\) has build an '(.+?)'"),
            'crafting': re.compile(r"\[.*?\]\[info\] '(.+?)' \(UserId=(steam_\d+), IP=.+?\) started crafting '(.+?)'"),
            'tech': re.compile(r"\[.*?\]\[info\] '(.+?)' \(UserId=(steam_\d+), IP=.+?\) unlocking Technology: '(.+?)'"),
            'chat': re.compile(r"\[.*?\]\[info\] \[Chat::Global\]\['(.+?)' \(UserId=(steam_\d+), IP=.+?\)\](?:\[.*?\])*: (.+)")
        }
        
        # Reward values
        self.rewards = {
            'building': {
                'Wooden': 5,
                'Stone': 10,
                'Metal': 15,
                'default': 5
            },
            'crafting': {
                'default': 2,
                'Plastic': 5,
                'Cement': 5,
                'SteelIngot': 5,
                'IronIngot': 3,
                'CopperIngot': 2,
                'PalSphere': 10,
                'Cake': 15
            },
            'tech': 50,
            'chat': 1,
            'playtime_per_hour': 10,
            'daily_login': 25
        }
        
        self.rank_multipliers = {
            'Trainer': 1.0,
            'Gym Leader': 2.0,
            'Champion': 3.0
        }
        
        self.processed_lines = set()  # Track processed log lines to avoid duplicates
    
    def get_building_reward(self, building_name: str) -> int:
        """Calculate reward for building based on type"""
        for material in ['Wooden', 'Stone', 'Metal']:
            if material in building_name:
                return self.rewards['building'][material]
        return self.rewards['building']['default']
    
    def get_crafting_reward(self, item_name: str) -> int:
        """Calculate reward for crafting based on item"""
        # Remove null terminator if present
        item_name = item_name.replace('\x00', '')
        
        for key, value in self.rewards['crafting'].items():
            if key in item_name:
                return value
        return self.rewards['crafting']['default']
    
    async def apply_rank_multiplier(self, steam_id: str, base_reward: int) -> int:
        """Apply rank multiplier to reward (Async)"""
        stats = await db.get_player_stats(steam_id)
        if stats:
            rank = stats.get('rank', 'Trainer')
            multiplier = self.rank_multipliers.get(rank, 1.0)
            return int(base_reward * multiplier)
        return base_reward
    
    def parse_line(self, line: str, line_hash: str = None) -> Optional[Dict]:
        """Parse a single log line and return activity data"""
        # Avoid processing duplicate lines
        if line_hash and line_hash in self.processed_lines:
            return None
        
        # Try each pattern
        for activity_type, pattern in self.patterns.items():
            match = pattern.search(line)
            if match:
                if line_hash:
                    self.processed_lines.add(line_hash)
                
                if activity_type == 'login':
                    player_name, steam_id, ip = match.groups()
                    return {
                        'type': 'login',
                        'player_name': player_name,
                        'steam_id': steam_id,
                        'ip': ip
                    }
                
                elif activity_type == 'logout':
                    player_name, steam_id, ip = match.groups()
                    return {
                        'type': 'logout',
                        'player_name': player_name,
                        'steam_id': steam_id,
                        'ip': ip
                    }
                
                elif activity_type == 'building':
                    player_name, steam_id, building = match.groups()
                    reward = self.get_building_reward(building)
                    return {
                        'type': 'building',
                        'player_name': player_name,
                        'steam_id': steam_id,
                        'building': building,
                        'reward': reward
                    }
                
                elif activity_type == 'crafting':
                    player_name, steam_id, item = match.groups()
                    reward = self.get_crafting_reward(item)
                    return {
                        'type': 'crafting',
                        'player_name': player_name,
                        'steam_id': steam_id,
                        'item': item,
                        'reward': reward
                    }
                
                elif activity_type == 'tech':
                    player_name, steam_id, tech = match.groups()
                    return {
                        'type': 'tech',
                        'player_name': player_name,
                        'steam_id': steam_id,
                        'tech': tech,
                        'reward': self.rewards['tech']
                    }
                
                elif activity_type == 'chat':
                    player_name, steam_id, message = match.groups()
                    return {
                        'type': 'chat',
                        'player_name': player_name,
                        'steam_id': steam_id,
                        'message': message,
                        'reward': self.rewards['chat']
                    }
        
        return None
    
    async def process_activity(self, activity: Dict) -> Tuple[int, str, str]:
        """Process activity and update database, return reward amount, discord message, and in-game message"""
        activity_type = activity['type']
        steam_id = activity['steam_id']
        player_name = activity['player_name']
        
        # Ensure player exists
        await db.upsert_player(steam_id, player_name)
        
        # Track initial rank to detect rank-up
        stats = await db.get_player_stats(steam_id)
        old_rank = stats.get('rank', 'Trainer') if stats else 'Trainer'
        
        msg = ""
        in_game_broadcast = ""
        total_reward = 0
        
        if activity_type == 'login':
            streak, is_first_today = await db.record_login(steam_id, player_name)
            
            # 1. Prepare base arrival messages even if no reward
            in_game_broadcast = ""
            current_rank = old_rank
            active_announcer = stats.get('active_announcer', 'default') if stats else 'default'
            
            # If not the first today, we still want to announce arrival but NO rewards
            if not is_first_today:
                in_game_broadcast = rank_system.get_join_message(active_announcer, player_name)
                
                # For Discord, just a simple arrival message if you want, or nothing
                # Let's return a simple msg so the user knows they are recognized
                msg = f"📥 **{player_name}** joined the server (Welcome back!)"
                return 0, msg, in_game_broadcast

            # 2. Process Daily Rewards (Only if is_first_today is True)
            base_reward = self.rewards['daily_login']
            
            # Calculate streak bonus
            streak_bonus = 0
            streak_msg = ""
            
            if streak >= 30:
                streak_bonus = 500
                streak_msg = "🎊 30-DAY STREAK BONUS!"
            elif streak >= 14:
                streak_bonus = 250
                streak_msg = "🎉 14-DAY STREAK BONUS!"
            elif streak >= 7:
                streak_bonus = 100
                streak_msg = "🔥 7-DAY STREAK BONUS!"
            elif streak >= 3:
                streak_bonus = 50
                streak_msg = "⭐ 3-DAY STREAK BONUS!"
            
            total_reward = base_reward + streak_bonus
            
            if total_reward > 0:
                total_reward = await self.apply_rank_multiplier(steam_id, total_reward)
                await db.add_palmarks(steam_id, total_reward, f"Daily login (Streak: {streak})")
                
                # Check for rank up immediately after adding login reward
                new_rank, ranked_up = await rank_system.check_and_update_rank(steam_id)
                
                # Get virtual rewards based on rank and streak
                current_rank = new_rank if ranked_up else old_rank
                virtual_rewards = rank_system.get_daily_rewards(current_rank, streak)
                
                # Create Discord message for the virtual economy
                rank_emoji = rank_system.get_rank_info(current_rank)['emoji']
                msg = f"🎉 {rank_emoji} **{player_name}** logged in! +{total_reward} PALDOGS earned."
                
                # List virtual items/bonuses added to Discord profile
                items_list = []
                for item_id, amount in virtual_rewards['items'].items():
                    items_list.append(f"{amount}x {item_id}")
                if virtual_rewards['exp'] > 0:
                    items_list.append(f"{virtual_rewards['exp']} Rank EXP")
                
                if items_list:
                    msg += f"\n🎁 **Discord Rewards:** {', '.join(items_list)}"
                
                if streak > 1:
                    msg += f"\n🔥 **{streak}-day streak!**"
                
                if streak_msg:
                    msg += f"\n{streak_msg}"
                
                # Rank up notification
                if ranked_up:
                    new_rank_emoji = rank_system.get_rank_info(new_rank)['emoji']
                    msg += f"\n\n🎊 **RANK UP!** {new_rank_emoji} You are now a **{new_rank}**!"
                    msg += f"\n✨ Reward multiplier increased to {rank_system.get_rank_info(new_rank)['multiplier']}x!"

                # Create Exclusive In-Game Announcement for Arrival using active announcer
                in_game_broadcast = rank_system.get_join_message(active_announcer, player_name)
                
                # If they ranked up, we also add the celebration
                if ranked_up:
                    rank_msg = rank_system.get_rank_message(active_announcer, player_name, new_rank)
                    # We can either append or replace. Let's send a combined or separate broadcast.
                    # For now, let's append it as a celebratory line.
                    in_game_broadcast += f" {rank_msg}"
                
                return total_reward, msg, in_game_broadcast
            return 0, "", ""
        
        elif activity_type == 'logout':
            await db.record_logout(steam_id)
            return 0, "", ""
        
        elif activity_type == 'building':
            await db.add_activity(steam_id, 'building', 1)
            total_reward = await self.apply_rank_multiplier(steam_id, activity['reward'])
            await db.add_palmarks(steam_id, total_reward, f"Built {activity['building']}")
            
            # Check for real-time rank up
            new_rank, ranked_up = await rank_system.check_and_update_rank(steam_id)
            if ranked_up:
                active_announcer = stats.get('active_announcer', 'default') if stats else 'default'
                new_rank_emoji = rank_system.get_rank_info(new_rank)['emoji']
                msg = f"🎊 **RANK UP!** {new_rank_emoji} **{player_name}** has reached the rank of **{new_rank}**!"
                in_game_broadcast = rank_system.get_rank_message(active_announcer, player_name, new_rank)
            
            return total_reward, msg, in_game_broadcast
        
        elif activity_type == 'crafting':
            await db.add_activity(steam_id, 'crafting', 1)
            total_reward = await self.apply_rank_multiplier(steam_id, activity['reward'])
            await db.add_palmarks(steam_id, total_reward, f"Crafted {activity['item']}")
            
            # Check for real-time rank up
            new_rank, ranked_up = await rank_system.check_and_update_rank(steam_id)
            if ranked_up:
                new_rank_emoji = rank_system.get_rank_info(new_rank)['emoji']
                msg = f"🎊 **RANK UP!** {new_rank_emoji} **{player_name}** has reached the rank of **{new_rank}**!"
                in_game_broadcast = f"🎊 RANK UP! {player_name} is now a {new_rank}!"
                
            return total_reward, msg, in_game_broadcast
        
        elif activity_type == 'tech':
            await db.add_activity(steam_id, 'tech', 1)
            total_reward = await self.apply_rank_multiplier(steam_id, activity['reward'])
            await db.add_palmarks(steam_id, total_reward, f"Unlocked {activity['tech']}")
            
            # Check for real-time rank up
            new_rank, ranked_up = await rank_system.check_and_update_rank(steam_id)
            if ranked_up:
                new_rank_emoji = rank_system.get_rank_info(new_rank)['emoji']
                msg = f"🎊 **RANK UP!** {new_rank_emoji} **{player_name}** has reached the rank of **{new_rank}**!"
                in_game_broadcast = f"🎊 RANK UP! {player_name} is now a {new_rank}!"
                
            return total_reward, msg, in_game_broadcast
        
        elif activity_type == 'chat':
            await db.add_activity(steam_id, 'chat', 1)
            return 0, "", ""
        
        return 0, "", ""
        
        return 0, "", ""
    
    def tail_log_file(self, log_path: str, callback=None):
        """Tail a log file and process new lines"""
        if not os.path.exists(log_path):
            print(f"⚠️ Log file not found: {log_path}")
            return
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Go to end of file
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    line_hash = hash(line)
                    activity = self.parse_line(line, str(line_hash))
                    
                    if activity:
                        reward, message = self.process_activity(activity)
                        
                        if callback and message:
                            callback(activity, reward, message)
                else:
                    # No new line, wait a bit
                    import time
                    time.sleep(0.1)


# Global instance
log_parser = PalDefenderLogParser()
