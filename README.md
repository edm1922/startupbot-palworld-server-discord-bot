# 🎮 Paltastic - Palworld Server Discord Bot

A premium, feature-rich Discord bot designed to manage Palworld Dedicated Servers with ease. Built for reliability, visual excellence, and effortless configuration.

---

## 🚀 Key Features

### ⚙️ Interactive Configuration Hub
*   **Embedded Interface**: No more cumbersome modals. Configure everything via a premium **Interactive Hub** using dropdowns and categories.
*   **Easy Selectors**: Use **Channel Selectors** and **User Selectors** to setup your server without typing a single ID manually.
*   **Simplified Mastery**: Choose common intervals (like 3h or 6h restarts) from dropdown lists instead of manually entering seconds.

### ⚡ Advanced Server Controls
*   **Interactive Panel**: Use the `/server_controls` panel with premium buttons (Start, Restart, Shutdown).
*   **Live Status**: Real-time server status updates (Online/Offline) sent to your designated status channel.
*   **Smart Checks**: Bot ensures the server is actually running before performing restarts, avoiding accidental startups during planned downtime.

### 🗨️ Cross-Chat Relay (Discord ↔️ Palworld)
*   **Bi-directional Chat**: Relay messages from Discord to in-game and vice versa.
*   **Premium Webhook Relay**: In-game chat is relayed to Discord via Webhooks, showing the actual player's name and avatar for a sleek look.
*   **Log-Based Relay**: Uses PalGuard/PalDefender logs for extremely reliable chat capturing.

### ⏰ Advanced Scheduling & Announcements
*   **Customizable Auto-Restarts**: Set deep maintenance cycles that restart your server automatically at specified intervals.
*   **In-Game Broadcasts**: Automatic breakdown warnings (e.g., 30m, 10m, 5m, 1m) broadcasted in-game before a restart occur so players can save their progress.
*   **System Monitoring**: Real-time RAM reports sent every 10 minutes to keep your hardware in check.

### 🌐 REST API Power
*   **Live Player List & Monitor**: `/players` command shows online players. Plus, get automatic **Join/Leave notifications** in Discord.
*   **Server Diagnostics**: `/serverinfo` provides technical details about your server instance.
*   **Manual World Saves**: Trigger a `/saveworld` command directly from Discord.

---

## 🛠️ Setup Instructions

1.  **Clone & Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

2.  **Authentication**:
    Add your bot token to the `.env` file:
    ```env
    DISCORD_BOT_TOKEN=your_token_here
    GUILD_ID=your_server_id
    ```

3.  **Run the Bot**:
    Run `start_bot.bat` or use the command line:
    ```powershell
    python startupbot.py
    ```

4.  **In-App Configuration**:
    Once the bot is online, type `/config` in your Discord server.
    *   **Main Hub**: Navigate through Categories using the main dropdown.
    *   **Channels**: Use the channel selector to bind the bot to specific Discord channels.
    *   **Schedule**: Set your restart intervals and pick an announcement preset.

---

## ⌨️ Command Reference

| Command | Type | Description |
| :-- | :-- | :-- |
| `/palhelp` | Slash | Displays this help menu |
| `/config` | Slash | Open the **Interactive Configuration Hub** (Admin only) |
| `/server_controls` | Slash | Show the interactive control panel (Admin only) |
| `/players` | Slash | List online players (requires REST API) |
| `/serverinfo` | Slash | Show technical server info (requires REST API) |
| `/saveworld` | Slash | Manually trigger a world save (Admin only) |
| `!startserver` | Prefix | Start the server (Admin only) |
| `!stopserver` | Prefix | Stop the server (Admin only) |

---

## 🔒 Security & Reliability
*   **Single Instance Lock**: Built-in protection prevents multiple instances of the bot from running simultaneously on the same port.
*   **Admin-Only Access**: Critical commands are locked behind Discord Administrator permissions or a specific `admin_user_id`.
*   **Data Integrity**: Configuration is handled through a thread-safe JSON manager, keeping your `.env` clean of non-sensitive data.

---

## 📦 Requirements
*   Python 3.10+
*   `nextcord`, `aiohttp`, `psutil`
*   Palworld Dedicated Server
*   (Optional) PalGuard/PalDefender for chat relay functionality

---
*Created by Paltastic - Powering your Palworld experience.*
