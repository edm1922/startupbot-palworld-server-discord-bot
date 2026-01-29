import json
import os
from typing import Dict, Optional, List

class PalSystem:
    """Manages custom Pal definitions/presets for administration"""
    
    def __init__(self, filename="custom_pals.json"):
        # Go up from cogs/ to root, then into data/
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.filename = os.path.join(root_dir, "data", filename)
        self.custom_pals = {}
        self.load_pals()
    
    def load_pals(self):
        """Load custom pals from JSON file"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.custom_pals = json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ Error decoding {self.filename}. Starting with empty custom pals.")
                self.custom_pals = {}
        else:
            # Create empty file
            self.custom_pals = {}
            self.save_pals()
    
    def save_pals(self):
        """Save custom pals to JSON file"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.custom_pals, f, indent=4)
        except Exception as e:
            print(f"❌ Error saving custom pals: {e}")
    
    def add_pal(self, name: str, pal_json: str, description: str = None, export_dir: str = None) -> str:
        """Add or update a custom pal definition"""
        name = name.lower()
        if name not in self.custom_pals:
            msg = f"Created new custom Pal **{name}**"
        else:
            msg = f"Updated custom Pal **{name}**"
            
        self.custom_pals[name] = {
            "json": pal_json,
            "description": description or "Custom Defined Pal"
        }
            
        self.save_pals()

        # If an export directory is provided, save the standalone JSON file there
        if export_dir and os.path.exists(export_dir):
            try:
                file_path = os.path.join(export_dir, f"{name}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Parse and re-dump to ensure clean formatting if it was minified
                    parsed = json.loads(pal_json)
                    json.dump(parsed, f, indent=4)
                msg += f" and saved to `{name}.json` in template folder"
            except Exception as e:
                msg += f" (⚠️ Failed to save file: {e})"
                
        return msg

    def delete_pal_file(self, name: str, export_dir: str = None):
        """Delete the standalone JSON file if it exists"""
        if export_dir and os.path.exists(export_dir):
            file_path = os.path.join(export_dir, f"{name.lower()}.json")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    return True
                except:
                    pass
        return False

    def edit_pal(self, name: str, pal_json: str = None, description: str = None, export_dir: str = None) -> bool:
        """Update pal metadata or JSON"""
        name = name.lower()
        if name not in self.custom_pals:
            return False
            
        if pal_json is not None:
            self.custom_pals[name]["json"] = pal_json
        if description is not None:
            self.custom_pals[name]["description"] = description
            
        self.save_pals()
        return True
    
    def delete_pal(self, name: str) -> bool:
        """Delete a custom pal definition"""
        name = name.lower()
        if name in self.custom_pals:
            del self.custom_pals[name]
            self.save_pals()
            return True
        return False
        
    def get_pal(self, name: str) -> Optional[Dict]:
        """Get definition of a custom pal"""
        return self.custom_pals.get(name.lower())
    
    def get_all_pal_names(self) -> List[str]:
        """Get list of all custom pal names"""
        return list(self.custom_pals.keys())

# Global instance
pal_system = PalSystem()
