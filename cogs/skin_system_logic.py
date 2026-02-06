import os
import json
import logging

class SkinSystem:
    def __init__(self):
        self.config_path = os.path.join("data", "skins_config.json")
        self.skins = {}
        self.load_skins()

    def get_skins_dir(self):
        """Get the skins directory from bot config or default."""
        from utils.config_manager import config
        return config.get('skins_source_dir', os.path.join("data", "palskins"))

    def load_skins(self):
        """Load skins from the configuration file."""
        if not os.path.exists(self.config_path):
            self.save_skins()
            return
            
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                self.skins = data.get('skins', {})
        except Exception as e:
            logging.error(f"Error loading skins: {e}")
            self.skins = {}

    def save_skins(self):
        """Save current skins to the configuration file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump({"skins": self.skins}, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving skins: {e}")

    def sync_with_folder(self):
        """Scan the skins directory and add any new .pak files automatically."""
        skins_dir = self.get_skins_dir()
        if not os.path.exists(skins_dir):
            return 0, []

        new_count = 0
        added_files = []
        found_files = [f for f in os.listdir(skins_dir) if f.endswith('.pak')]
        
        # Track which pak files we already have in config
        config_paks = {data['pak_filename']: sid for sid, data in self.skins.items()}

        changed = False
        for pak in found_files:
            base_name = pak.replace('.pak', '')
            
            # Auto-discovery of local image
            image_file = ""
            for ext in ['.png', '.jpg', '.jpeg']:
                if os.path.exists(os.path.join(skins_dir, base_name + ext)):
                    image_file = base_name + ext
                    break

            if pak not in config_paks:
                # NEW SKIN
                sid = base_name.lower().replace(' ', '_')
                # Ensure SID is unique
                original_sid = sid
                counter = 1
                while sid in self.skins:
                    sid = f"{original_sid}_{counter}"
                    counter += 1
                
                self.skins[sid] = {
                    "name": base_name.replace('_', ' ').title(),
                    "price": 0,
                    "pak_filename": pak,
                    "description": "Auto-discovered skin.",
                    "image_url": "",
                    "image_filename": image_file,
                    "download_url": ""
                }
                new_count += 1
                added_files.append(pak)
                changed = True
            else:
                # EXISTING SKIN - Update image if missing
                sid = config_paks[pak]
                if image_file and not self.skins[sid].get('image_filename'):
                    self.skins[sid]['image_filename'] = image_file
                    changed = True

        if changed:
            self.save_skins()
        
        return new_count, added_files

    def add_skin(self, skin_id, name, price, pak_filename, description="", image_url="", image_filename="", download_url=""):
        """Add or update a skin."""
        self.skins[skin_id] = {
            "name": name,
            "price": price,
            "pak_filename": pak_filename,
            "description": description,
            "image_url": image_url,
            "image_filename": image_filename,
            "download_url": download_url
        }
        self.save_skins()
        return True

    def delete_skin(self, skin_id):
        """Remove a skin from the system."""
        if skin_id in self.skins:
            del self.skins[skin_id]
            self.save_skins()
            return True
        return False

    def get_skin(self, skin_id):
        return self.skins.get(skin_id)

    def get_all_skins(self):
        return self.skins

    def get_all_skin_ids(self):
        return list(self.skins.keys())

# Global instance
skin_system = SkinSystem()
