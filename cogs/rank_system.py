from utils.database import db
from typing import Dict, Tuple, List, Optional
import json
import os

class RankSystem:
    """Manages player rank progression and rewards"""
    
    def __init__(self):
        # Professional Rank Progression (Higher thresholds for grindy feel)
        self.ranks = {
            'Trainer': {
                'min_palmarks': 0,
                'max_palmarks': 4999,
                'multiplier': 1.0,
                'emoji': '🎓',
                'daily_reward_items': {'PALDOGS': 100},
                'daily_reward_exp': 50,
                'color': 0x95a5a6 # Gray
            },
            'Elite Trainer': {
                'min_palmarks': 5000,
                'max_palmarks': 14999,
                'multiplier': 1.5,
                'emoji': '🎖️',
                'daily_reward_items': {'PALDOGS': 250, 'PalSphere': 5},
                'daily_reward_exp': 100,
                'color': 0x3498db # Blue
            },
            'Gym Leader': {
                'min_palmarks': 15000,
                'max_palmarks': 44999,
                'multiplier': 2.0,
                'emoji': '⭐',
                'daily_reward_items': {'PALDOGS': 500, 'PalSphere_Mega': 5},
                'daily_reward_exp': 200,
                'color': 0xf1c40f # Gold
            },
            'Ace Trainer': {
                'min_palmarks': 45000,
                'max_palmarks': 99999,
                'multiplier': 2.5,
                'emoji': '🔥',
                'daily_reward_items': {'PALDOGS': 1000, 'PalSphere_Giga': 5},
                'daily_reward_exp': 400,
                'color': 0xe67e22 # Orange
            },
            'Pal Master': {
                'min_palmarks': 100000,
                'max_palmarks': 249999,
                'multiplier': 3.0,
                'emoji': '🧿',
                'daily_reward_items': {'PALDOGS': 2500, 'PalSphere_Master': 5},
                'daily_reward_exp': 800,
                'color': 0x9b59b6 # Purple
            },
            'Champion': {
                'min_palmarks': 250000,
                'max_palmarks': 9999999,
                'multiplier': 4.0,
                'emoji': '👑',
                'daily_reward_items': {'PALDOGS': 5000, 'PalSphere_Ultimate': 5},
                'daily_reward_exp': 1500,
                'color': 0xe74c3c # Red
            }
        }
        
        # Consistent rank order for logic
        self.rank_order = ['Trainer', 'Elite Trainer', 'Gym Leader', 'Ace Trainer', 'Pal Master', 'Champion']
        
        # Streak bonus items
        self.streak_bonuses = {
            3: {'PALDOGS': 50, 'exp': 100},
            7: {'PALDOGS': 150, 'PalSphere': 10, 'exp': 250},
            14: {'PALDOGS': 500, 'PalSphere_Mega': 5, 'exp': 500},
            30: {'PALDOGS': 1500, 'PalSphere_Giga': 3, 'exp': 1000}
        }

        # --- ANNOUNCER PACKS ---
        self.announcers_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "announcers.json")
        self.load_announcers()

    def load_announcers(self):
        """Load announcer packs from JSON file"""
        try:
            if os.path.exists(self.announcers_file):
                with open(self.announcers_file, 'r', encoding='utf-8') as f:
                    self.announcer_packs = json.load(f)
            else:
                self.announcer_packs = {} # Fallback
        except Exception as e:
            print(f"❌ Error loading announcers: {e}")
            self.announcer_packs = {}

    def save_announcers(self):
        """Save announcer packs to JSON file"""
        try:
            with open(self.announcers_file, 'w', encoding='utf-8') as f:
                json.dump(self.announcer_packs, f, indent=4)
        except Exception as e:
            print(f"❌ Error saving announcers: {e}")

    def update_announcer_price(self, aid: str, new_price: int) -> bool:
        """Update the price of an announcer pack"""
        if aid in self.announcer_packs:
            self.announcer_packs[aid]['price'] = new_price
            self.save_announcers()
            return True
        return False

    def get_rank_from_palmarks(self, palmarks: int) -> str:
        """Determine rank based on total PALDOGS (returns the highest possible rank)"""
        highest_rank = 'Trainer'
        for rank_name, rank_data in self.ranks.items():
            if palmarks >= rank_data['min_palmarks']:
                # Since ranks are checked in dict order, we need to ensure we get the highest applicable min_palmarks
                if rank_data['min_palmarks'] >= self.ranks[highest_rank]['min_palmarks']:
                    highest_rank = rank_name
        return highest_rank
    
    async def check_and_update_rank(self, steam_id: str) -> Tuple[str, bool]:
        """Check if player should rank up and update if needed"""
        stats = await db.get_player_stats(steam_id)
        if not stats: return 'Trainer', False
        
        current_rank = stats.get('rank', 'Trainer')
        palmarks = stats.get('palmarks', 0)
        
        # Fix: Ensure we don't downgrade or announce rank up if already at max or same rank
        new_rank = self.get_rank_from_palmarks(palmarks)
        
        if new_rank != current_rank:
            # Check if it's actually a rank UP by order
            try:
                old_idx = self.rank_order.index(current_rank)
                new_idx = self.rank_order.index(new_rank)
                if new_idx > old_idx:
                    await db.update_player_rank(steam_id, new_rank)
                    return new_rank, True
                else:
                    # Don't downgrade rank automatically if palmarks dropped (e.g. spent in shop)
                    # Unless that's desired. Usually players keep their highest rank.
                    return current_rank, False
            except ValueError:
                await db.update_player_rank(steam_id, new_rank)
                return new_rank, True
        
        return current_rank, False
    
    def get_level_exp(self, level: int) -> int:
        """Calculate EXP required for a specific level"""
        return level * level * 100

    async def get_progress_to_next_rank(self, steam_id: str) -> Optional[Dict]:
        stats = await db.get_player_stats(steam_id)
        if not stats: return None
        
        current_level = stats.get('level', 1)
        current_exp = stats.get('experience', 0)
        
        required_exp = self.get_level_exp(current_level)
        prev_level_exp = self.get_level_exp(current_level - 1) if current_level > 1 else 0
        
        # Calculate percentage within the current level
        exp_in_level = current_exp - prev_level_exp
        needed_in_level = required_exp - prev_level_exp
        
        percentage = min(100, int((exp_in_level / needed_in_level) * 100)) if needed_in_level > 0 else 100
        
        return {
            'level': current_level,
            'experience': current_exp,
            'required_exp': required_exp,
            'percentage': percentage,
            'is_max_rank': False # Levels are infinite for now
        }
    
    def get_daily_rewards(self, rank: str, streak: int) -> Dict:
        rank_data = self.ranks.get(rank, self.ranks['Trainer'])
        rewards = {
            'items': rank_data['daily_reward_items'].copy(),
            'exp': rank_data['daily_reward_exp']
        }
        for streak_days, bonus in self.streak_bonuses.items():
            if streak >= streak_days:
                for item_id, amount in bonus.items():
                    if item_id == 'exp': rewards['exp'] += amount
                    else: rewards['items'][item_id] = rewards['items'].get(item_id, 0) + amount
        return rewards
    
    def get_rank_info(self, rank: str) -> Dict:
        return self.ranks.get(rank, self.ranks['Trainer'])
    
    def get_next_rank_info(self, current_rank: str) -> Optional[Dict]:
        try:
            current_index = self.rank_order.index(current_rank)
            if current_index < len(self.rank_order) - 1:
                next_rank = self.rank_order[current_index + 1]
                return {
                    'name': next_rank,
                    'required_palmarks': self.ranks[next_rank]['min_palmarks'],
                    'info': self.ranks[next_rank]
                }
        except ValueError: pass
        return None

        return {
            'current_rank': current_rank,
            'next_rank': next_rank_info['name'],
            'current_palmarks': palmarks,
            'required_palmarks': required,
            'percentage': percentage,
            'is_max_rank': False
        }
    
    def get_rank_from_exp(self, exp: int) -> str:
        """Determine rank based on total EXP if desired (currently still using palmarks in logic above)"""
        # For now, we are keeping the user's preference of 'Rank' being a separate tier, 
        # but we could link it here if they wanted.
        return self.get_rank_from_palmarks(exp // 10) # Example scaling 10 exp = 1 palmark equivalent


    # --- ANNOUNCER PACK LOGIC ---
    def get_join_message(self, announcer_id: str, player_name: str) -> str:
        pack = self.announcer_packs.get(announcer_id, self.announcer_packs['default'])
        return pack['join_template'].format(player=player_name)

    def get_rank_message(self, announcer_id: str, player_name: str, rank_name: str) -> str:
        pack = self.announcer_packs.get(announcer_id, self.announcer_packs['default'])
        return pack['rank_template'].format(player=player_name, rank=rank_name)


# Global instance
rank_system = RankSystem()
