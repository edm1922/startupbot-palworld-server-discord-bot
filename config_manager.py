import json
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables is now handled inside ConfigManager using absolute paths

class ConfigManager:
    """
    Manages bot configuration, transitioning from .env to a JSON-based system
    while keeping sensitive data secure.
    """
    
    
    def __init__(self, config_file: str = "bot_config.json"):
        # Use absolute path based on the script location to ensure consistency
        # even if launched from a different working directory (like Windows Startup)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.base_dir, config_file)
        self.env_file = os.path.join(self.base_dir, ".env")
        
        # Load environment variables using absolute path
        load_dotenv(self.env_file)
        
        self.config_data = {}
        self.load_config()
    
    def load_config(self):
        """Load configuration from JSON file, with fallback to .env"""
        # Load existing JSON config if it exists
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.config_data = {}
        
        # Migrate from .env ONLY if JSON config is truly empty or missing
        if not self.config_data:
            print(f"No configuration found at {self.config_file}. Attempting migration...")
            self.migrate_from_env()
    
    def migrate_from_env(self):
        """Migrate configuration from .env file to JSON config"""
        env_mapping = {
            'GUILD_ID': ('guild_id', int),
            'ALLOWED_CHANNEL_ID': ('allowed_channel_id', int),
            'STATUS_CHANNEL_ID': ('status_channel_id', int),
            'RAM_USAGE_CHANNEL_ID': ('ram_usage_channel_id', int),
            'PLAYER_MONITOR_CHANNEL_ID': ('player_monitor_channel_id', int),
            'RESTART_INTERVAL': ('restart_interval', int),
            'SERVER_DIRECTORY': ('server_directory', str),
            'STARTUP_SCRIPT': ('startup_script', str),
            'SHUTDOWN_TIME': ('shutdown_time', str),
            'STARTUP_TIME': ('startup_time', str),
            'ADMIN_USER_ID': ('admin_user_id', int),  # New field for admin ID
            'REST_API_ENDPOINT': ('rest_api_endpoint', str),  # For future REST API
            'REST_API_KEY': ('rest_api_key', str),  # For future REST API
        }
        
        migrated_data = {}
        
        for env_key, (config_key, converter) in env_mapping.items():
            env_value = os.getenv(env_key)
            if env_value:
                try:
                    if converter == int:
                        migrated_data[config_key] = int(env_value)
                    elif converter == str:
                        migrated_data[config_key] = env_value.strip()
                except ValueError:
                    print(f"Warning: Could not convert {env_key}={env_value} to {converter.__name__}")
        
        # Set defaults for missing values
        defaults = {
            'restart_interval': 10800,  # 3 hours in seconds
            'shutdown_time': "05:00",
            'startup_time': "10:00",
            'admin_user_id': 0,  # No default admin ID, relies on server admin perms
            'auto_restart_enabled': True,
        }
        
        for key, default_value in defaults.items():
            if key not in migrated_data:
                migrated_data[key] = default_value
        
        self.config_data = migrated_data
        self.save_config()
        print("Configuration migrated from .env to JSON file.")
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config_data.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """Set a configuration value and save to file"""
        self.config_data[key] = value
        return self.save_config()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        return self.config_data.copy()
    
    def get_discord_token(self) -> Optional[str]:
        """Get the Discord bot token from .env (never stored in JSON)"""
        return os.getenv("DISCORD_BOT_TOKEN")


# Global config instance
config = ConfigManager()