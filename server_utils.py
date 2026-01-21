import os
import subprocess
import psutil
import nextcord
import asyncio
from config_manager import config
from rest_api import rest_api

def is_server_running():
    """Check if the Palworld server is running by looking for actual binaries."""
    target_binaries = ["palserver.exe", "palserver-win64-shipping.exe", "palserver-win64-shipping-cmd.exe"]
    
    try:
        # Optimization: Use process_iter with only needed info
        for proc in psutil.process_iter(['name']):
            try:
                # Use .get() to safely access 'name' and avoid Potential KeyErrors
                name = proc.info.get('name')
                if name:
                    proc_name = name.lower()
                    if any(bin_name in proc_name for bin_name in target_binaries):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"⚠️ Error checking processes: {e}")
        
    return False

async def stop_server(bot=None, graceful=True):
    """Stops the Palworld server, optionally trying gracefully first if REST API is configured."""
    print(f"🛑 stop_server(graceful={graceful}) function called")
    
    # 1. Immediate check: If server is already offline, return success early
    if not is_server_running():
        print("ℹ️ stop_server: Server is already offline. Skipping shutdown logic.")
        return True

    try:
        # 2. Attempt Graceful Shutdown if REST API is configured
        if graceful and rest_api.is_configured():
            print("📡 Attempting to save world and shutdown gracefully...")
            # We don't want to wait forever if the server is hung
            try:
                await asyncio.wait_for(rest_api.save_world(), timeout=6.0)
                await asyncio.sleep(2) # Give it a moment to finish saving
                
                # Send the shutdown command
                success = await asyncio.wait_for(
                    rest_api.shutdown_server_gracefully(seconds=10, message="Server Restarting/Shutting Down"),
                    timeout=6.0
                )
                
                if success:
                    print("✅ Graceful shutdown command sent. Waiting for process to exit...")
                    # Wait up to 15 seconds for it to close on its own
                    for _ in range(15):
                        if not is_server_running():
                            print("✅ Server process exited gracefully.")
                            break
                        await asyncio.sleep(1)
            except asyncio.TimeoutError:
                print("⚠️ Graceful shutdown timed out. Proceeding to force kill.")
            except Exception as e:
                print(f"⚠️ Error during graceful shutdown attempt: {e}")
        
        # 3. Force kill any remaining processes (fallback)
        if is_server_running():
            print("🔪 Force-killing server processes...")
            if os.name == 'nt':
                # Use taskkill tree kill to ensure we get everything
                subprocess.run(["taskkill", "/F", "/IM", "PalServer.exe", "/T"], shell=True, capture_output=True)
                subprocess.run(["taskkill", "/F", "/IM", "PalServer-Win64-Shipping.exe", "/T"], shell=True, capture_output=True)
            else:
                subprocess.run(["pkill", "-f", "PalServer"], shell=True)
            
            # Brief pause to let OS clean up
            await asyncio.sleep(1)
            
        # 4. Final verification and notification
        if bot:
            status_channel_id = config.get('status_channel_id', 0)
            channel = bot.get_channel(status_channel_id)
            if channel:
                embed = nextcord.Embed(title="paltastic", description="🔴 **OFFLINE**\nPalworld", color=0xFF0000)
                embed.set_footer(text="powered by Paltastic")
                await channel.send(embed=embed)
        
        # Return success if it's now stopped
        return not is_server_running()
    except Exception as e:
        print(f"❌ Critical error in stop_server: {e}")
        return False

async def start_server(bot=None):
    """Starts the Palworld server using subprocess.Popen."""
    print("🚀 start_server() function called")
    try:
        startup_script = config.get('startup_script', '')
        server_directory = config.get('server_directory', '')
        
        if not startup_script or not server_directory:
            print("⚠️ Cannot start: Missing config script/dir")
            return False

        if os.name == 'nt':
            subprocess.Popen(["cmd.exe", "/c", startup_script], cwd=server_directory, shell=True)
        else:
            await asyncio.create_subprocess_exec("bash", startup_script, cwd=server_directory)
        
        if bot:
            status_channel_id = config.get('status_channel_id', 0)
            channel = bot.get_channel(status_channel_id)
            if channel:
                embed = nextcord.Embed(title="paltastic", description="🟢 **ONLINE**\nPalworld", color=0x00FF00)
                embed.set_footer(text="powered by Paltastic")
                await channel.send(embed=embed)
        return True
    except Exception as e:
        print(f"❌ Error in start_server: {e}")
        return False

async def restart_server(bot=None, graceful=True):
    """Full restart cycle: Stop then Start."""
    print(f"🔄 restart_server(graceful={graceful}) initiated")
    
    # 1. Stop the server completely
    stopped = await stop_server(bot, graceful=graceful)
    
    # If we couldn't stop it (and it's still running), we shouldn't try to start another instance
    if not stopped:
        print("❌ Restart Aborted: Failed to stop the server.")
        if bot:
            status_channel_id = config.get('status_channel_id', 0)
            channel = bot.get_channel(status_channel_id)
            if channel:
                embed = nextcord.Embed(title="Restart Failed", description="Could not stop the existing server process.", color=0xFF0000)
                await channel.send(embed=embed)
        return False

    # 2. Longer buffer time to ensure ports/files are released
    print("⏳ Waiting 15 seconds for complete shutdown...")
    await asyncio.sleep(15)
    
    # 3. Start the server
    return await start_server(bot)
