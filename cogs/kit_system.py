import json
import os
from typing import Dict, Optional, List

class KitSystem:
    """Manages item kits/presets for administration"""
    
    def __init__(self, filename="kits.json"):
        # Go up from cogs/ to root, then into data/
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filename = os.path.join(root_dir, "data", filename)
        self.kits = {}
        self.load_kits()
    
    def load_kits(self):
        """Load kits from JSON file"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.kits = json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ Error decoding {self.filename}. Starting with empty kits.")
                self.kits = {}
        else:
            # Create default starter kit
            self.kits = {
                "starter": {
                    "items": {
                        "Gold": 500,
                        "PalSphere": 10,
                        "Bread": 5
                    },
                    "description": "Basic starter pack for new players",
                    "price": 0
                }
            }
            self.save_kits()
        
        # Ensure 'price' exists for all kits
        updated = False
        for name in self.kits:
            if "price" not in self.kits[name]:
                self.kits[name]["price"] = 0
                updated = True
        if updated:
            self.save_kits()
    
    def save_kits(self):
        """Save kits to JSON file"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.kits, f, indent=4)
        except Exception as e:
            print(f"❌ Error saving kits: {e}")
    
    def create_or_update_kit(self, name: str, item_id: str, amount: int, description: str = None, price: int = None) -> str:
        """Add an item to a kit"""
        name = name.lower()
        if name not in self.kits:
            self.kits[name] = {
                "items": {}, 
                "description": description or "Custom Admin Kit",
                "price": price if price is not None else 0
            }
            msg = f"Created new kit **{name}**"
        else:
            msg = f"Updated kit **{name}**"
            
        self.kits[name]["items"][item_id] = amount
        if description:
            self.kits[name]["description"] = description
        if price is not None:
            self.kits[name]["price"] = price
            
        self.save_kits()
        return msg

    def edit_kit(self, name: str, description: str = None, price: int = None) -> bool:
        """Update kit metadata without affecting items"""
        name = name.lower()
        if name not in self.kits:
            return False
            
        if description is not None:
            self.kits[name]["description"] = description
        if price is not None:
            self.kits[name]["price"] = price
            
        self.save_kits()
        return True
        
    def remove_item_from_kit(self, name: str, item_id: str) -> bool:
        """Remove an item from a kit"""
        name = name.lower()
        if name in self.kits and item_id in self.kits[name]["items"]:
            del self.kits[name]["items"][item_id]
            # Clean up empty kits if desired, or keep them to add more items later
            # if not self.kits[name]["items"]:
            #     del self.kits[name]
            self.save_kits()
            return True
        return False
    
    def delete_kit(self, name: str) -> bool:
        """Delete an entire kit"""
        name = name.lower()
        if name in self.kits:
            del self.kits[name]
            self.save_kits()
            return True
        return False
        
    def get_kit(self, name: str) -> Optional[Dict]:
        """Get contents of a kit"""
        return self.kits.get(name.lower())
    
    def get_all_kit_names(self) -> List[str]:
        """Get list of all kit names"""
        return list(self.kits.keys())

# Global instance
kit_system = KitSystem()
