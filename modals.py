import nextcord
from nextcord.ui import Modal, TextInput
from nextcord import Interaction
from config_manager import config


class ChannelConfigModal(Modal):
    def __init__(self):
        super().__init__(title="Configure Channels")
        
        self.guild_id_input = TextInput(
            label="Guild ID",
            placeholder="Enter the guild/server ID...",
            required=True,
            default_value=str(config.get('guild_id', ''))
        )
        self.add_item(self.guild_id_input)
        
        self.allowed_channel_input = TextInput(
            label="Allowed Channel ID",
            placeholder="Enter the allowed channel ID...",
            required=True,
            default_value=str(config.get('allowed_channel_id', ''))
        )
        self.add_item(self.allowed_channel_input)
        
        self.status_channel_input = TextInput(
            label="Status Channel ID",
            placeholder="Enter the status channel ID...",
            required=True,
            default_value=str(config.get('status_channel_id', ''))
        )
        self.add_item(self.status_channel_input)
        
        self.ram_usage_channel_input = TextInput(
            label="RAM Usage Channel ID",
            placeholder="Enter the RAM usage channel ID...",
            required=True,
            default_value=str(config.get('ram_usage_channel_id', ''))
        )
        self.add_item(self.ram_usage_channel_input)

    async def callback(self, interaction: Interaction):
        try:
            # Validate that inputs are numeric
            guild_id = int(self.guild_id_input.value)
            allowed_channel_id = int(self.allowed_channel_input.value)
            status_channel_id = int(self.status_channel_input.value)
            ram_usage_channel_id = int(self.ram_usage_channel_input.value)
            
            # Save to config
            config.set('guild_id', guild_id)
            config.set('allowed_channel_id', allowed_channel_id)
            config.set('status_channel_id', status_channel_id)
            config.set('ram_usage_channel_id', ram_usage_channel_id)
            
            await interaction.response.send_message("Channel configuration updated successfully!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Error: Please enter valid numeric IDs", ephemeral=True)


class ChatConfigModal(Modal):
    def __init__(self):
        super().__init__(title="Configure Chat Relay")
        
        self.chat_channel_input = TextInput(
            label="Cross-Chat Channel ID",
            placeholder="Enter the channel ID for in-game chat...",
            required=True,
            default_value=str(config.get('chat_channel_id', ''))
        )
        self.add_item(self.chat_channel_input)
        
        self.chat_webhook_url_input = TextInput(
            label="Chat Webhook URL (Optional)",
            placeholder="Paste Discord Webhook URL here...",
            required=False,
            default_value=config.get('chat_webhook_url', '')
        )
        self.add_item(self.chat_webhook_url_input)

    async def callback(self, interaction: Interaction):
        try:
            chat_channel_id = int(self.chat_channel_input.value)
            chat_webhook_url = self.chat_webhook_url_input.value.strip()
            
            config.set('chat_channel_id', chat_channel_id)
            config.set('chat_webhook_url', chat_webhook_url)
            
            await interaction.response.send_message("Chat configuration updated successfully!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Error: Please enter a valid numeric Channel ID", ephemeral=True)


class ServerConfigModal(Modal):
    def __init__(self):
        super().__init__(title="Configure Server Settings")
        
        self.server_directory_input = TextInput(
            label="Server Directory Path",
            placeholder="Enter the server directory path...",
            required=True,
            default_value=config.get('server_directory', '')
        )
        self.add_item(self.server_directory_input)
        
        self.startup_script_input = TextInput(
            label="Startup Script Name",
            placeholder="Enter the startup script name...",
            required=True,
            default_value=config.get('startup_script', '')
        )
        self.add_item(self.startup_script_input)
        
        self.admin_user_id_input = TextInput(
            label="Admin User ID",
            placeholder="Enter the admin user ID...",
            required=True,
            default_value=str(config.get('admin_user_id', ''))
        )
        self.add_item(self.admin_user_id_input)
        
        self.log_directory_input = TextInput(
            label="PalGuard Logs Directory",
            placeholder="E.g. D:\HaruHostGSM\Pal\Binaries\Win64\PalDefender\Logs",
            required=False,
            default_value=config.get('log_directory', '')
        )
        self.add_item(self.log_directory_input)

    async def callback(self, interaction: Interaction):
        try:
            # Validate admin user ID is numeric
            admin_user_id = int(self.admin_user_id_input.value)
            
            # Save to config
            config.set('server_directory', self.server_directory_input.value)
            config.set('startup_script', self.startup_script_input.value)
            config.set('admin_user_id', admin_user_id)
            config.set('log_directory', self.log_directory_input.value)
            
            await interaction.response.send_message("Server configuration updated successfully!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Error: Please enter a valid numeric Admin User ID", ephemeral=True)


