# 🎮 Paltastic - Palworld Server Discord Bot

A premium, feature-rich Discord bot designed to manage Palworld Dedicated Servers with ease. Built for reliability, visual excellence, and effortless configuration.

---

## 🚀 Key Features

### 🛠️ Effortless Configuration
*   **Discord-Integrated Setup**: No more messy `.env` file editing. Configure everything via high-quality **Discord Modals**.
*   **Automatic Migration**: Automatically moves your existing settings from `.env` to a persistent `bot_config.json`.

### ⚡ Advanced Server Controls
*   **Interactive Panel**: Use the `/server_controls` panel with premium buttons (Start, Restart, Shutdown).
*   **Live Status**: Real-time server status updates (Online/Offline) sent to your designated status channel.
*   **Legacy Support**: Prefix commands (`!startserver`, `!stopserver`) still available for classic users.

### 🗨️ Cross-Chat Relay (Discord ↔️ Palworld)
*   **Bi-directional Chat**: Relay messages from Discord to in-game and vice versa.
*   **Premium Webhook Relay**: In-game chat is relayed to Discord via Webhooks, showing the actual player's name and avatar for a sleek look.
*   **Log-Based Relay**: Uses PalGuard/PalDefender logs for extremely reliable chat capturing.

### 📊 System Monitoring & Scheduling
*   **RAM Usage Monitoring**: Automatically reports system memory usage to a dedicated channel every 10 minutes.
*   **Automated Tasks**: Configure scheduled server startups and shutdowns (e.g., daily restarts).

### 🌐 REST API Power
*   **Live Player List**: `/players` command shows online players via the Palworld REST API.
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
    *   **Channel Config**: Set up your Status, RAM, and Chat channels.
    *   **Server Config**: Set your PalServer directory and startup script.
    *   **REST API Config**: (Optional) Add your Admin Password and API endpoint for advanced features.

---

## ⌨️ Command Reference

| Command | Type | Description |
| :-- | :-- | :-- |
| `/palhelp` | Slash | Displays this help menu |
| `/config` | Slash | Open the configuration control center (Admin only) |
| `/server_controls` | Slash | Show the interactive control panel (Admin only) |
| `/players` | Slash | List online players (requires REST API) |
| `/serverinfo` | Slash | Show technical server info (requires REST API) |
| `/saveworld` | Slash | Manually trigger a world save (Admin only) |
| `!startserver` | Prefix | Start the server (Admin only) |
| `!stopserver` | Prefix | Stop the server (Admin only) |

---

## 🔒 Security & Reliability
*   **Single Instance Lock**: Built-in protection prevents multiple instances of the bot from running simultaneously.
*   **Admin-Only Access**: Critical commands are locked behind Discord Administrator permissions or a specific `admin_user_id`.
*   **Data Integrity**: Configuration is handled through a thread-safe JSON manager.

---

## 📦 Requirements
*   Python 3.10+
*   `nextcord`, `aiohttp`, `psutil`
*   Palworld Dedicated Server
*   (Optional) PalGuard/PalDefender for chat relay functionality

---
*Created by Paltastic - Powering your Palworld experience.*