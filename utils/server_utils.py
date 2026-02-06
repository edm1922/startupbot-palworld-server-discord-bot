import os
import subprocess
import psutil
import nextcord
import asyncio
from enum import Enum
from utils.config_manager import config
from utils.rest_api import rest_api

# Server State Enum
class ServerState(Enum):
    OFFLINE = "offline"
    STARTING = "starting"
    ONLINE = "online"
    STOPPING = "stopping"

# Global lock to prevent conflicting server operations (e.g. manual vs auto-restart)
server_lock = asyncio.Lock()

# Global server state tracking
_current_server_state = ServerState.OFFLINE
_state_change_callbacks = []

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

async def verify_server_responsive() -> bool:
    """Verify that the server is actually responsive via REST API."""
    if not rest_api.is_configured():
        print("⚠️ REST API not configured, cannot verify server responsiveness")
        return False
    
    try:
        # Try to get server info with a short timeout
        server_info = await rest_api.get_server_info()
        if server_info:
            print("✅ Server is responsive via REST API")
            return True
        else:
            print("⚠️ Server process running but REST API not responding")
            return False
    except Exception as e:
        print(f"⚠️ Error verifying server responsiveness: {e}")
        return False

def get_server_state() -> ServerState:
    """Get the current server state."""
    return _current_server_state

async def set_server_state(new_state: ServerState, bot=None):
    """Set the server state and trigger callbacks."""
    global _current_server_state
    
    if _current_server_state == new_state:
        return  # No change
    
    old_state = _current_server_state
    _current_server_state = new_state
    
    print(f"🔄 Server state changed: {old_state.value.upper()} → {new_state.value.upper()}")
    
    # Trigger callbacks (like updating channel name)
    for callback in _state_change_callbacks:
        try:
            await callback(new_state, bot)
        except Exception as e:
            print(f"⚠️ Error in state change callback: {e}")

def register_state_callback(callback):
    """Register a callback to be called when server state changes."""
    if callback not in _state_change_callbacks:
        _state_change_callbacks.append(callback)

# Track last rename time to avoid Discord 429 rate limits (limit is ~2 per 10 mins)
_last_rename_time = 0

async def update_status_channel_name(new_state: ServerState, bot):
    """Update the status channel name with emoji based on server state with rate limit protection."""
    global _last_rename_time
    import time
    
    if not bot:
        return
    
    status_channel_id = config.get('status_channel_id', 0)
    if not status_channel_id:
        return
    
    try:
        # Check cooldown (600 seconds = 10 minutes)
        now = time.time()
        if now - _last_rename_time < 600:
            return

        channel = bot.get_channel(status_channel_id)
        if not channel:
            channel = await bot.fetch_channel(status_channel_id)
        
        if not channel:
            return
        
        # Map states to emojis (Simplified to avoid rate limits: Red for busy/off, Green for online)
        state_emojis = {
            ServerState.OFFLINE: "🔴",
            ServerState.STARTING: "🔴",
            ServerState.ONLINE: "🟢",
            ServerState.STOPPING: "🔴"
        }
        
        emoji = state_emojis.get(new_state, "⚪")
        
        # Get base channel name
        current_name = channel.name
        base_name = current_name
        
        # Remove any existing status emoji (including old circle ones)
        old_emojis = ["🔴", "🟡", "🟢", "🟠", "❌", "🚀", "✅", "⚠️", "⚪"]
        for old_emoji in old_emojis:
            if current_name.startswith(old_emoji):
                base_name = current_name[len(old_emoji):].lstrip("-").strip()
                break
        
        # Create new name with emoji
        new_name = f"{emoji}-{base_name}" if base_name else f"{emoji}-server-status"
        
        # Only update if name actually changed
        if current_name != new_name:
            await channel.edit(name=new_name)
            _last_rename_time = now
            print(f"✅ Updated status channel name to: {new_name}")
    
    except nextcord.errors.HTTPException as e:
        if e.status == 429:
            print(f"⚠️ Discord Rate Limit: Cannot rename channel yet. Will try again later.")
            _last_rename_time = time.time()
        else:
            print(f"⚠️ Error updating status channel name: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error updating channel name: {e}")


