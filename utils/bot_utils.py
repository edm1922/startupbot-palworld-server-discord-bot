import os
import importlib.util
import logging
import socket
import sys

import importlib
from nextcord.ext import commands


def load_cogs(bot):
    """Recursively load all cogs from the cogs directory if they have a setup() function"""
    if not os.path.exists("cogs"):
        logging.warning("No 'cogs' directory found.")
        return

    for root, dirs, files in os.walk("cogs"):
        for filename in files:
            if filename.endswith(".py") and not filename.startswith("__"):
                # Construct module path relative to workspace root
                rel_path = os.path.relpath(os.path.join(root, filename), os.getcwd())
                module_name = rel_path.replace(os.sep, ".")[:-3]
                
                try:
                    # Try to load it. If it doesn't have setup(), nextcord will raise a NoEntryPointError
                    # which we can quietly ignore as it's likely a utility module.
                    bot.load_extension(module_name)
                    logging.info(f"✅ Loaded extension: {module_name}")
                except commands.errors.NoEntryPointError:
                    # This module doesn't have a setup() function, it's just a helper file.
                    pass
                except commands.errors.ExtensionAlreadyLoaded:
                    # Already loaded via main.py or another cog
                    pass
                except Exception as e:
                    logging.error(f"❌ Failed to load extension {module_name}: {e}")

# Global variable to hold the socket object
instance_lock = None

def enforce_single_instance(port=65432):
    """Ensure only one instance of the bot is running by binding to a dedicated port."""
    global instance_lock
    try:
        instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Bind to localhost on a specific port
        instance_lock.bind(('127.0.0.1', port))
    except socket.error:
        print("\n" + "!" * 50)
        print("CRITICAL ERROR: ANOTHER INSTANCE IS ALREADY RUNNING!")
        print("Please close any existing bot windows before starting a new one.")
        print("!" * 50 + "\n")
        sys.exit(1)
