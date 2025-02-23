# StartupBot - Palworld Server Discord Bot

🚀 A Nextcord-based Discord bot for managing a Palworld dedicated server remotely.

## Features
✅ Start and stop the Palworld server from Discord  
✅ Automatic server restarts with configurable intervals  
✅ Real-time system RAM monitoring  
✅ Customizable settings via `.env` file  

## Installation

### Prerequisites
- Python 3.8+
- A running Palworld dedicated server
- A Discord bot token from the Discord Developer Portal
- Required dependencies: `nextcord`, `psutil`, `dotenv`

### Setup
1. Clone the repository:
   ```sh
   git clone https://github.com/edm1922/startupbot-palworld-server-discord-bot.git  
   cd startupbot-palworld-server-discord-bot  
   ```  
2. Install dependencies:
   ```sh
   pip install -r requirements.txt  
   ```  
3. Create a `.env` file in the project root and configure your bot settings:
   ```ini
   DISCORD_BOT_TOKEN=your-bot-token  
   GUILD_ID=your-server-id  
   ALLOWED_CHANNEL_ID=channel-id-for-commands  
   STATUS_CHANNEL_ID=channel-id-for-status  
   RAM_USAGE_CHANNEL_ID=channel-id-for-ram-monitoring  
   RESTART_INTERVAL=10800  # Default restart interval in seconds (3 hours)
   ```  
4. Run the bot:
   ```sh
   python bot.py  
   ```  

## Commands  
| Command | Description |
|---------|-------------|
| `!startserver` | Start the Palworld server |
| `!stopserver` | Stop the server |
| `!restartserver` | Restart the server |
| `!setrestartinterval <hours>` | Set auto-restart interval (1-24 hours) |
| `!togglerestart on/off` | Enable/disable automatic restarts |
| `!bothelp` | Show available commands |

## Troubleshooting  
- **Bot not responding?** Ensure it's running and has permission to read/send messages.  
- **Server not starting?** Check the path to the batch/script file that starts your Palworld server.  
- **RAM monitoring not working?** Ensure `psutil` is installed correctly.  

## Contributing  
Feel free to submit issues or pull requests!  

## License  
MIT License  

