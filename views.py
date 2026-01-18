import nextcord
from nextcord.ui import View, Button
from nextcord import Interaction
import subprocess
import os
import psutil
from config_manager import config


import asyncio

class ServerControlView(View):
    """View with buttons to control the Palworld server"""
    
    def __init__(self):
        super().__init__(timeout=None)  # No timeout to keep persistent
        self._processing_lock = False

    def is_server_running(self):
        """Check if the specific server instance is running based on directory and script"""
        server_directory = config.get('server_directory')
        startup_script = config.get('startup_script')
        
        # Normalize path for comparison
        if server_directory:
            server_directory = os.path.normpath(server_directory.lower())

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
            try:
                # Check CWD (Current Working Directory)
                try:
                    proc_cwd = os.path.normpath(proc.cwd().lower()) if proc.cwd() else ""
                    if server_directory and server_directory in proc_cwd:
                         # Use loose checking as requested to find "configured instances"
                         # We check if it is a relevant process type (java, pal, cmd, etc)
                         # OR if checking CWD is enough for the user (seems to be what they want)
                         return True
                except (psutil.AccessDenied, FileNotFoundError):
                    pass
                
                # Check cmdline for startup script
                if proc.info['cmdline'] and startup_script:
                    cmdline = " ".join(proc.info['cmdline']).lower()
                    if startup_script.lower() in cmdline:
                        return True

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    async def check_permissions(self, interaction: Interaction) -> bool:
        """Check if user has permission to use these controls"""
        admin_user_id = config.get('admin_user_id', 0)  # No default hardcoded ID
        
        # Check if user is admin or has administrator permissions
        if interaction.user.id == admin_user_id or interaction.user.guild_permissions.administrator:
            return True
        else:
            await interaction.response.send_message("You don't have permission to use these controls.", ephemeral=True)
            return False

    async def interaction_check(self, interaction: Interaction) -> bool:
        # Check permissions for any button interaction
        return await self.check_permissions(interaction)

    async def on_timeout(self):
        # Called when the view times out (won't happen due to timeout=None)
        pass

    async def on_error(self, error: Exception, item: nextcord.ui.Item, interaction: Interaction) -> None:
        # Handle any errors that occur
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)
            else:
                await interaction.followup.send(f"An error occurred: {error}", ephemeral=True)
        except:
            pass


    def is_server_running(self):
        """Check if PalServer is currently running"""
        # Reverting to simpler check as 'smart' checks were finding stuck/ghost CMD processes
        # and preventing the server from starting.
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'PalServer' in proc.info['name']:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    @nextcord.ui.button(label='Start Server', style=nextcord.ButtonStyle.green, emoji='🟢', custom_id='start_server_btn')
    async def start_server_button(self, button: nextcord.ui.Button, interaction: Interaction):
        print("🖱️ 'Start Server' button clicked!")
        
        if self._processing_lock:
            print("🔒 Button locked (processing previous click)")
            await interaction.response.send_message("⚠️ Already processing a request. Please wait...", ephemeral=True)
            return

        self._processing_lock = True
        try:
            # Acknowledge immediately to prevent timeout/retries
            await interaction.response.defer(ephemeral=True)
            
            # Double check running state
            if self.is_server_running():
                print("⚠️ Server found running during check.")
                await interaction.followup.send("✅ Server is already running!")
                return
                
            server_directory = config.get('server_directory')
            startup_script = config.get('startup_script')
            
            if not server_directory or not startup_script:
                await interaction.followup.send("Server directory or startup script not configured!", ephemeral=True)
                return
            
            print(f"🚀 Launching server: {startup_script} in {server_directory}")
            if os.name == 'nt':
                # Reverting to original method as requested by user
                subprocess.Popen(["cmd.exe", "/c", startup_script], cwd=server_directory, shell=True)
            else:
                await interaction.followup.send("Linux startup not implemented yet.", ephemeral=True)
                return
                
            await interaction.followup.send("✅ Server startup initiated!")
            
            # Send status update
            status_channel_id = config.get('status_channel_id')
            if status_channel_id:
                try:
                    channel = interaction.guild.get_channel(status_channel_id) or interaction.client.get_channel(status_channel_id)
                    if channel:
                        embed = nextcord.Embed(title="paltastic", description="🟢 **ONLINE**\nPalworld", color=0x00FF00)
                        embed.set_footer(text="powered by Paltastic")
                        await channel.send(embed=embed)
                except Exception as e:
                    print(f"Failed to send status update: {e}")
            
            # Keep lock for a few seconds to prevent accidental double-clicks
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"❌ Error in start_server_button: {e}")
            await interaction.followup.send(f"❌ Failed to start the server: {e}", ephemeral=True)
        finally:
            self._processing_lock = False
            print("🔓 Button lock released")

    @nextcord.ui.button(label='Restart Server', style=nextcord.ButtonStyle.blurple, emoji='🔄', custom_id='restart_server_btn')
    async def restart_server_button(self, button: nextcord.ui.Button, interaction: Interaction):
        try:
            # Stop the server first
            if os.name == 'nt':
                subprocess.run(["taskkill", "/F", "/IM", "PalServer.exe", "/T"], shell=True)
            else:
                await interaction.response.send_message("Linux shutdown not implemented yet.", ephemeral=True)
                return
                
            await interaction.response.send_message("Server stopping...", ephemeral=True)
            
            # Send offline status
            status_channel_id = config.get('status_channel_id')
            if status_channel_id:
                try:
                    channel = interaction.guild.get_channel(status_channel_id) or interaction.client.get_channel(status_channel_id)
                    if channel:
                        embed = nextcord.Embed(title="paltastic", description="🔴 **OFFLINE**\nPalworld", color=0xFF0000)
                        embed.set_footer(text="powered by Paltastic")
                        await channel.send(embed=embed)
                except:
                    pass

            # Wait a bit before starting again
            await asyncio.sleep(5)
            
            # Then start the server
            server_directory = config.get('server_directory')
            startup_script = config.get('startup_script')
            
            if not server_directory or not startup_script:
                await interaction.followup.send("Server directory or startup script not configured!", ephemeral=True)
                return
            
            if os.name == 'nt':
                 subprocess.Popen(["cmd.exe", "/c", startup_script], cwd=server_directory, shell=True)
            
            await interaction.followup.send("✅ Server restart initiated!", ephemeral=True)

            # Send online status
            if status_channel_id:
                try:
                    channel = interaction.guild.get_channel(status_channel_id) or interaction.client.get_channel(status_channel_id)
                    if channel:
                        embed = nextcord.Embed(title="paltastic", description="🟢 **ONLINE**\nPalworld", color=0x00FF00)
                        embed.set_footer(text="powered by Paltastic")
                        await channel.send(embed=embed)
                except:
                    pass

        except Exception as e:
             # If interaction is already responded to, use followup
             if interaction.response.is_done():
                 await interaction.followup.send(f"❌ Failed to restart the server: {e}", ephemeral=True)
             else:
                 await interaction.response.send_message(f"❌ Failed to restart the server: {e}", ephemeral=True)

    @nextcord.ui.button(label='Shutdown Server', style=nextcord.ButtonStyle.red, emoji='🔴', custom_id='stop_server_btn')
    async def stop_server_button(self, button: nextcord.ui.Button, interaction: Interaction):
        try:
            if os.name == 'nt':
                subprocess.run(["taskkill", "/F", "/IM", "PalServer.exe", "/T"], shell=True)
            else:
                await interaction.response.send_message("Linux shutdown not implemented yet.", ephemeral=True)
                return
                
            await interaction.response.send_message("✅ Server shutdown initiated!", ephemeral=True)
            
            # Send status update
            status_channel_id = config.get('status_channel_id')
            if status_channel_id:
                try:
                    channel = interaction.guild.get_channel(status_channel_id) or interaction.client.get_channel(status_channel_id)
                    if channel:
                        embed = nextcord.Embed(title="paltastic", description="🔴 **OFFLINE**\nPalworld", color=0xFF0000)
                        embed.set_footer(text="powered by Paltastic")
                        await channel.send(embed=embed)
                except Exception as e:
                    print(f"Failed to send status update: {e}")

        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to stop the server: {e}", ephemeral=True)


