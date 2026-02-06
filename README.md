# Paltastic - Palworld Server Discord Bot

A Discord bot for managing Palworld Dedicated Servers. Features include server management, economy system, giveaways, and live stats.

## Core Features

- **Lucky Wheel (Gambling)**: 🎰 Spin for guaranteed wins including Mysterious Pals and items. Features real-time **Public Activity Logs**.
- **Mystery Chest Room**: ✨ Explore and find Basic, Rare, Epic, or Legendary chests. Every opening is logged publicly in the "Recent Discoveries" feed.
- **Premium Skin Shop**: 🎨 Integrated skin system with an **Auto-Installer for Pals**. Manage and purchase custom `.pak` skins with PALDOGS.
- **Economy & Ranks**: Earn PALDOGS currency and progress through ranks (Trainer, Gym Leader, Champion).
- **Giveaway System**: Create giveaways for Kits or Pals. Winners can claim rewards when online.
- **Live Stats**: Automatic updates for server status, player counts, and system performance.
- **Smart Auto-Restart**: Configurable restart intervals with countdown announcements and a strict toggle system.
- **Server Controls**: Manage the server (Start, Restart, Shutdown) directly from Discord.
- **Cross-Chat Relay**: Bi-directional chat between Discord and Palworld.

## Command Reference

### Player Commands
| Command | Description |
| :--- | :--- |
| `/palhelp` | Show all available commands |
| `/link` | Link Discord to SteamID (**Required for rewards**) |
| `/profile` | View stats, rank, level, and active announcer |
| `/inventory` | View and claim your won items |
| `/balance` | Check PALDOGS and EXP balance |
| `/give_paldogs` | Transfer PALDOGS to another player |
| `/skinshop` | Browse and buy premium Pal skins |
| `/kit view` | Browse available item kits |
| `/players` | View currently online players |
| `/nextrestart` | Time until next scheduled auto-restart |

### Admin Commands
| Command | Description |
| :--- | :--- |
| `/config` | Open the main configuration dashboard |
| `/setup_channels` | Configure bot-specific channels |
| `/server_controls` | Open the server control panel |
| `/chest setup_ui` | Spawn the persistent Mystery Chest Room |
| `/gamble_admin` | Setup/Manage the Lucky Wheel and rewards |
| `/skin_admin` | Sync, add, and update skins in the shop |
| `/kit_admin` | Create, edit, and manually give kits to players |
| `/paldog_admin` | Manage economy and grant manual rewards |
| `/giveaway_admin`| Create and manage server giveaways |
| `/pal_admin` | Manage custom Pal data and bulk imports |
| `/saveworld` | Manually trigger world save |

## Structure & Organization

- **`cogs/`**: Modularized features (Gambling, Skins, Chets, Rank System, etc).
- **`data/`**: Configuration, databases, and assets.
  - **`palskins/`**: Centralized home for skin installer scripts and `.pak` templates.
- **`utils/`**: Core utilities for RCON, REST API, Database, and Server communication.

## Setup Instructions

1. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

2. **Configuration**:
   Update the `.env` file with your credentials:
   ```env
   DISCORD_BOT_TOKEN=your_token_here
   GUILD_ID=your_server_id
   ADMIN_USER_ID=your_discord_id
   ```

3. **Run the Bot**:
   ```powershell
   python main.py
   ```
   Or use the provided batch files: `start_bot.bat`, `restart_bot.bat`.

## Documentation
Additional guides are in the `docs/` folder:
- [Implementation Summary](docs/IMPLEMENTATION_COMPLETE.md)
- [Kit System Guide](docs/KIT_SYSTEM_GUIDE.md)
- [Live Stats Setup](docs/LIVE_STATS_README.md)
- [Rewards Configuration](docs/REWARDS_SETUP_GUIDE.md)
