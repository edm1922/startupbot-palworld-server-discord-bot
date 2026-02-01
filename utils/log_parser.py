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
            'chat': re.compile(r"\[.*?\]\[info\] \[Chat::Global\]\['(.+?)' \(UserId=(steam_\d+), IP=.+?\)\](?:\[.*?\])*: (.+)"),
            'combat': re.compile(r"\[.*?\]\[info\] '(.+?)' \(UserId=(steam_\d+), IP=.+?\) dealing damage \((\d+)\) to '(.+?)'"),
            'kill': re.compile(r"\[.*?\]\[info\] '(.+?)' \(UserId=(steam_\d+), IP=.+?\) killed '(.+?)'")
        }
        
        # Reward values (Both PALDOGS and EXP)
        self.rewards = {
            'building': {
                'Wooden': {'paldogs': 5, 'exp': 10},
                'Stone': {'paldogs': 10, 'exp': 20},
                'Metal': {'paldogs': 15, 'exp': 30},
                'default': {'paldogs': 5, 'exp': 10}
            },
            'crafting': {
                'default': {'paldogs': 2, 'exp': 5},
                'Plastic': {'paldogs': 5, 'exp': 10},
                'Cement': {'paldogs': 5, 'exp': 10},
                'SteelIngot': {'paldogs': 5, 'exp': 10},
                'IronIngot': {'paldogs': 3, 'exp': 8},
                'CopperIngot': {'paldogs': 2, 'exp': 5},
                'PalSphere': {'paldogs': 10, 'exp': 20},
                'Cake': {'paldogs': 15, 'exp': 50}
            },
            'tech': {'paldogs': 50, 'exp': 200},
            'chat': {'paldogs': 1, 'exp': 2},
            'combat': {'paldogs': 0, 'exp': 1}, # 1 exp per damage instance? Maybe too much. Let's say per hit.
            'kill': {'paldogs': 10, 'exp': 50},
            'playtime_per_hour': {'paldogs': 10, 'exp': 100},
            'daily_login': {'paldogs': 25, 'exp': 100}
        }
        
        self.rank_multipliers = {
            'Trainer': 1.0,
            'Gym Leader': 2.0,
            'Champion': 3.0
        }
        
        self.processed_lines = set()  # Track processed log lines to avoid duplicates

    def get_crafting_reward(self, item_name: str) -> Dict[str, int]:
        """Calculate PALDOGS and EXP for crafting"""
        for key, value in self.rewards['crafting'].items():
            if key in item_name:
                return value
        return self.rewards['crafting']['default']

    def get_building_reward(self, building_name: str) -> Dict[str, int]:
        """Calculate PALDOGS and EXP for building"""
        for material in ['Wooden', 'Stone', 'Metal']:
            if material in building_name:
                return self.rewards['building'][material]
        return self.rewards['building']['default']
    
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

                elif activity_type == 'combat':
                    player_name, steam_id, damage, target = match.groups()
                    return {
                        'type': 'combat',
                        'player_name': player_name,
                        'steam_id': steam_id,
                        'damage': int(damage),
                        'target': target,
                        'reward': self.rewards['combat']
                    }

                elif activity_type == 'kill':
                    player_name, steam_id, target = match.groups()
                    return {
                        'type': 'kill',
                        'player_name': player_name,
                        'steam_id': steam_id,
                        'target': target,
                        'reward': self.rewards['kill']
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
            
            # 1. Prepare base arrival messages
            in_game_broadcast = ""
            current_rank = old_rank
            active_announcer = stats.get('active_announcer', 'default') if stats else 'default'
            
            if not is_first_today:
                in_game_broadcast = rank_system.get_join_message(active_announcer, player_name)
                msg = f"📥 **{player_name}** joined the server"
                return 0, msg, in_game_broadcast

            # 2. Daily Rewards
            paldogs_reward = self.rewards['daily_login']['paldogs']
            exp_reward = self.rewards['daily_login']['exp']
            
            # Streak bonus
            streak_p_bonus = 0
            streak_e_bonus = 0
            streak_msg = ""
            if streak >= 30: streak_p_bonus, streak_e_bonus, streak_msg = 500, 1000, "🎊 30-DAY STREAK!"
            elif streak >= 14: streak_p_bonus, streak_e_bonus, streak_msg = 250, 500, "🎉 14-DAY STREAK!"
            elif streak >= 7: streak_p_bonus, streak_e_bonus, streak_msg = 100, 250, "🔥 7-DAY STREAK!"
            elif streak >= 3: streak_p_bonus, streak_e_bonus, streak_msg = 50, 100, "⭐ 3-DAY STREAK!"
            
            total_paldogs = await self.apply_rank_multiplier(steam_id, paldogs_reward + streak_p_bonus)
            total_exp = exp_reward + streak_e_bonus
            
            await db.add_palmarks(steam_id, total_paldogs, f"Daily login (Streak: {streak})")
            leveled_up, new_level = await db.add_experience(steam_id, total_exp)
            
            new_rank, ranked_up = await rank_system.check_and_update_rank(steam_id)
            current_rank = new_rank if ranked_up else old_rank
            
            rank_info = rank_system.get_rank_info(current_rank)
            msg = f"🎉 {rank_info['emoji']} **{player_name}** logged in!\n💰 +{total_paldogs} PALDOGS | ✨ +{total_exp} EXP"
            
            if leveled_up:
                msg += f"\n🆙 **LEVEL UP!** You are now level **{new_level}**!"
            if ranked_up:
                msg += f"\n🎊 **RANK UP!** You are now a **{new_rank}**!"
            if streak_msg:
                msg += f"\n{streak_msg} ({streak} days)"

            in_game_broadcast = rank_system.get_join_message(active_announcer, player_name)
            if leveled_up: in_game_broadcast += f" ✨ Level UP! {new_level}!"
            if ranked_up: in_game_broadcast += f" {rank_system.get_rank_message(active_announcer, player_name, new_rank)}"
            
            return total_paldogs, msg, in_game_broadcast
        
        elif activity_type == 'logout':
            await db.record_logout(steam_id)
            return 0, "", ""
        
        elif activity_type == 'building':
            await db.add_activity(steam_id, 'building', 1)
            p_base = activity['reward']['paldogs']
            e_base = activity['reward']['exp']
            total_paldogs = await self.apply_rank_multiplier(steam_id, p_base)
            total_exp = e_base
            
            await db.add_palmarks(steam_id, total_paldogs, f"Built {activity['building']}")
            leveled_up, new_level = await db.add_experience(steam_id, total_exp)
            
            new_rank, ranked_up = await rank_system.check_and_update_rank(steam_id)
            msg = ""
            in_game_broadcast = ""
            
            if leveled_up or ranked_up:
                active_announcer = stats.get('active_announcer', 'default') if stats else 'default'
                rank_info = rank_system.get_rank_info(new_rank if ranked_up else old_rank)
                if leveled_up: msg += f"🆙 **LEVEL UP!** **{player_name}** is now level **{new_level}**!\n"
                if ranked_up: 
                    msg += f"🎊 **RANK UP!** {rank_info['emoji']} **{player_name}** is now a **{new_rank}**!"
                    in_game_broadcast = rank_system.get_rank_message(active_announcer, player_name, new_rank)
            
            return total_paldogs, msg, in_game_broadcast
        
        elif activity_type == 'crafting':
            await db.add_activity(steam_id, 'crafting', 1)
            p_base = activity['reward']['paldogs']
            e_base = activity['reward']['exp']
            total_paldogs = await self.apply_rank_multiplier(steam_id, p_base)
            total_exp = e_base
            
            await db.add_palmarks(steam_id, total_paldogs, f"Crafted {activity['item']}")
            leveled_up, new_level = await db.add_experience(steam_id, total_exp)
            
            new_rank, ranked_up = await rank_system.check_and_update_rank(steam_id)
            msg = ""
            if leveled_up: msg += f"🆙 **LEVEL UP! {player_name}** reached Level **{new_level}**!"
            return total_paldogs, msg, ""
        
        elif activity_type == 'tech':
            await db.add_activity(steam_id, 'tech', 1)
            total_paldogs = await self.apply_rank_multiplier(steam_id, activity['reward']['paldogs'])
            total_exp = activity['reward']['exp']
            
            await db.add_palmarks(steam_id, total_paldogs, f"Unlocked {activity['tech']}")
            leveled_up, new_level = await db.add_experience(steam_id, total_exp)
            
            new_rank, ranked_up = await rank_system.check_and_update_rank(steam_id)
            msg = ""
            if leveled_up: msg += f"🆙 **LEVEL UP! {player_name}** reached Level **{new_level}**!"
            return total_paldogs, msg, ""
        
        elif activity_type == 'chat':
            await db.add_activity(steam_id, 'chat', 1)
            await db.add_experience(steam_id, self.rewards['chat']['exp'])
            return 0, "", ""

        elif activity_type == 'combat':
            # Award small amount of EXP for combat activity
            await db.add_experience(steam_id, activity['reward']['exp'])
            return 0, "", ""

        elif activity_type == 'kill':
            total_paldogs = await self.apply_rank_multiplier(steam_id, activity['reward']['paldogs'])
            total_exp = activity['reward']['exp']
            await db.add_palmarks(steam_id, total_paldogs, f"Killed {activity['target']}")
            leveled_up, new_level = await db.add_experience(steam_id, total_exp)
            msg = ""
            if leveled_up: msg = f"🆙 **LEVEL UP! {player_name}** reached Level **{new_level}**!"
            return total_paldogs, msg, ""
        
        return 0, "", ""
    
    async def tail_log_file(self, log_path: str, callback=None):
        """Tail a log file and process new lines (Async)"""
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
                        reward, message, broadcast = await self.process_activity(activity)
                        
                        if callback and message:
                            callback(activity, reward, message)
                else:
                    # No new line, wait a bit
                    await asyncio.sleep(0.1)


# Global instance
log_parser = PalDefenderLogParser()
