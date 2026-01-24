import os
import subprocess
import psutil
import nextcord
import asyncio
from config_manager import config
from rest_api import rest_api

# Global lock to prevent conflicting server operations (e.g. manual vs auto-restart)
server_lock = asyncio.Lock()

# Caching for server status to prevent redundant process scans
_status_cache = {"running": False, "timestamp": 0}
STATUS_CACHE_TTL = 2.0 # 2 seconds

def _sync_is_server_running():
    """Synchronous implementation of process check."""
    target_binaries = ["palserver.exe", "palserver-win64-shipping.exe", "palserver-win64-shipping-cmd.exe"]
    try:
        # Fetching only 'name' is significantly faster than 'exe' or other fields
        for proc in psutil.process_iter(['name']):
            try:
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

async def is_server_running():
    """Check if the Palworld server is running (non-blocking with cache)."""
    import time
    now = time.time()
    
    # Return cached result if fresh
    if now - _status_cache["timestamp"] < STATUS_CACHE_TTL:
        return _status_cache["running"]
    
    # Run the synchronous check in a thread to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    is_running = await loop.run_in_executor(None, _sync_is_server_running)
    
    # Update cache
    _status_cache["running"] = is_running
    _status_cache["timestamp"] = now
    
    return is_running

async def stop_server(bot=None, graceful=True):
    """Stops the Palworld server, optionally trying gracefully first if REST API is configured."""
    print(f"🛑 [SHUTDOWN] stop_server(graceful={graceful}) initiated")
    
    # 1. Immediate check: If server is already offline, return success early
    if not await is_server_running():
        print("ℹ️ [SHUTDOWN] Server is already offline.")
        return True

    try:
        # 2. Attempt Graceful Shutdown if REST API is configured
        if graceful and rest_api.is_configured():
            print("📡 [SHUTDOWN] Attempting graceful shutdown via REST API...")
            try:
                # Broadcast and save
                await rest_api.broadcast_message("⚠️ SERVER SHUTTING DOWN FOR MAINTENANCE")
                await asyncio.wait_for(rest_api.save_world(), timeout=10.0)
                await asyncio.sleep(2)
                
                # Send the shutdown command
                success = await asyncio.wait_for(
                    rest_api.shutdown_server_gracefully(seconds=10, message="Server Restarting"),
                    timeout=10.0
                )
                
                if success:
                    print("✅ [SHUTDOWN] Graceful command sent. Waiting for process exit...")
                    # Wait up to 30 seconds for it to close (Palworld can be slow)
                    for i in range(30):
                        if not is_server_running():
                            print(f"✅ [SHUTDOWN] Server process exited gracefully after {i}s.")
                            break
                        await asyncio.sleep(1)
            except asyncio.TimeoutError:
                print("⚠️ [SHUTDOWN] Graceful shutdown timed out.")
            except Exception as e:
                print(f"⚠️ [SHUTDOWN] Error during graceful attempt: {e}")
        
        # 3. Force kill any remaining processes (fallback)
        if await is_server_running():
            print("🔪 [SHUTDOWN] Force-killing server processes...")
            if os.name == 'nt':
                # Kill both the launcher and the shipping binary tree
                for bin_name in ["PalServer.exe", "PalServer-Win64-Shipping.exe"]:
                     subprocess.run(["taskkill", "/F", "/IM", bin_name, "/T"], shell=True, capture_output=True)
            else:
                subprocess.run(["pkill", "-9", "-f", "PalServer"], shell=True)
            
            # Pause to let OS release file handles/ports
            await asyncio.sleep(3)
            
        # 4. Final verification and notification
        offline_success = not await is_server_running()
        
        if offline_success:
            print("✅ [SHUTDOWN] Server is now confirmed OFFLINE.")
            if bot:
                status_channel_id = config.get('status_channel_id', 0)
                channel = bot.get_channel(status_channel_id)
                if channel:
                    embed = nextcord.Embed(title="paltastic", description="🔴 **OFFLINE**\nPalworld", color=0xFF0000)
                    embed.set_footer(text="powered by Paltastic")
                    try: await channel.send(embed=embed)
                    except: pass
        else:
            print("❌ [SHUTDOWN] FAILED to stop server. Processes still persist.")
        
        return offline_success
    except Exception as e:
        print(f"❌ [SHUTDOWN] Critical error: {e}")
        return False

