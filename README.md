# Paltastic - Palworld Server Discord Bot

A Discord bot for managing Palworld Dedicated Servers. Features include server management, economy system, giveaways, and live stats.

## Core Features

- **Gambling System**: Play Casino games like Roulette and Blackjack to win PALDOGS and items.
- **Giveaway System**: Create giveaways for Kits or Pals. Winners can claim rewards when online.
- **Economy & Ranks**: Earn PALDOGS currency and progress through ranks (Trainer, Gym Leader, Champion).
- **Live Stats**: Automatic updates for server status, player counts, and system performance.
- **Server Controls**: Manage the server (Start, Restart, Shutdown) directly from Discord.
- **Cross-Chat Relay**: Bi-directional chat between Discord and Palworld.
- **Pal & Kit Management**: Import/Export Pal data and manage custom item kits.
- **Configuration Hub**: Easy setup using `/config` and `/setup_channels`.

## Command Reference

### Player Commands
| Command | Description |
| :--- | :--- |
| `/palhelp` | Show all available commands |
| `/profile` | View stats, rank, and balance |
| `/gamble` | Access Casino games (Roulette, Blackjack) |
| `/shop` | Access the PALDOGS Exchange shop |
| `/balance` | Check PALDOGS balance |
| `/link` | Link Discord to SteamID |
| `/players` | View online players |
| `/inventory` | View and claim your won items |
| `/serverinfo` | Show server technical info |

### Admin Commands
| Command | Description |
| :--- | :--- |
| `/config` | Open the configuration hub |
| `/setup_channels` | Configure bot channels |
| `/server_controls` | Open the server control panel |
| `/gamble setup_roulette` | Initialize the Roulette table |
| `/gamble setup_blackjack` | Initialize the Blackjack UI |
| `/giveaway create` | Create a new giveaway |
| `/kit` | Manage item kits |
| `/pal_cage` | Manage Pal data |
| `/paldog_admin` | Manage economy and progression |
| `/saveworld` | Manually trigger world save |

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
   Or use the provided batch files: `start_bot.bat`, `start_background_bot.bat`.

## Documentation
Additional guides are in the `docs/` folder:
- [Implementation Summary](docs/IMPLEMENTATION_COMPLETE.md)
- [Kit System Guide](docs/KIT_SYSTEM_GUIDE.md)
- [Live Stats Setup](docs/LIVE_STATS_README.md)
- [Rewards Configuration](docs/REWARDS_SETUP_GUIDE.md)
