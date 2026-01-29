# 🧪 How to Test RCON and Item Giving

I've added a **debug command** to help you verify that RCON is working and that you can give items to players.

## 1. Prerequisites
- The bot must be running.
- The server (with PalGuard) must be running.
- **RCON must be configured** in both `PalGuard.cfg` and `bot_config.json`.
- The target player **must have logged in at least once** (so the bot knows their Steam ID).

## 2. Using the Command

In any Discord channel the bot can see, type:

```
/test_give_item
```

It will ask for 3 things:
1. **player_name**: The exact in-game name of the player (e.g., `AshKetchum`).
2. **item_id**: The internal ID of the item (e.g., `Gold`, `PalSphere`, `Wood`).
3. **amount**: How many to give (default is 1).

### Example:
```
/test_give_item player_name:AshKetchum item_id:Gold amount:100
```

## 3. What Happens?

1. The bot looks up `AshKetchum` in its database to find their Steam ID (e.g., `steam_76561198...`).
2. It sends an RCON command: `give steam_76561198... Gold 100` to the server.
3. The server (PalGuard) processes the command.
4. **Discord Output:**
   - ✅ **Success:** Embed confirmation. Requires an explicit success response from the server.
   - ❌ **Failed:** Server didn't respond or returned an error.

## 4. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| **Player not found in database** | Typo or player hasn't logged in since bot started tracking. | Check spelling exactly. Have player log in again. |
| **Command Failed (Red Embed)** | RCON connection issue. | Check `bot_config.json` password/port. Ensure server firewall allows port 25575. |
| **Success but no item?** | Wrong Item ID. | Use exact IDs like `Gold` (Capital G), not `gold`. |

## 5. View Logs

Check the bot's console window for detailed logs:
```
🧪 Testing RCON: Giving 100x Gold to AshKetchum (steam_7656...)...
✅ RCON: Gave 100x Gold to steam_7656...
```
