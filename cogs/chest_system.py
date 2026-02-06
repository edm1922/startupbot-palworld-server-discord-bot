import json
import os
from typing import Dict, List, Optional
import random

class ChestSystem:
    """Manages the chest reward system, rarity rates, and reward pools"""
    
    def __init__(self, filename="chest_config.json"):
        # Go up from cogs/ to root, then into data/
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filename = os.path.join(root_dir, "data", filename)
        
        # Default configuration
        self.config = {
            "reroll_cost": 100,
            "tier_costs": {
                "basic": 500,
                "rare": 1500,
                "epic": 5000,
                "legendary": 20000
            },
            "cost_increment": 250, # Progressive increment per level
            "rates": {
                "legendary": 1.5,
                "epic": 8.5,
                "rare": 25.0,
                "basic": 65.0
            },
            "rewards": {
                "legendary": [],
                "epic": [],
                "rare": [],
                "basic": []
            },
            "burst_settings": {
                "max_rolls": 10,
                "cooldown_seconds": 30
            },
            "global_burst": {
                "max_rolls": 20,
                "cooldown_seconds": 60
            },
            "daily_limit": 50
        }
        self.load_config()

    def load_config(self):
        """Load chest configuration from JSON file"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Use the loaded dict as base, then merge into default if needed
                    # but actually we want the loaded one to be primary.
                    for key in loaded:
                        if key in self.config and isinstance(self.config[key], dict) and isinstance(loaded[key], dict):
                            self.config[key].update(loaded[key])
                        else:
                            self.config[key] = loaded[key]
                print(f"✅ Loaded chest config from {self.filename}")
                # Log counts for debugging
                for tier, rewards in self.config.get("rewards", {}).items():
                    print(f"  - {tier.title()}: {len(rewards)} rewards")
            except json.JSONDecodeError as e:
                print(f"⚠️ Error decoding {self.filename}: {e}. Using defaults.")
            except Exception as e:
                print(f"❌ Unexpected error loading {self.filename}: {e}")
        else:
            self.save_config()

    def save_config(self):
        """Save chest configuration to JSON file"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"❌ Error saving chest config: {e}")

    def add_reward(self, tier: str, reward_type: str, reward_id: str, amount: int = 1, weight: float = 1.0) -> bool:
        """Add a reward to a specific tier"""
        tier = tier.lower()
        if tier not in self.config["rewards"]:
            return False
        
        reward = {
            "type": reward_type.lower(), # 'item', 'kit', 'pal', 'currency', 'exp'
            "id": reward_id,
            "amount": amount,
            "weight": weight,
            "name": f"{amount}x {reward_id}" if reward_type.lower() == 'item' else reward_id
        }
        
        # Check if already exists and update, or append
        found = False
        for i, r in enumerate(self.config["rewards"][tier]):
            if r["id"] == reward_id and r["type"] == reward_type.lower():
                self.config["rewards"][tier][i] = reward
                found = True
                break
        
        if not found:
            self.config["rewards"][tier].append(reward)
            
        self.save_config()
        return True

    def remove_reward(self, tier: str, reward_id: str, reward_type: str) -> bool:
        """Remove a reward from a specific tier"""
        tier = tier.lower()
        if tier not in self.config["rewards"]:
            return False
            
        initial_len = len(self.config["rewards"][tier])
        self.config["rewards"][tier] = [r for r in self.config["rewards"][tier] 
                                       if not (r["id"] == reward_id and r["type"] == reward_type.lower())]
        
        if len(self.config["rewards"][tier]) < initial_len:
            self.save_config()
            return True
        return False

    def update_settings(self, cost: int = None, rates: Dict[str, float] = None):
        """Update roll cost or drop rates"""
        if cost is not None:
            self.config["roll_cost"] = cost
        if rates:
            for tier, rate in rates.items():
                if tier in self.config["rates"]:
                    self.config["rates"][tier] = rate
        self.save_config()

    def roll_rarity(self) -> str:
        """Roll to determine the chest rarity tier"""
        roll = random.uniform(0, 100)
        cumulative = 0
        
        # Sort by rate ascending to check small probabilities first
        sorted_rates = sorted(self.config["rates"].items(), key=lambda x: x[1])
        
        # Wait, sorted by rate ascending: legendary=1.5, epic=8.5, etc.
        # If roll=1.0, it's <=1.5 so legendary.
        # If roll=5.0, it's >1.5 but <=1.5+8.5 (10.0) so epic.
        
        for tier, rate in sorted_rates:
            cumulative += rate
            if roll <= cumulative:
                return tier
        
        return "basic" # Fallback

    def roll_reward(self, tier: str) -> Optional[Dict]:
        """Roll for a specific reward within a tier using weights"""
        rewards = self.config["rewards"].get(tier, [])
        if not rewards:
            return None
            
        total_weight = sum(r.get("weight", 1.0) for r in rewards)
        if total_weight <= 0:
            return random.choice(rewards)
            
        roll = random.uniform(0, total_weight)
        cumulative = 0
        for reward in rewards:
            cumulative += reward.get("weight", 1.0)
            if roll <= cumulative:
                return reward
        
        return rewards[-1]

    def get_all_rewards(self) -> Dict[str, List[Dict]]:
        """Get all configured rewards"""
        return self.config["rewards"]

# Global instance
chest_system = ChestSystem()
