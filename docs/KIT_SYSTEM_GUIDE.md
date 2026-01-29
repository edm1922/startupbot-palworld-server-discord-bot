# 🎁 Kit System Guide

The **Kit System** allows admins to create presets of items and give them to players instantly. This is perfect for starter packs, event rewards, or compensation.

## 🚀 Main Commands

All commands start with `/kit`.

### 1. Creating a Kit
Add items to a kit one by one. If the kit doesn't exist, it will be created automatically.

```
/kit add_item kit_name:Starter item_id:Gold amount:500
/kit add_item kit_name:Starter item_id:PalSphere amount:10
/kit add_item kit_name:Starter item_id:Bread amount:5
```

This creates a **"Starter"** kit with 500 Gold, 10 Spheres, and 5 Bread.

### 2. Giving a Kit
Give an entire kit to a player with one command.

```
/kit give player_name:AshKetchum kit_name:Starter
```

The player will receive ALL items in the kit instantly via RCON.

### 3. Viewing Kits
See what kits are available or check what's inside a specific kit.

```
/kit view                 # List all kits
/kit view kit_name:Starter # See contents of Starter kit
```

### 4. Managing Kits
Remove items or delete entire kits.

```
/kit remove_item kit_name:Starter item_id:Bread  # Remove Bread from kit
/kit delete kit_name:Starter                     # Delete the entire kit
```

---

## 📝 Example Kits

Here are some ideas for kits you can create:

### 🛡️ **Starter Kit**
- `Gold`: 500
- `PalSphere`: 10
- `BakedBerry`: 20
- `ClothOutfit`: 1

### 🏗️ **Builder Kit**
- `Wood`: 500
- `Stone`: 500
- `Fiber`: 200

### ⚔️ **Raid Box**
- `MegaSphere`: 20
- `AssaultRifle_Default`: 1
- `AssaultRifleBullet`: 200
- `Cake`: 5

---

## ⚠️ Important Notes

1. **RCON Required:** The kit system uses RCON to give items. Make sure RCON is configured!
2. **Exact Item IDs:** You must use the correct internal Item IDs (e.g. `PalSphere` not `pal sphere`).
3. **Player Must Be Known:** The target player must have logged into the server at least once so the bot knows their SteamID.

---

## 📂 Data Storage
Kits are saved in `kits.json` in your bot directory. You can manually edit this file if you prefer (but restarting the bot is recommended after manual edits).
