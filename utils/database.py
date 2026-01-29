import sqlite3
import os  # Core OS handling
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
import threading
import asyncio

class PlayerStatsDB:
    """Database handler for player statistics and rewards system (PALDOGS)"""
    
    def __init__(self, db_path: str = "player_stats.db"):
        # Go up from utils/ to root, then into data/
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(root_dir, "data", db_path)
        self.lock = threading.RLock()
        self.init_database()
    
    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Players table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    steam_id TEXT PRIMARY KEY,
                    player_name TEXT NOT NULL,
                    discord_id TEXT,
                    rank TEXT DEFAULT 'Trainer',
                    palmarks INTEGER DEFAULT 0,
                    total_playtime INTEGER DEFAULT 0,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    login_streak INTEGER DEFAULT 0,
                    last_login_date DATE,
                    active_announcer TEXT DEFAULT 'default'
                )
            ''')
            
            # Activity stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_stats (
                    steam_id TEXT PRIMARY KEY,
                    structures_built INTEGER DEFAULT 0,
                    items_crafted INTEGER DEFAULT 0,
                    tech_unlocked INTEGER DEFAULT 0,
                    chat_messages INTEGER DEFAULT 0,
                    FOREIGN KEY (steam_id) REFERENCES players(steam_id)
                )
            ''')
            
            # Session tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    steam_id TEXT NOT NULL,
                    login_time TIMESTAMP NOT NULL,
                    logout_time TIMESTAMP,
                    duration INTEGER,
                    FOREIGN KEY (steam_id) REFERENCES players(steam_id)
                )
            ''')
            
            # Reward history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reward_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    steam_id TEXT NOT NULL,
                    reward_type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    description TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (steam_id) REFERENCES players(steam_id)
                )
            ''')
            
            # Daily stats for leaderboards
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    steam_id TEXT NOT NULL,
                    date DATE NOT NULL,
                    palmarks_earned INTEGER DEFAULT 0,
                    playtime INTEGER DEFAULT 0,
                    structures_built INTEGER DEFAULT 0,
                    items_crafted INTEGER DEFAULT 0,
                    UNIQUE(steam_id, date),
                    FOREIGN KEY (steam_id) REFERENCES players(steam_id)
                )
            ''')
            
            # Migration: Rename dogcoin to palmarks in players table
            cursor.execute("PRAGMA table_info(players)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'dogcoin' in columns and 'palmarks' not in columns:
                try:
                    cursor.execute("ALTER TABLE players RENAME COLUMN dogcoin TO palmarks")
                    print("🔄 Migrated database: players.dogcoin -> players.palmarks")
                except Exception as e:
                    print(f"[ERROR] Migration error (players): {e}")

            # Migration: Rename dogcoin_earned to palmarks_earned in daily_stats table
            cursor.execute("PRAGMA table_info(daily_stats)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'dogcoin_earned' in columns and 'palmarks_earned' not in columns:
                try:
                    cursor.execute("ALTER TABLE daily_stats RENAME COLUMN dogcoin_earned TO palmarks_earned")
                    print("🔄 Migrated database: daily_stats.dogcoin_earned -> daily_stats.palmarks_earned")
                except Exception as e:
                    print(f"[ERROR] Migration error (daily_stats): {e}")

            # Migration: Add active_announcer column if not exists
            cursor.execute("PRAGMA table_info(players)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'active_announcer' not in columns:
                try:
                    cursor.execute("ALTER TABLE players ADD COLUMN active_announcer TEXT DEFAULT 'default'")
                    print("🔄 Migrated database: Added active_announcer to players")
                except Exception as e:
                    print(f"[ERROR] Migration error (announcer): {e}")

            conn.commit()
            conn.close()
            print("[OK] Database initialized successfully")
    
    async def upsert_player(self, steam_id: str, player_name: str, discord_id: str = None):
        """Insert or update player information (Async)"""
        await asyncio.to_thread(self._upsert_player, steam_id, player_name, discord_id)

    def _upsert_player(self, steam_id: str, player_name: str, discord_id: str = None):
        """Insert or update player information (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO players (steam_id, player_name, discord_id, last_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(steam_id) DO UPDATE SET
                    player_name = excluded.player_name,
                    discord_id = COALESCE(excluded.discord_id, discord_id),
                    last_seen = CURRENT_TIMESTAMP
            ''', (steam_id, player_name, discord_id))
            
            # Ensure activity stats entry exists
            cursor.execute('''
                INSERT OR IGNORE INTO activity_stats (steam_id)
                VALUES (?)
            ''', (steam_id,))
            
            conn.commit()
            conn.close()

    async def link_account(self, steam_id: str, discord_id: int):
        """Link a Steam ID to a Discord ID (Async)"""
        await asyncio.to_thread(self._link_account, steam_id, discord_id)

    def _link_account(self, steam_id: str, discord_id: int):
        """Link a Steam ID to a Discord ID (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if this discord_id is already linked to another steam_id
            cursor.execute("UPDATE players SET discord_id = NULL WHERE discord_id = ?", (str(discord_id),))
            
            # Link to the new steam_id
            cursor.execute("UPDATE players SET discord_id = ? WHERE steam_id = ?", (str(discord_id), steam_id))
            
            conn.commit()
            conn.close()

    async def get_player_by_discord(self, discord_id: int) -> Optional[Dict]:
        """Find player data by Discord ID (Async)"""
        return await asyncio.to_thread(self._get_player_by_discord, discord_id)

    def _get_player_by_discord(self, discord_id: int) -> Optional[Dict]:
        """Find player data by Discord ID (Internal)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players WHERE discord_id = ?", (str(discord_id),))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    async def record_login(self, steam_id: str, player_name: str):
        """Record player login (Async)"""
        return await asyncio.to_thread(self._record_login, steam_id, player_name)

    def _record_login(self, steam_id: str, player_name: str):
        """Record player login (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Update player
            self._upsert_player(steam_id, player_name)
            
            # Check login streak
            cursor.execute('''
                SELECT last_login_date, login_streak FROM players WHERE steam_id = ?
            ''', (steam_id,))
            result = cursor.fetchone()
            
            today = datetime.now().date()
            new_streak = 1
            is_first_today = True
            
            if result and result['last_login_date']:
                last_date = datetime.strptime(result['last_login_date'], '%Y-%m-%d').date()
                days_diff = (today - last_date).days
                
                if days_diff == 1:
                    new_streak = result['login_streak'] + 1
                elif days_diff == 0:
                    new_streak = result['login_streak']
                    is_first_today = False
            
            # Update streak
            cursor.execute('''
                UPDATE players 
                SET login_streak = ?, last_login_date = ?
                WHERE steam_id = ?
            ''', (new_streak, today.isoformat(), steam_id))
            
            # Create session
            cursor.execute('''
                INSERT INTO sessions (steam_id, login_time)
                VALUES (?, CURRENT_TIMESTAMP)
            ''', (steam_id,))
            
            conn.commit()
            conn.close()
            
            return new_streak, is_first_today
    
    async def record_logout(self, steam_id: str):
        """Record player logout and calculate session duration (Async)"""
        await asyncio.to_thread(self._record_logout, steam_id)

    def _record_logout(self, steam_id: str):
        """Record player logout and calculate session duration (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Find active session
            cursor.execute('''
                SELECT id, login_time FROM sessions
                WHERE steam_id = ? AND logout_time IS NULL
                ORDER BY login_time DESC LIMIT 1
            ''', (steam_id,))
            
            session = cursor.fetchone()
            if session:
                login_time = datetime.fromisoformat(session['login_time'])
                logout_time = datetime.now()
                duration = int((logout_time - login_time).total_seconds())
                
                # Update session
                cursor.execute('''
                    UPDATE sessions
                    SET logout_time = ?, duration = ?
                    WHERE id = ?
                ''', (logout_time.isoformat(), duration, session['id']))
                
                # Update total playtime
                cursor.execute('''
                    UPDATE players
                    SET total_playtime = total_playtime + ?
                    WHERE steam_id = ?
                ''', (duration, steam_id))
                
                conn.commit()
            
            conn.close()
    
    async def add_activity(self, steam_id: str, activity_type: str, count: int = 1):
        """Record player activity (Async)"""
        await asyncio.to_thread(self._add_activity, steam_id, activity_type, count)

    def _add_activity(self, steam_id: str, activity_type: str, count: int = 1):
        """Record player activity (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if activity_type == 'building':
                cursor.execute('''
                    UPDATE activity_stats
                    SET structures_built = structures_built + ?
                    WHERE steam_id = ?
                ''', (count, steam_id))
            elif activity_type == 'crafting':
                cursor.execute('''
                    UPDATE activity_stats
                    SET items_crafted = items_crafted + ?
                    WHERE steam_id = ?
                ''', (count, steam_id))
            elif activity_type == 'tech':
                cursor.execute('''
                    UPDATE activity_stats
                    SET tech_unlocked = tech_unlocked + ?
                    WHERE steam_id = ?
                ''', (count, steam_id))
            elif activity_type == 'chat':
                cursor.execute('''
                    UPDATE activity_stats
                    SET chat_messages = chat_messages + ?
                    WHERE steam_id = ?
                ''', (count, steam_id))
            
            conn.commit()
            conn.close()
    
    async def add_palmarks(self, steam_id: str, amount: int, reason: str = ""):
        """Add PALDOGS to player (Async)"""
        await asyncio.to_thread(self._add_palmarks, steam_id, amount, reason)

    def _add_palmarks(self, steam_id: str, amount: int, reason: str = ""):
        """Add PALDOGS to player (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE players
                SET palmarks = palmarks + ?
                WHERE steam_id = ?
            ''', (amount, steam_id))
            
            # Record in history
            cursor.execute('''
                INSERT INTO reward_history (steam_id, reward_type, amount, description)
                VALUES (?, 'paldogs', ?, ?)
            ''', (steam_id, amount, reason))
            
            # Update daily stats
            today = datetime.now().date().isoformat()
            cursor.execute('''
                INSERT INTO daily_stats (steam_id, date, palmarks_earned)
                VALUES (?, ?, ?)
                ON CONFLICT(steam_id, date) DO UPDATE SET
                    palmarks_earned = palmarks_earned + excluded.palmarks_earned
            ''', (steam_id, today, amount))
            
            conn.commit()
            conn.close()
    
    async def get_player_stats(self, steam_id: str) -> Optional[Dict]:
        """Get complete player statistics (Async)"""
        return await asyncio.to_thread(self._get_player_stats, steam_id)

    def _get_player_stats(self, steam_id: str) -> Optional[Dict]:
        """Get complete player statistics (Internal)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, a.*
            FROM players p
            LEFT JOIN activity_stats a ON p.steam_id = a.steam_id
            WHERE p.steam_id = ?
        ''', (steam_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return dict(result)
        return None
    
    async def get_server_stats(self) -> Dict:
        """Get overall server statistics (PALDOGS dashboard) (Async)"""
        return await asyncio.to_thread(self._get_server_stats)

    def _get_server_stats(self) -> Dict:
        """Get overall server statistics (Internal)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Active players today
        today = datetime.now().date().isoformat()
        cursor.execute('''
            SELECT COUNT(DISTINCT steam_id) as count
            FROM sessions
            WHERE DATE(login_time) = ?
        ''', (today,))
        active_today = cursor.fetchone()['count']
        
        # Total PalMarks earned today
        cursor.execute('''
            SELECT COALESCE(SUM(palmarks_earned), 0) as total
            FROM daily_stats
            WHERE date = ?
        ''', (today,))
        palmarks_today = cursor.fetchone()['total']
        
        # Total structures built today
        cursor.execute('''
            SELECT COALESCE(SUM(structures_built), 0) as total
            FROM daily_stats
            WHERE date = ?
        ''', (today,))
        structures_today = cursor.fetchone()['total']
        
        # Total items crafted today
        cursor.execute('''
            SELECT COALESCE(SUM(items_crafted), 0) as total
            FROM daily_stats
            WHERE date = ?
        ''', (today,))
        crafts_today = cursor.fetchone()['total']
        
        # All-time totals
        cursor.execute('''
            SELECT 
                COALESCE(SUM(structures_built), 0) as total_structures,
                COALESCE(SUM(items_crafted), 0) as total_crafts
            FROM activity_stats
        ''')
        totals = cursor.fetchone()
        
        conn.close()
        
        return {
            'active_today': active_today,
            'palmarks_today': palmarks_today,
            'structures_today': structures_today,
            'crafts_today': crafts_today,
            'total_structures': totals['total_structures'] if totals else 0,
            'total_crafts': totals['total_crafts'] if totals else 0
        }

    async def get_total_players_count(self) -> int:
        """Get total number of registered players (Async)"""
        return await asyncio.to_thread(self._get_total_players_count)

    def _get_total_players_count(self) -> int:
        """Get total number of registered players (Internal)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM players')
        count = cursor.fetchone()['count']
        conn.close()
        return count
    
    async def get_leaderboard(self, category: str = 'dogcoin', limit: int = 10) -> List[Dict]:
        """Get leaderboard for specified category (Async)"""
        return await asyncio.to_thread(self._get_leaderboard, category, limit)

    def _get_leaderboard(self, category: str = 'dogcoin', limit: int = 10) -> List[Dict]:
        """Get leaderboard for specified category (Internal)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if category == 'palmarks':
            cursor.execute('''
                SELECT player_name, palmarks, rank
                FROM players
                ORDER BY palmarks DESC
                LIMIT ?
            ''', (limit,))
        elif category == 'playtime':
            cursor.execute('''
                SELECT player_name, total_playtime, rank
                FROM players
                ORDER BY total_playtime DESC
                LIMIT ?
            ''', (limit,))
        elif category == 'building':
            cursor.execute('''
                SELECT p.player_name, a.structures_built, p.rank
                FROM players p
                JOIN activity_stats a ON p.steam_id = a.steam_id
                ORDER BY a.structures_built DESC
                LIMIT ?
            ''', (limit,))
        elif category == 'crafting':
            cursor.execute('''
                SELECT p.player_name, a.items_crafted, p.rank
                FROM players p
                JOIN activity_stats a ON p.steam_id = a.steam_id
                ORDER BY a.items_crafted DESC
                LIMIT ?
            ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    async def update_player_rank(self, steam_id: str, new_rank: str):
        """Update player's rank (Async)"""
        await asyncio.to_thread(self._update_player_rank, steam_id, new_rank)

    def _update_player_rank(self, steam_id: str, new_rank: str):
        """Update player's rank (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE players
                SET rank = ?
                WHERE steam_id = ?
            ''', (new_rank, steam_id))
            
            conn.commit()
            conn.close()
            print(f"[OK] Updated {steam_id} to rank: {new_rank}")
    
    async def get_player_stats_by_name(self, player_name: str) -> Optional[Dict]:
        """Get player statistics by player name (Async)"""
        return await asyncio.to_thread(self._get_player_stats_by_name, player_name)

    def _get_player_stats_by_name(self, player_name: str) -> Optional[Dict]:
        """Get player statistics by player name (Internal)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, a.*
            FROM players p
            LEFT JOIN activity_stats a ON p.steam_id = a.steam_id
            WHERE p.player_name = ? COLLATE NOCASE
            ORDER BY p.last_seen DESC
            LIMIT 1
        ''', (player_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return dict(result)
        return None




    async def get_player_names_autocomplete(self, current: str) -> List[str]:
        """Get player names for autocomplete (Async)"""
        return await asyncio.to_thread(self._get_player_names_autocomplete, current)

    def _get_player_names_autocomplete(self, current: str) -> List[str]:
        """Get player names for autocomplete (Internal)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT player_name FROM players WHERE player_name LIKE ? LIMIT 25",
            (f"%{current}%",)
        )
        results = cursor.fetchall()
        conn.close()
        return [row['player_name'] for row in results]

    async def reset_all_progression(self):
        """Reset ALL player ranks and PalMarks to start over (Async)"""
        await asyncio.to_thread(self._reset_all_progression)

    def _reset_all_progression(self):
        """Reset ALL player ranks and PalMarks to start over (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Reset PALDOGS and Rank
            cursor.execute("UPDATE players SET palmarks = 0, rank = 'Trainer'")
            
            # Clear rewards history to be consistent
            cursor.execute("DELETE FROM reward_history")
            
            # Clear daily stats to reset leaderboards
            cursor.execute("DELETE FROM daily_stats")
            
            conn.commit()
            conn.close()
            print("🚨 [DATABASE] ALL PLAYER PROGRESSION RESET (PALDOGS=0, Rank=Trainer)")

    async def update_active_announcer(self, steam_id: str, announcer_id: str):
        """Update player's active announcer pack (Async)"""
        await asyncio.to_thread(self._update_active_announcer, steam_id, announcer_id)

    def _update_active_announcer(self, steam_id: str, announcer_id: str):
        """Update player's active announcer pack (Internal)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE players SET active_announcer = ? WHERE steam_id = ?", (announcer_id, steam_id))
            conn.commit()
            conn.close()

# Global instance
db = PlayerStatsDB()