class InteractiveConfigView(View):
    """A premium, embedded configuration system using dropdowns and buttons"""
    
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.category = "home"
        self.setup_items()

    def setup_items(self):
        self.clear_items()
        
        # 1. Main Category Select
        options = [
            nextcord.SelectOption(label="Home", emoji="🏠", value="home", description="Configuration overview"),
            nextcord.SelectOption(label="Channels", emoji="📺", value="channels", description="Configure Discord channels"),
            nextcord.SelectOption(label="Server", emoji="🖥️", value="server", description="Directories and startup scripts"),
            nextcord.SelectOption(label="Schedule", emoji="⏰", value="schedule", description="Auto-restarts and daily timers"),
            nextcord.SelectOption(label="REST API", emoji="🌐", value="api", description="Game server API settings"),
            nextcord.SelectOption(label="Chat Relay", emoji="💬", value="chat", description="Discord <-> Game chat settings"),
        ]
        
        select = nextcord.ui.Select(
            placeholder="Choose a configuration category...",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.category_callback
        self.add_item(select)

        # 2. Category-specific items
        if self.category == "channels":
            # Add buttons for specific channel types
            self.add_item(ConfigButton(label="Set Admin Channel", custom_id="set_admin_ch", style=nextcord.ButtonStyle.primary))
            self.add_item(ConfigButton(label="Set Status Channel", custom_id="set_status_ch", style=nextcord.ButtonStyle.primary))
            self.add_item(ConfigButton(label="Set RAM Channel", custom_id="set_ram_ch", style=nextcord.ButtonStyle.primary))
            self.add_item(ConfigButton(label="Set Chat Channel", custom_id="set_chat_ch", style=nextcord.ButtonStyle.primary))
            self.add_item(ConfigButton(label="Set Monitor Channel", custom_id="set_monitor_ch", style=nextcord.ButtonStyle.primary))
        
        elif self.category == "server":
            self.add_item(ConfigButton(label="Edit Server Directory", custom_id="edit_server_dir"))
            self.add_item(ConfigButton(label="Edit Startup Script", custom_id="edit_startup_script"))
            self.add_item(ConfigButton(label="Set Admin User", custom_id="set_admin_user", style=nextcord.ButtonStyle.secondary))
            self.add_item(ConfigButton(label="Edit Log Directory", custom_id="edit_log_dir"))

        elif self.category == "schedule":
            self.add_item(ConfigButton(label="Edit Restart Interval", custom_id="edit_restart_int"))
            self.add_item(ConfigButton(label="Edit Announcement Times", custom_id="edit_restart_announcements"))
            self.add_item(ConfigButton(label="Edit Shutdown Time", custom_id="edit_shutdown_time"))
            self.add_item(ConfigButton(label="Edit Startup Time", custom_id="edit_startup_time"))

        elif self.category == "api":
            self.add_item(ConfigButton(label="Edit API Endpoint", custom_id="edit_api_endpoint"))
            self.add_item(ConfigButton(label="Edit API Key", custom_id="edit_api_key"))

        elif self.category == "chat":
            self.add_item(ConfigButton(label="Edit Webhook URL", custom_id="edit_webhook"))

    async def category_callback(self, interaction: Interaction):
        self.category = interaction.data['values'][0]
        self.setup_items()
        await self.update_message(interaction)

    async def update_message(self, interaction: Interaction):
        embed = self.get_embed()
        if interaction.response.is_done():
            await interaction.edit_original_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    def get_embed(self):
        config_data = config.get_all()
        
        if self.category == "home":
            embed = nextcord.Embed(
                title="⚙️ Configuration Hub",
                description="Welcome to the interactive configuration menu. Select a category below to get started.",
                color=0x00ADD8
            )
            embed.add_field(name="Current Status", value="All systems functional. Changes are saved instantly to `bot_config.json`.", inline=False)
            return embed

        elif self.category == "channels":
            embed = nextcord.Embed(title="📺 Channel Configuration", color=0x5865F2)
            embed.add_field(name="Admin Channel", value=f"<#{config_data.get('allowed_channel_id', 0)}>", inline=True)
            embed.add_field(name="Status Channel", value=f"<#{config_data.get('status_channel_id', 0)}>", inline=True)
            embed.add_field(name="RAM Channel", value=f"<#{config_data.get('ram_usage_channel_id', 0)}>", inline=True)
            embed.add_field(name="Chat Channel", value=f"<#{config_data.get('chat_channel_id', 0)}>", inline=True)
            embed.add_field(name="Monitor Channel", value=f"<#{config_data.get('player_monitor_channel_id', 0)}>", inline=True)
            embed.set_footer(text="Click a button to change a channel using a dropdown selector.")
            return embed

        elif self.category == "server":
            embed = nextcord.Embed(title="🖥️ Server Configuration", color=0x7289DA)
            embed.add_field(name="Directory", value=f"`{config_data.get('server_directory', 'Not Set')}`", inline=False)
            embed.add_field(name="Startup Script", value=f"`{config_data.get('startup_script', 'Not Set')}`", inline=True)
            embed.add_field(name="Admin User", value=f"<@{config_data.get('admin_user_id', 0)}>", inline=True)
            embed.add_field(name="Logs Dir", value=f"`{config_data.get('log_directory', 'Not Set')}`", inline=False)
            return embed

        elif self.category == "schedule":
            interval = config_data.get('restart_interval', 10800)
            announcements = config_data.get('restart_announcements', '30,10,5,1')
            embed = nextcord.Embed(title="⏰ Schedule Configuration", color=0xFEE75C)
            embed.add_field(name="Restart Interval", value=f"`{interval}`s ({interval//3600}h)", inline=True)
            embed.add_field(name="Announcement Times", value=f"`{announcements}` mins", inline=True)
            embed.add_field(name="Shutdown Time", value=f"`{config_data.get('shutdown_time', '05:00')}`", inline=True)
            embed.add_field(name="Startup Time", value=f"`{config_data.get('startup_time', '10:00')}`", inline=True)
            embed.set_footer(text="Announcements: Comma-separated minutes (e.g. 30,10,5,1)")
            return embed

        elif self.category == "api":
            embed = nextcord.Embed(title="🌐 REST API Configuration", color=0xEB459E)
            embed.add_field(name="Endpoint", value=f"`{config_data.get('rest_api_endpoint', 'Not Set')}`", inline=False)
            embed.add_field(name="API Key", value="`********`" if config_data.get('rest_api_key') else "`Not Set`", inline=False)
            return embed

        elif self.category == "chat":
            embed = nextcord.Embed(title="💬 Chat Relay Configuration", color=0x57F287)
            embed.add_field(name="Webhook URL", value="`Configured`" if config_data.get('chat_webhook_url') else "`Not Set`", inline=False)
            return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This configuration menu belongs to another user.", ephemeral=True)
            return False
        return True


class ConfigButton(nextcord.ui.Button):
    def __init__(self, label, custom_id, style=nextcord.ButtonStyle.secondary):
        super().__init__(label=label, style=style, custom_id=custom_id)

    async def callback(self, interaction: Interaction):
        view: InteractiveConfigView = self.view
        
        # Handle different button types
        if self.custom_id.startswith("set_") and self.custom_id.endswith("_ch"):
            # Show a channel selector
            channel_type_map = {
                "set_admin_ch": "allowed_channel_id",
                "set_status_ch": "status_channel_id",
                "set_ram_ch": "ram_usage_channel_id",
                "set_chat_ch": "chat_channel_id",
                "set_monitor_ch": "player_monitor_channel_id"
            }
            config_key = channel_type_map.get(self.custom_id)
            
            # Temporary view with channel select
            temp_view = View(timeout=60)
            selector = nextcord.ui.ChannelSelect(placeholder="Select the channel...", channel_types=[nextcord.ChannelType.text])
            
            async def select_callback(inter: Interaction):
                selected_channel = selector.values[0]
                config.set(config_key, selected_channel.id)
                await inter.response.send_message(f"✅ Successfully updated channel to {selected_channel.mention}!", ephemeral=True)
                # Update parent view
                await view.update_message(interaction)
                
            selector.callback = select_callback
            temp_view.add_item(selector)
            await interaction.response.send_message("Select a channel from the list below:", view=temp_view, ephemeral=True)

        elif self.custom_id == "set_admin_user":
            temp_view = View(timeout=60)
            selector = nextcord.ui.UserSelect(placeholder="Select the administrator...")
            
            async def user_callback(inter: Interaction):
                selected_user = selector.values[0]
                config.set('admin_user_id', selected_user.id)
                await inter.response.send_message(f"✅ Successfully updated administrator to {selected_user.mention}!", ephemeral=True)
                await view.update_message(interaction)
                
            selector.callback = user_callback
            temp_view.add_item(selector)
            await interaction.response.send_message("Select a user to be the bot administrator:", view=temp_view, ephemeral=True)

        elif self.custom_id == "edit_restart_int":
            # Show a dropdown for common restart intervals
            temp_view = View(timeout=60)
            options = [
                nextcord.SelectOption(label="1 Hour", value="3600"),
                nextcord.SelectOption(label="3 Hours", value="10800", description="Recommended default"),
                nextcord.SelectOption(label="6 Hours", value="21600"),
                nextcord.SelectOption(label="12 Hours", value="43200"),
                nextcord.SelectOption(label="24 Hours", value="86400"),
                nextcord.SelectOption(label="Custom Manual Entry", emoji="⌨️", value="custom")
            ]
            
            selector = nextcord.ui.Select(placeholder="Pick a restart interval...", options=options)
            
            async def interval_callback(inter: Interaction):
                val = selector.values[0]
                if val == "custom":
                    await inter.response.send_modal(QuickModal("Custom Restart Interval", "Restart Interval (seconds)", "restart_interval", int, view))
                else:
                    config.set('restart_interval', int(val))
                    await inter.response.send_message(f"✅ Restart interval set to {int(val)//3600} hours!", ephemeral=True)
                    await view.update_message(interaction)
                
            selector.callback = interval_callback
            temp_view.add_item(selector)
            await interaction.response.send_message("Choose a pre-made interval or enter a custom one:", view=temp_view, ephemeral=True)

        elif self.custom_id == "edit_restart_announcements":
            # Show a dropdown for common announcement presets
            temp_view = View(timeout=60)
            options = [
                nextcord.SelectOption(label="Standard Countdown", description="30, 10, 5, 1 mins", value="30,10,5,1"),
                nextcord.SelectOption(label="Long Countdown", description="60, 30, 15, 10, 5, 1 mins", value="60,30,15,10,5,1"),
                nextcord.SelectOption(label="Short Warning", description="10, 5, 1 mins", value="10,5,1"),
                nextcord.SelectOption(label="Immediate Warning", description="2, 1, 0.5 mins", value="2,1,0.5"),
                nextcord.SelectOption(label="Custom Series", emoji="⌨️", value="custom")
            ]
            
            selector = nextcord.ui.Select(placeholder="Pick announcement intervals...", options=options)
            
            async def announce_callback(inter: Interaction):
                val = selector.values[0]
                if val == "custom":
                    await inter.response.send_modal(QuickModal("Custom Announcements", "Announcement Times (minutes)", "restart_announcements", str, view))
                else:
                    config.set('restart_announcements', val)
                    await inter.response.send_message(f"✅ Announcement times set to: `{val}` minutes", ephemeral=True)
                    await view.update_message(interaction)
                
            selector.callback = announce_callback
            temp_view.add_item(selector)
            await interaction.response.send_message("Choose a pre-made announcement sequence:", view=temp_view, ephemeral=True)

        else:
            # Fallback to a simple 1-field modal for text inputs
            modal_map = {
                "edit_server_dir": ("Server Directory Path", "server_directory"),
                "edit_startup_script": ("Startup Script Name", "startup_script"),
                "edit_log_dir": ("Log Directory Path", "log_directory"),
                "edit_shutdown_time": ("Shutdown Time (HH:MM)", "shutdown_time"),
                "edit_startup_time": ("Startup Time (HH:MM)", "startup_time"),
                "edit_api_endpoint": ("REST API Endpoint (IP:Port)", "rest_api_endpoint"),
                "edit_api_key": ("REST API Key (Admin Password)", "rest_api_key"),
                "edit_webhook": ("Chat Webhook URL", "chat_webhook_url")
            }
            
            label, key, *data_type = modal_map.get(self.custom_id, ("Value", "unknown"))
            converter = data_type[0] if data_type else str
            
            await interaction.response.send_modal(QuickModal(f"Edit {label}", label, key, converter, view))


class QuickModal(nextcord.ui.Modal):
    def __init__(self, title, label, key, converter, parent_view):
        super().__init__(title=title)
        self.key = key
        self.converter = converter
        self.parent_view = parent_view
        self.input = nextcord.ui.TextInput(
            label=label,
            placeholder=f"Enter {label.lower()}...",
            default_value=str(config.get(key, '')),
            required=True
        )
        self.add_item(self.input)
    
    async def callback(self, inter: Interaction):
        try:
            val = self.converter(self.input.value)
            config.set(self.key, val)
            await inter.response.send_message(f"✅ Updated `{self.key}` successfully!", ephemeral=True)
            await self.parent_view.update_message(inter)
        except ValueError:
            await inter.response.send_message(f"❌ Invalid input format for {self.key}.", ephemeral=True)


class StatusEmbedView(View):
    """View that shows server status with buttons"""
    
    def __init__(self):
        super().__init__(timeout=None)
        # self.server_control_view = ServerControlView() # Not needed here
        
    async def interaction_check(self, interaction: Interaction) -> bool:
        return True