async def stop_server(bot=None, graceful=True):
    """Stops the Palworld server, optionally trying gracefully first if REST API is configured."""
    print(f"🛑 [SHUTDOWN] stop_server(graceful={graceful}) initiated")
    
    # Set state to STOPPING
    await set_server_state(ServerState.STOPPING, bot)
    
    # 1. Immediate check: If server is already offline, return success early
    if not await is_server_running():
        print("ℹ️ [SHUTDOWN] Server is already offline.")
        await set_server_state(ServerState.OFFLINE, bot)
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
                        if not await is_server_running():
                            print(f"✅ [SHUTDOWN] Server process exited gracefully after {i}s.")
                            break
                        await asyncio.sleep(1)
            except asyncio.TimeoutError:
                print("⚠️ [SHUTDOWN] Graceful shutdown timed out.")
            except Exception as e:
                print(f"⚠️ [SHUTDOWN] Error during graceful attempt: {e}")
        
        # 3. Force kill any remaining processes (fallback)
        # Check both the binaries AND any wrapper scripts (like the batch file)
        print("🔪 [SHUTDOWN] Cleaning up server processes and wrappers...")
        if os.name == 'nt':
            # 3a. Kill known binaries
            for bin_name in ["PalServer.exe", "PalServer-Win64-Shipping.exe", "PalServer-Win64-Shipping-Cmd.exe"]:
                 subprocess.run(["taskkill", "/F", "/IM", bin_name, "/T"], shell=True, capture_output=True)
            
            # 3b. Kill any cmd.exe wrappers running our startup script
            startup_script = config.get('startup_script', '')
            if startup_script:
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        if proc.info['name'] and 'cmd.exe' in proc.info['name'].lower():
                            cmdline = proc.info.get('cmdline')
                            if cmdline and any(startup_script.lower() in str(arg).lower() for arg in cmdline):
                                print(f"🔪 [SHUTDOWN] Killing wrapper process PID {proc.info['pid']} ({startup_script})")
                                try: proc.kill()
                                except: pass
                except Exception as e:
                    print(f"⚠️ [SHUTDOWN] Error killing wrappers: {e}")
            
            # Pause to let OS release file handles/ports
            await asyncio.sleep(4)
        else:
            subprocess.run(["pkill", "-9", "-f", "PalServer"], shell=True)
            await asyncio.sleep(3)
            
        # 4. Final verification and notification
        offline_success = not await is_server_running()
        
        if offline_success:
            print("✅ [SHUTDOWN] Server is now confirmed OFFLINE.")
            await set_server_state(ServerState.OFFLINE, bot)
            
            if bot:
                status_channel_id = config.get('status_channel_id', 0)
                channel = bot.get_channel(status_channel_id)
                if channel:
                    embed = nextcord.Embed(title="paltastic", description="**OFFLINE**\nPalworld", color=0xFF0000)
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
    """Starts the Palworld server and verifies its status with REST API verification."""
    print("🚀 [STARTUP] start_server() initiated")
    
    # Set state to STARTING
    await set_server_state(ServerState.STARTING, bot)
    
    try:
        startup_script = config.get('startup_script', '')
        server_directory = config.get('server_directory', '')
        
        if not startup_script or not server_directory:
            print("⚠️ [STARTUP] Aborted: Missing script or directory in config.")
            await set_server_state(ServerState.OFFLINE, bot)
            return False

        if not os.path.exists(os.path.join(server_directory, startup_script)):
            print(f"⚠️ [STARTUP] Aborted: Startup script not found: {startup_script}")
            await set_server_state(ServerState.OFFLINE, bot)
            return False

        # Start the process
        if os.name == 'nt':
            # Use CREATE_NEW_CONSOLE to ensure independence and visibility for debugging.
            # Running directly via cmd /c ensures the wrapper script is trackable.
            # Removed '/b' as it often causes the process to attach to the bot's console.
            print(f"📂 [STARTUP] Running {startup_script} in {server_directory}")
            subprocess.Popen(
                f'cmd.exe /c {startup_script}', 
                cwd=server_directory, 
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
            )
        else:
            await asyncio.create_subprocess_exec("bash", startup_script, cwd=server_directory)
        
        # Send STARTING embed immediately
        status_channel_id = config.get('status_channel_id', 0)
        channel = bot.get_channel(status_channel_id) if bot else None
        if channel:
            embed = nextcord.Embed(title="paltastic", description="**STARTING**\nPalworld", color=0xFF8800)
            embed.set_footer(text="powered by Paltastic")
            try: await channel.send(embed=embed)
            except: pass

        # Phase 1: Wait for process to appear
        print("⏳ [STARTUP] Phase 1: Verifying process startup...")
        process_detected = False
        for i in range(10):  # Check for 20 seconds (10 * 2s)
            await asyncio.sleep(2)
            if await is_server_running():
                print(f"✅ [STARTUP] Server process detected after {i*2+2}s.")
                process_detected = True
                break
        
        if not process_detected:
            print("❌ [STARTUP] Server failed to appear in process list after launch attempt.")
            await set_server_state(ServerState.OFFLINE, bot)
            return False
        
        # Phase 2: Wait for REST API to become responsive (if configured)
        if rest_api.is_configured():
            print("⏳ [STARTUP] Phase 2: Waiting for REST API to become responsive...")
            api_responsive = False
            
            # Wait up to 120 seconds for REST API to respond (Increased for large saves)
            for i in range(60):  # 60 * 2s = 120 seconds
                await asyncio.sleep(2)
                if await verify_server_responsive():
                    print(f"✅ [STARTUP] REST API responsive after {(i+1)*2}s.")
                    api_responsive = True
                    break
                
                # Check if process is still running
                if not await is_server_running():
                    print("❌ [STARTUP] Server process died during REST API wait.")
                    await set_server_state(ServerState.OFFLINE, bot)
                    return False
            
            if not api_responsive:
                print("⚠️ [STARTUP] REST API did not respond within timeout, but process is running.")
                print("⚠️ [STARTUP] Server may still be initializing. Marking as STARTING.")
                # Keep state as STARTING - monitoring task will update when ready
                return True
        else:
            print("ℹ️ [STARTUP] REST API not configured, skipping Phase 2 verification.")
        
        # Success! Server is fully online
        print("✅ [STARTUP] Server is fully ONLINE and responsive!")
        await set_server_state(ServerState.ONLINE, bot)
        
        if bot:
            status_channel_id = config.get('status_channel_id', 0)
            channel = bot.get_channel(status_channel_id)
            if channel:
                embed = nextcord.Embed(title="paltastic", description="**ONLINE**\nPalworld", color=0x00FF00)
                embed.set_footer(text="powered by Paltastic")
                try: await channel.send(embed=embed)
                except: pass
        return True

    except Exception as e:
        print(f"❌ [STARTUP] Critical error: {e}")
        await set_server_state(ServerState.OFFLINE, bot)
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
    wait_time = 60 # Increased from 20 to avoid port 33103/33105 contention
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

