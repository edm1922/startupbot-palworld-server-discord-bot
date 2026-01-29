# 🎮 Paltastic - Palworld Server Discord Bot

A premium, feature-rich Discord bot designed to manage Palworld Dedicated Servers with ease. Built for reliability, visual excellence, and effortless configuration.

---

## 🚀 Key Features

### 🎁 Giveaway & Reward System
*   **Interactive Giveaways**: Create giveaways for **Kits** or **Pals** directly from Discord.
*   **Smart Claiming**: Winners receive a private "Claim Reward" button. The bot checks if the player is currently online before delivering the prize.
*   **Automated Delivery**: Prizes are delivered via RCON or PalGuard commands automatically.

### 📊 Live Stats & Leaderboards
*   **Dynamic Stats Channel**: A dedicated channel that auto-updates with server status, player counts, and system performance.
*   **Player Leaderboards**: Real-time rankings showing the top players by activity and wealth (**PALDOGS**).
*   **Interactive Profile**: Players can check their `/profile` to see their rank progress, balance, and active announcer pack.

### 🛒 Economic & Rank System
*   **PALDOGS Currency**: Earn currency through daily logins, activity streaks, and server participation.
*   **Progression Ranks**: Advance from **Trainer** to **Gym Leader** and **Champion**, unlocking better rewards and multipliers.
*   **The Shop**: A premium shop interface to spend PALDOGS on kits, announcer packs, and more.

### 🐾 Pal & Kit Management
*   **Pal Cage**: Advanced management for Pals. Import/Export Pal data and manage captures.
*   **Custom Kits**: Administrators can define complex item kits for players to claim or win.

### ⚙️ Interactive Configuration Hub
*   **Premium Hub**: Configure everything via a premium **Interactive Hub** using dropdowns and categories (`/config`).
*   **Dual Setup**: Use `/setup_channels` for lightning-fast channel binding without opening the full menu.

### ⚡ Advanced Server Controls
*   **Interactive Panel**: Use the `/server_controls` panel with premium buttons (Start, Restart, Shutdown).
*   **Smart Shutdowns**: Tries to save the world and shut down gracefully via REST API first; falls back to force-kill if the server is unresponsive.

### 🗨️ Cross-Chat Relay (Discord ↔️ Palworld)
*   **Bi-directional Chat**: Relay messages from Discord to in-game and vice versa.
*   **Premium Webhook Relay**: In-game chat is relayed to Discord via Webhooks, showing the actual player's name and avatar.

---

## 🛠️ Setup Instructions

1.  **Clone & Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

2.  **Authentication**:
    Add your bot token and admin ID to the `.env` file:
    ```env
    DISCORD_BOT_TOKEN=your_token_here
    GUILD_ID=your_server_id
    ADMIN_USER_ID=your_discord_id
    ```

3.  **Run the Bot**:
    Run `start_bot.bat` or use the command line:
    ```powershell
    python main.py
    ```

    *   **Background Running**: Use `start_background_bot.bat` to run the bot without a console window.
    *   **Quick Restart**: Use `restart_bot.bat` if the bot becomes unresponsive.

4.  **In-App Configuration**:
    Once the bot is online, use the slash commands:
    *   `/setup_channels`: Bind the bot to your Discord channels.
    *   `/config`: Open the full interactive configuration menu.

---

## ⌨️ Command Reference

### Player Commands
| Command | Description |
| :-- | :-- |
| `/palhelp` | Displays the help menu with all commands |
| `/profile` | View your stats, rank, and PALDOGS balance |
| `/shop` | Open the PALDOGS Exchange shop |
| `/balance` | Quickly check your PALDOGS balance |
| `/link` | Link your Discord account to your SteamID |
| `/players` | List online players (requires REST API) |
| `/serverinfo` | Show technical server info |

### Admin Commands
| Command | Description |
| :-- | :-- |
| `/config` | Open the **Interactive Configuration Hub** |
| `/setup_channels` | Quickly configure bot channels |
| `/server_controls` | Show the interactive control panel |
| `/giveaway create` | Start a new giveaway for items or Pals |
| `/kit` | Manage and create item kits |
| `/pal_cage` | Import, export, and manage Pal data |
| `/paldog_admin` | Manage shop prices and player progression |
| `/saveworld` | Manually trigger a world save |

---

## 📂 Documentation
Detailed guides are available in the `docs/` folder:
*   [Implementation Summary](docs/IMPLEMENTATION_COMPLETE.md)
*   [Kit System Guide](docs/KIT_SYSTEM_GUIDE.md)
*   [Live Stats Setup](docs/LIVE_STATS_README.md)
*   [Rewards Configuration](docs/REWARDS_SETUP_GUIDE.md)

---

## 🔒 Security & Reliability
*   **Single Instance Lock**: Built-in protection prevents multiple instances.
*   **Admin-Only Access**: Critical commands are locked behind Administrator permissions.
*   **Thread-Safe Config**: Configuration is handled through a thread-safe JSON manager.

---
*Created by Paltastic - Powering your Palworld experience.*
