import nextcord
from nextcord.ext import commands
import asyncio
import json
import datetime
import time
import os
import psutil
import re
import aiohttp
import logging
from collections import deque
from utils.config_manager import config
from utils.rest_api import rest_api
from utils.server_utils import is_server_running, start_server, stop_server, restart_server, server_lock
from utils.database import db
from utils.rcon_utility import rcon_util
from cogs.rank_system import rank_system
from cogs.kit_mgmt import kit_system
from cogs.pal_system import pal_system

class MonitorRelay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.running_tasks = {}
        self.next_restart_time = None
        self.restart_enabled = True
        self.chest_burst_tracker = {} # Track in-game rolls
        self.attempts = {"start": {}, "stop": {}}
        self.MAX_ATTEMPTS = 3
        self.ATTEMPT_RESET_TIME = 86400
        
        # Loop prevention for chat relay
        self.recent_relays = set()
        self.recent_relays_order = deque()
        self.MAX_RELAY_HISTORY = 100
        
        self.last_api_error_time = 0
        self.file_positions = {}
        self.line_buffer = "" # Buffer for partial lines
        self.roll_lock = asyncio.Lock() # Prevent concurrent in-game RCON rolls
        self.global_roll_count = 0
        self.global_cooldown_until = 0
        
        # Pre-compile regex patterns for performance
        self.chat_patterns = [
            re.compile(r"\[Chat::Global\]\['(?P<author>.+?)'\s*\(UserId=.*?\)\].*?:\s*(?P<content>.*)"),
            re.compile(r"\[Chat::(?:Global)\]\['(?P<author>[^']+)'.*\].*?:\s*(?P<content>.*)"),
            re.compile(r"\[Chat::Global\]\s*\[?(?P<author>[^'\[]+?)[\s'\]]*\(UserId=.*?\)\].*?:\s*(?P<content>.*)"),
            re.compile(r"\[.*?\]\[info\] \[Chat::Global\]\['(?P<author>.+?)' \(UserId=steam_\d+, IP=.+?\)\](?:\[.*?\])*:\s*(?P<content>.+)")
        ]
        
        # Initialize tasks
        self.bot.loop.create_task(self.start_tasks())

    async def start_tasks(self):
        await self.bot.wait_until_ready()
        
        # Register shared variables with bot for access from other cogs if needed
        self.bot.next_restart_time = self.next_restart_time
        
        task_mappings = {
            'monitor_ram': self.monitor_system_ram,
            'auto_restart': self.auto_restart,
            'scheduled_shutdown': self.scheduled_shutdown,
            'scheduled_startup': self.scheduled_startup,
            'reset_attempts': self.reset_attempts_task,
            'tail_logs': self.tail_palguard_logs,
            'monitor_players': self.monitor_players
        }
        
        for name, func in task_mappings.items():
            if name not in self.running_tasks or self.running_tasks[name].done():
                self.running_tasks[name] = asyncio.create_task(func())
                logging.info(f"🚀 Started background task: {name}")

    async def monitor_system_ram(self):
        while True:
            try:
                memory = psutil.virtual_memory()
                total_memory = memory.total / (1024 ** 3)
                used_memory = memory.used / (1024 ** 3)
                memory_percent = memory.percent
                
                ram_channel_id = config.get('ram_usage_channel_id', 0)
                ram_channel = self.bot.get_channel(ram_channel_id)
                if ram_channel:
                    await ram_channel.send(f"💻 **System RAM Usage:** {used_memory:.2f} GB / {total_memory:.2f} GB ({memory_percent}% used)")
            except Exception as e:
                logging.error(f"Error in monitor_ram: {e}")
            await asyncio.sleep(600)

    async def monitor_players(self):
        last_players = {}
        first_run = True
        
        while True:
            try:
                if not rest_api.is_configured():
                    await asyncio.sleep(60)
                    continue
                
                import time
                if time.time() - self.last_api_error_time < 60:
                     await asyncio.sleep(10)
                     continue
                
                if not await is_server_running():
                    if last_players:
                        print("📡 Server offline: Clearing player monitoring state.")
                        last_players = {}
                    first_run = True
                    await asyncio.sleep(15)
                    continue

                player_data = await rest_api.get_player_list()
                if player_data is not None:
                    players = player_data.get('players', [])
                    current_players = {p.get('userId'): p.get('name', 'Unknown') for p in players if p.get('userId')}
                    
                    if not first_run:
                        # Joined
                        for uid, name in current_players.items():
                            if uid not in last_players:
                                print(f"📥 Player detected: {name} ({uid}) joined.")
                                await self.send_player_event(name, "joined")
                        
                        # Left
                        for uid, name in last_players.items():
                            if uid not in current_players:
                                print(f"📤 Player detected: {name} ({uid}) left.")
                                await self.send_player_event(name, "left")
                    
                    # Ensure all online players are in DB
                    for uid, name in current_players.items():
                        await db.upsert_player(uid, name)
                    
                    last_players = current_players
                    first_run = False
            except Exception as e:
                if "Timeout" not in str(e) and "Connection" not in str(e):
                    logging.error(f"Error in monitor_players: {e}")
                self.last_api_error_time = time.time()
            
            await asyncio.sleep(20)

    async def send_player_event(self, name, event_type):
        channel_id = config.get('player_monitor_channel_id', 0)
        if not channel_id: return
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        if channel:
            color = 0x00FF00 if event_type == "joined" else 0xFF0000
            embed = nextcord.Embed(
                description=f"{'📥' if event_type == 'joined' else '📤'} **{name}** has {event_type} the server.",
                color=color,
                timestamp=nextcord.utils.utcnow()
            )
            await channel.send(embed=embed)


    async def reset_attempts_task(self):
        while True:
            await asyncio.sleep(self.ATTEMPT_RESET_TIME)
            self.attempts["start"].clear()
            self.attempts["stop"].clear()

    async def auto_restart(self):
        while True:
            try:
                # 1. Immediate check if enabled
                if not config.get('auto_restart_enabled', True) or not self.restart_enabled:
                    self.next_restart_time = None
                    self.bot.next_restart_time = None
                    await asyncio.sleep(30)
                    continue

                interval = config.get('restart_interval', 10800)
                if interval < 600:
                    logging.warning(f"⚠️ Restart interval ({interval}s) is too short. Defaulting to 10800s (3h).")
                    interval = 10800

                announcements_str = config.get('restart_announcements', '30,10,5,1')
                try:
                    announce_times = sorted([int(m.strip()) * 60 for m in announcements_str.split(',') if m.strip().isdigit()], reverse=True)
                except:
                    announce_times = [1800, 600, 300, 60]

                countdown_duration = max(announce_times) if announce_times else 0
                now = datetime.datetime.now()
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                seconds_since_midnight = (now - midnight).total_seconds()
                
                intervals_passed = int(seconds_since_midnight // interval)
                next_interval_seconds = (intervals_passed + 1) * interval
                target_time = midnight + datetime.timedelta(seconds=next_interval_seconds)
                
                if (target_time - now).total_seconds() < -30: 
                    next_interval_seconds += interval
                    target_time = midnight + datetime.timedelta(seconds=next_interval_seconds)
                
                time_until_target = (target_time - now).total_seconds()
                initial_sleep = max(0, time_until_target - countdown_duration)
                
                self.next_restart_time = target_time
                self.bot.next_restart_time = target_time
                
                logging.info(f"🚥 Auto-Restart Scheduled for: {target_time} (in {time_until_target:.1f}s)")
                
                # Sleep in increments so we can react to toggle changes faster
                while initial_sleep > 0:
                    if not config.get('auto_restart_enabled', True): break
                    sleep_chunk = min(initial_sleep, 60)
                    await asyncio.sleep(sleep_chunk)
                    initial_sleep -= sleep_chunk

                # Re-check before starting countdown
                if not config.get('auto_restart_enabled', True) or not self.restart_enabled or not await is_server_running():
                    await asyncio.sleep(10)
                    continue

                # Smart Countdown Loop
                now = datetime.datetime.now()
                remaining_seconds = (target_time - now).total_seconds()
                
                if remaining_seconds > 0:
                    valid_announcements = [t for t in announce_times if t < remaining_seconds]
                    
                    if valid_announcements:
                        first_wait = remaining_seconds - valid_announcements[0]
                        if first_wait > 0:
                            await asyncio.sleep(first_wait)
                            
                        for i, wait_sec in enumerate(valid_announcements):
                            # Mid-countdown check
                            if not config.get('auto_restart_enabled', True): 
                                logging.info("🛑 Auto-Restart aborted mid-countdown (Disabled by user).")
                                break

                            mins = wait_sec // 60
                            msg = f"⚠️ SERVER RESTART IN {mins} MINUTE{'S' if mins != 1 else ''} FOR MAINTENANCE"
                            if wait_sec < 60: msg = f"⚠️ SERVER RESTART IN {wait_sec} SECONDS"
                            
                            if rest_api.is_configured(): 
                                await rest_api.broadcast_message(msg)
                            
                            if i < len(valid_announcements) - 1:
                                await asyncio.sleep(wait_sec - valid_announcements[i+1])
                            else:
                                await asyncio.sleep(valid_announcements[-1])
                        
                        if not config.get('auto_restart_enabled', True):
                            continue # Skip the actual restart
                    else:
                        await asyncio.sleep(remaining_seconds)
                
                # Final check
                if config.get('auto_restart_enabled', True) and self.restart_enabled:
                    async with server_lock:
                        await restart_server(self.bot, graceful=True)
                else:
                    logging.info("🛑 Auto-Restart aborted last-second (Disabled by user).")
            except Exception as e:
                logging.error(f"Error in auto_restart: {e}")
                await asyncio.sleep(60)

    async def scheduled_shutdown(self):
        last_triggered_date = None
        while True:
            try:
                now = datetime.datetime.now()
                shutdown_str = config.get('shutdown_time', '05:00')
                if ':' in shutdown_str:
                    h, m = map(int, shutdown_str.split(':'))
                    if now.hour == h and now.minute == m and last_triggered_date != now.date():
                        if await is_server_running():
                            if rest_api.is_configured():
                                await rest_api.broadcast_message("⚠️ DAILY SCHEDULED SHUTDOWN IN 10 SECONDS")
                                await asyncio.sleep(10)
                            async with server_lock:
                                await stop_server(self.bot, graceful=True)
                        last_triggered_date = now.date()
            except Exception as e: logging.error(f"Error in scheduled_shutdown: {e}")
            await asyncio.sleep(10)

    async def scheduled_startup(self):
        last_triggered_date = None
        while True:
            try:
                now = datetime.datetime.now()
                startup_str = config.get('startup_time', '10:00')
                if ':' in startup_str:
                    h, m = map(int, startup_str.split(':'))
                    if now.hour == h and now.minute == m and last_triggered_date != now.date():
                        if not await is_server_running():
                            async with server_lock:
                                await start_server(self.bot)
                        last_triggered_date = now.date()
            except Exception as e: logging.error(f"Error in scheduled_startup: {e}")
            await asyncio.sleep(10)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        chat_channel_id = config.get('chat_channel_id', 0)
        if message.channel.id == chat_channel_id and not message.content.startswith('!'):
            msg_hash = hash(message.content.strip())
            entry = (message.author.display_name, msg_hash)
            
            if entry in self.recent_relays: return

            self.recent_relays.add(entry)
            self.recent_relays_order.append(entry)
            if len(self.recent_relays_order) > self.MAX_RELAY_HISTORY:
                self.recent_relays.discard(self.recent_relays_order.popleft())

            if rest_api.is_configured():
                broadcast_text = f"[Discord] {message.author.display_name}: {message.content}"
                await rest_api.broadcast_message(broadcast_text)

    async def tail_palguard_logs(self):
        current_log_file = None
        
        while True:
            try:
                log_dir = config.get('log_directory', '').strip()
                chat_channel_id = config.get('chat_channel_id', 0)
                
                if not log_dir or not chat_channel_id or not os.path.exists(log_dir):
                    await asyncio.sleep(10)
                    continue
                
                # Get the latest log file
                files = sorted(
                    [f for f in os.listdir(log_dir) if f.endswith('.log') or f.endswith('.txt')],
                    key=lambda x: os.path.getmtime(os.path.join(log_dir, x)),
                    reverse=True
                )
                
                if not files:
                    await asyncio.sleep(5)
                    continue
                    
                latest_file = os.path.join(log_dir, files[0])
                
                # If we switched files, initialize position to end of file
                if latest_file != current_log_file:
                    current_log_file = latest_file
                    with open(current_log_file, 'rb') as f:
                        f.seek(0, 2) # Go to end
                        self.file_positions[current_log_file] = f.tell()
                    logging.info(f"📁 Now tailing new log file: {os.path.basename(current_log_file)}")
                    await asyncio.sleep(1)
                    continue

                # Read new data from current file
                chunk = ""
                pos = self.file_positions.get(current_log_file, 0)
                
                with open(current_log_file, 'rb') as f:
                    # Check if file was truncated
                    f.seek(0, 2)
                    size = f.tell()
                    if size < pos:
                        pos = 0
                    
                    if size > pos:
                        f.seek(pos)
                        chunk = f.read().decode('utf-8', errors='replace')
                        self.file_positions[current_log_file] = f.tell()

                if not chunk:
                    await asyncio.sleep(1)
                    continue
                
                # Use line buffer to handle partial lines
                self.line_buffer += chunk
                if '\n' not in self.line_buffer:
                    continue
                
                parts = self.line_buffer.split('\n')
                new_lines = parts[:-1] # All complete lines
                self.line_buffer = parts[-1] # Remaining partial line
                
                if new_lines:
                    from utils.log_parser import log_parser
                    from utils.rest_api import rest_api
                    
                    chat_channel = self.bot.get_channel(chat_channel_id) or await self.bot.fetch_channel(chat_channel_id)
                    monitor_channel_id = config.get('player_monitor_channel_id', chat_channel_id)
                    monitor_channel = self.bot.get_channel(monitor_channel_id) or await self.bot.fetch_channel(monitor_channel_id)
                    webhook_url = config.get('chat_webhook_url', '').strip()

                    for line in new_lines:
                        if not line.strip(): continue
                        
                        # 1. Process Game Activity via log_parser
                        line_hash = str(hash(line))
                        try:
                            activity = log_parser.parse_line(line, line_hash)
                            if activity:
                                # Special Case: Chat Command Handling
                                if activity['type'] == 'chat':
                                    msg = activity['message'].strip()
                                    if msg.startswith('/') or msg.startswith('!'):
                                        asyncio.create_task(self.handle_ingame_command(activity['player_name'], activity['steam_id'], msg))
                                
                                reward, d_msg, g_msg = await log_parser.process_activity(activity)
                                
                                # Send Discord notification for activity
                                if d_msg and monitor_channel:
                                    try: await monitor_channel.send(d_msg)
                                    except Exception as e: logging.error(f"Error sending activity to Discord: {e}")
                                    
                                # Send in-game broadcast for special events
                                if g_msg and rest_api.is_configured():
                                    await rest_api.broadcast_message(g_msg)
                        except Exception as e:
                            logging.error(f"Error in activity processing: {e}")

                        # 2. Process Chat Relay (Game -> Discord)
                        match = None
                        for p in self.chat_patterns:
                            match = p.search(line)
                            if match: break
                            
                        if match:
                            match_data = match.groupdict()
                            author = match_data.get('author', 'Unknown').strip("'[] ")
                            content = match_data.get('content', '').strip()
                            
                            if not content: continue
                            
                            # Loop prevention: Ignore messages that were sent from Discord to Game
                            if content.startswith("[Discord]"):
                                continue

                            # Loop prevention: Ignore messages already relayed by comparing author and content hash
                            msg_hash = hash(content)
                            entry = (author, msg_hash)
                            
                            if entry not in self.recent_relays:
                                self.recent_relays.add(entry)
                                self.recent_relays_order.append(entry)
                                if len(self.recent_relays_order) > self.MAX_RELAY_HISTORY:
                                    self.recent_relays.discard(self.recent_relays_order.popleft())
                                
                                logging.info(f"💬 Chat detected: {author}: {content}")
                                
                                try:
                                    if webhook_url:
                                        session = getattr(self.bot, 'http_session', None)
                                        if session and not session.closed:
                                            webhook = nextcord.Webhook.from_url(webhook_url, session=session)
                                            await webhook.send(content=content, username=author)
                                        else:
                                            async with aiohttp.ClientSession() as temp_session:
                                                webhook = nextcord.Webhook.from_url(webhook_url, session=temp_session)
                                                await webhook.send(content=content, username=author)
                                    elif chat_channel:
                                        await chat_channel.send(f"**[Game] {author}**: {content}")
                                except Exception as e:
                                    logging.error(f"Chat Relay error: {e}")
                                    if chat_channel:
                                        try: await chat_channel.send(f"**[Game] {author}**: {content}")
                                        except: pass
            except Exception as e:
                logging.error(f"Error in tail_logs: {e}")
                import traceback
                traceback.print_exc()
            await asyncio.sleep(1)

    async def handle_ingame_command(self, player_name, steam_id, message):
        content = message.strip()
        if not content: return
        
        parts = content.split()
        if not parts: return
        
        raw_token = parts[0]
        if not raw_token.startswith('!'):
            # Ignore anything not starting with ! to avoid mod conflicts
            return

        cmd = raw_token[1:].lower() # Remove !
        
        logging.info(f"🕹️ Command detected from {player_name} ({steam_id}): {cmd}")

        if cmd in ["profile", "p", "stats"]:
            await self.handle_profile_command(steam_id, player_name)
        elif cmd in ["balance", "bal", "money", "marks"]:
            await self.handle_balance_command(steam_id, player_name)
        # Abolished !roll / !chest roll commands

    async def handle_profile_command(self, steam_id, player_name):
        stats = await db.get_player_stats(steam_id)
        if not stats: return
        
        rank = stats.get('rank', 'Trainer')
        level = stats.get('level', 1)
        pm = stats.get('palmarks', 0)
        exp = stats.get('experience', 0)
        
        # Get progress
        progress = await rank_system.get_progress_to_next_rank(steam_id)
        prog_str = ""
        if progress:
            prog_str = f" | EXP: {exp:,}/{progress['required_exp']:,} ({progress['percentage']}%)"
            
        msg = f"[PROFILE] {player_name} | Rank: {rank} | Level: {level} | PALDOGS: {pm:,}{prog_str}"
        res = await rcon_util.send_private_message(steam_id, msg)
        logging.info(f"🕹️ Tell Profile result: {res}")

    async def handle_balance_command(self, steam_id, player_name):
        stats = await db.get_player_stats(steam_id)
        if not stats: return
        pm = stats.get('palmarks', 0)
        exp = stats.get('experience', 0)
        msg = f"[BALANCE] {player_name} | PALDOGS: {pm:,} | EXP: {exp:,} (Lv.{stats.get('level', 1)})"
        await rcon_util.send_private_message(steam_id, msg)

def setup(bot):
    bot.add_cog(MonitorRelay(bot))
