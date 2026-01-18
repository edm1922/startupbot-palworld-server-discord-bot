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
        self.server_starting = False
        self.server_stopping = False

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

    def __init__(self):
        super().__init__(timeout=None)  # No timeout to keep persistent
        self._processing_lock = False

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


class StatusEmbedView(View):
    """View that shows server status with buttons"""
    
    def __init__(self):
        super().__init__(timeout=None)
        # self.server_control_view = ServerControlView() # Not needed here
        
    async def interaction_check(self, interaction: Interaction) -> bool:
        return True