class ScheduleConfigModal(Modal):
    def __init__(self):
        super().__init__(title="Configure Schedule Settings")
        
        self.restart_interval_input = TextInput(
            label="Restart Interval (seconds)",
            placeholder="Enter restart interval in seconds (default: 10800)...",
            required=True,
            default_value=str(config.get('restart_interval', 10800))
        )
        self.add_item(self.restart_interval_input)
        
        self.shutdown_time_input = TextInput(
            label="Shutdown Time (HH:MM)",
            placeholder="Enter shutdown time in HH:MM format (default: 05:00)...",
            required=True,
            default_value=config.get('shutdown_time', '05:00')
        )
        self.add_item(self.shutdown_time_input)
        
        self.startup_time_input = TextInput(
            label="Startup Time (HH:MM)",
            placeholder="Enter startup time in HH:MM format (default: 10:00)...",
            required=True,
            default_value=config.get('startup_time', '10:00')
        )
        self.add_item(self.startup_time_input)

    async def callback(self, interaction: Interaction):
        try:
            # Validate numeric values
            restart_interval = int(self.restart_interval_input.value)
            
            # Validate time format (HH:MM)
            shutdown_time = self.shutdown_time_input.value
            startup_time = self.startup_time_input.value
            
            # Simple validation for time format
            if len(shutdown_time.split(':')) != 2 or len(startup_time.split(':')) != 2:
                await interaction.response.send_message("Error: Please enter times in HH:MM format", ephemeral=True)
                return
                
            hour_s, minute_s = shutdown_time.split(':')
            hour_u, minute_u = startup_time.split(':')
            
            if not (hour_s.isdigit() and minute_s.isdigit() and hour_u.isdigit() and minute_u.isdigit()):
                await interaction.response.send_message("Error: Please enter times in HH:MM format", ephemeral=True)
                return
                
            if int(hour_s) > 23 or int(minute_s) > 59 or int(hour_u) > 23 or int(minute_u) > 59:
                await interaction.response.send_message("Error: Invalid time format", ephemeral=True)
                return
            
            # Save to config
            config.set('restart_interval', restart_interval)
            config.set('shutdown_time', shutdown_time)
            config.set('startup_time', startup_time)
            
            await interaction.response.send_message("Schedule configuration updated successfully!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Error: Please enter valid numeric values", ephemeral=True)


class RestApiConfigModal(Modal):
    def __init__(self):
        super().__init__(title="Configure REST API Settings")
        
        self.rest_api_endpoint_input = TextInput(
            label="REST API Endpoint",
            placeholder="Enter the REST API endpoint URL...",
            required=False,
            default_value=config.get('rest_api_endpoint', '')
        )
        self.add_item(self.rest_api_endpoint_input)
        
        self.rest_api_key_input = TextInput(
            label="Server Admin Password",
            placeholder="Enter the server admin password...",
            required=False,
            default_value=config.get('rest_api_key', ''),
            style=nextcord.TextInputStyle.short
        )
        self.add_item(self.rest_api_key_input)

    async def callback(self, interaction: Interaction):
        try:
            # Save to config
            config.set('rest_api_endpoint', self.rest_api_endpoint_input.value)
            config.set('rest_api_key', self.rest_api_key_input.value)
            
            await interaction.response.send_message("REST API configuration updated successfully!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error updating REST API config: {str(e)}", ephemeral=True)