async def start_server(bot=None):
    """Starts the Palworld server and verifies its status."""
    print("🚀 [STARTUP] start_server() initiated")
    try:
        startup_script = config.get('startup_script', '')
        server_directory = config.get('server_directory', '')
        
        if not startup_script or not server_directory:
            print("⚠️ [STARTUP] Aborted: Missing script or directory in config.")
            return False

        if not os.path.exists(os.path.join(server_directory, startup_script)):
            print(f"⚠️ [STARTUP] Aborted: Startup script not found: {startup_script}")
            return False

        # Start the process
        if os.name == 'nt':
            # Use CREATE_NEW_CONSOLE to ensure independence and visibility for debugging
            # Also using 'start' command via shell ensures batch files run correctly
            print(f"📂 [STARTUP] Running {startup_script} in {server_directory}")
            subprocess.Popen(
                f'cmd.exe /c start /b {startup_script}', 
                cwd=server_directory, 
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
            )
        else:
            await asyncio.create_subprocess_exec("bash", startup_script, cwd=server_directory)
        
        # 5. Verification Loop: Wait and check if it actually stays running
        print("⏳ [STARTUP] Verifying process startup...")
        success = False
        for i in range(10): # Check for 10 seconds
            await asyncio.sleep(2)
            if await is_server_running():
                print(f"✅ [STARTUP] Server process detected after {i*2+2}s.")
                success = True
                break
        
        if success:
            if bot:
                status_channel_id = config.get('status_channel_id', 0)
                channel = bot.get_channel(status_channel_id)
                if channel:
                    embed = nextcord.Embed(title="paltastic", description="🟢 **ONLINE**\nPalworld", color=0x00FF00)
                    embed.set_footer(text="powered by Paltastic")
                    try: await channel.send(embed=embed)
                    except: pass
            return True
        else:
            print("❌ [STARTUP] Server failed to appear in process list after launch attempt.")
            return False

    except Exception as e:
        print(f"❌ [STARTUP] Critical error: {e}")
        return False

async def restart_server(bot=None, graceful=True):
    """Full restart cycle: Stop then Start with verification."""
    print(f"🔄 [RESTART] Global restart sequence beginning (Graceful={graceful})")
    
    # 1. Stop the server completely
    stopped = await stop_server(bot, graceful=graceful)
    
    if not stopped:
        print("❌ [RESTART] Aborted: Failed to stop the current instance.")
        if bot:
            try:
                allowed_channel_id = config.get('allowed_channel_id', 0)
                channel = bot.get_channel(allowed_channel_id)
                if channel:
                    await channel.send("⚠️ **Restart Failed:** Could not stop the existing server process. Aborting startup to prevent conflicts.")
            except: pass
        return False

    # 2. Safe buffer time
    # Palworld sometimes takes a while to release memory and network ports
    wait_time = 20 # Increased from 15
    print(f"⏳ [RESTART] Waiting {wait_time}s for system cleanup...")
    await asyncio.sleep(wait_time)
    
    # 3. Start the server
    started = await start_server(bot)
    
    if started:
        print("✅ [RESTART] Sequence completed successfully.")
    else:
        print("❌ [RESTART] Sequence failed during startup phase.")
        if bot:
            try:
                allowed_channel_id = config.get('allowed_channel_id', 0)
                channel = bot.get_channel(allowed_channel_id)
                if channel:
                    await channel.send("❌ **Restart Warning:** Shutdown succeeded, but server failed to start up! Please check manually.")
            except: pass
            
    return started

