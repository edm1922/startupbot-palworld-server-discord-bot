import nextcord
from nextcord.ext import commands
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Configure logging to both file and console"""
    if not os.path.exists('logs'):
        os.makedirs('logs')

    log_filename = f"bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    log_path = os.path.join('logs', log_filename)

    # File Handler
    file_handler = RotatingFileHandler(
        filename=log_path, 
        maxBytes=10*1024*1024, # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(file_formatter)

    # Configure Root Logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

async def handle_interaction_error(interaction: nextcord.Interaction, error: Exception):
    """Global error handler for interactions"""
    logging.error(f"Error in interaction {interaction.data.get('name', 'unknown')}: {error}", exc_info=True)
    
    msg = "❌ An unexpected error occurred."
    
    if isinstance(error, nextcord.Forbidden):
        msg = "❌ I don't have permission to do that."
    elif isinstance(error, commands.MissingPermissions):
        msg = "❌ You don't have permission to use this command."
    elif isinstance(error, commands.CommandOnCooldown):
        msg = f"⏳ This command is on cooldown. Try again in {error.retry_after:.1f}s."
    
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass
