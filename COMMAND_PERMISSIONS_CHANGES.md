# Command Permission Changes Summary

## Date: 2026-02-03

### Commands Restricted to Admin-Only Access

The following commands have been updated to require Administrator permissions. Standard users will no longer see or be able to use these commands:

1. **`/link [steam_id]`** - Link Discord account to SteamID
   - File: `cogs/player_features.py`
   - Added: `default_member_permissions=nextcord.Permissions(administrator=True)`

2. **`/shop`** - Open the shop
   - File: `cogs/player_features.py`
   - Added: `default_member_permissions=nextcord.Permissions(administrator=True)`

3. **`/gamble`** - Casino games (including `/gamble wheel`)
   - File: `cogs/gambling.py`
   - Added: `default_member_permissions=nextcord.Permissions(administrator=True)`

4. **`/chest`** - Chest system commands
   - File: `cogs/chest_mgmt.py`
   - Added: `default_member_permissions=nextcord.Permissions(administrator=True)`

5. **`/pal_cage`** - View custom Pal information (including `/pal_cage view`)
   - File: `cogs/pal_mgmt.py`
   - Added: `default_member_permissions=nextcord.Permissions(administrator=True)`

6. **`/kit`** - Kit commands (including `/kit view`)
   - File: `cogs/kit_mgmt.py`
   - Added: `default_member_permissions=nextcord.Permissions(administrator=True)`

---

## Commands Still Available to Standard Users

The following commands remain accessible to all users (no admin permission required):

1. **`/palhelp`** - Show all available commands
2. **`/profile [user]`** - View player stats, rank, and level
3. **`/balance`** - Check PALDOGS and experience
4. **`/give_paldogs [user] [amount]`** - Send PALDOGS to another player
5. **`/inventory`** - View and claim won items
6. **`/giveaway`** - View active giveaways
7. **`/players`** - See who's online on the server
8. **`/serverinfo`** - View server status and information
9. **`/nextrestart`** - Check time until next auto-restart

---

## Testing Instructions

To test the permission changes:

1. **Restart the bot** to reload the command permissions
2. **In Discord**, go to Server Settings → Integrations → Your Bot
3. Check that the restricted commands now show the "Administrator" permission requirement
4. Test with a non-admin account to verify they cannot see/use the restricted commands
5. Test with an admin account to verify all commands still work

---

## Notes

- Commands with `default_member_permissions=nextcord.Permissions(administrator=True)` will only be visible to users with the Administrator permission in Discord
- The bot will need to be restarted for these changes to take effect
- You can further customize permissions per-channel or per-role in Discord's Server Settings → Integrations
