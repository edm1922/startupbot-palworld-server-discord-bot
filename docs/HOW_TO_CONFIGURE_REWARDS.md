# 🎮 How to Configure Rewards - Simple Guide

## 🚀 Quick Start (3 Steps)

### Step 1: Find Your PalGuard Config File

**Location:** Your Palworld server folder
- Navigate to: `Pal/Binaries/Win64/Mods/PalGuard/`
- Look for: `PalGuard.cfg` or `PalDefender.cfg`

**Can't find it?**
- Check if PalGuard/PalDefender is installed
- Look in your server's mod folder
- Common path: `C:\PalworldServer\Pal\Binaries\Win64\Mods\PalGuard\`

---

### Step 2: Enable RCON in PalGuard

Open `PalGuard.cfg` in a text editor and find the RCON section:

```ini
[RCON]
Enabled=true
Host=127.0.0.1
Port=25575
Password=MySecurePassword123
```

**Change these:**
- `Enabled=true` - Must be true!
- `Password=MySecurePassword123` - Set your own password (remember it!)
- `Port=25575` - Usually 25575, but you can change it
- `Host=127.0.0.1` - Use this if bot is on same PC as server

**Save the file and restart your Palworld server!**

---

### Step 3: Configure the Bot

**Option A: Edit bot_config.json**

Open `bot_config.json` and add these lines:

```json
{
  "rcon_host": "127.0.0.1",
  "rcon_port": 25575,
  "rcon_password": "MySecurePassword123",
  "rewards_enabled": true
}
```

**Make sure:**
- Password matches what you set in PalGuard.cfg
- Port matches PalGuard.cfg
- Use `127.0.0.1` if bot and server are on same PC

**Option B: Use Discord Command**

In Discord, type:
```
/edit
  rcon_host: 127.0.0.1
  rcon_port: 25575
  rcon_password: MySecurePassword123
```

**Then restart your bot!**

---

## ✅ Test If It's Working

1. **Restart your bot** (close and run `startupbot.py` again)
2. **Have a player log into the server**
3. **Check the bot console** - you should see:
   ```
   ✅ RCON: Gave 10x Gold to steam_76561198...
   ✅ RCON: Gave 50 EXP to steam_76561198...
   ```
4. **Check Discord** - you should see a reward notification
5. **Check in-game** - player should have Gold in inventory!

---

## 🎁 Customizing Rewards

### Change What Items Players Get

**File to edit:** `rank_system.py`

**Find this section:**

```python
'Trainer': {
    'daily_reward_items': {
        'Gold': 10,  # ← Change this number
        'PalSphere': 5,  # ← Add or remove items
    },
    'daily_reward_exp': 50  # ← Change EXP amount
},
```

**Example - Give more items:**

```python
'Trainer': {
    'daily_reward_items': {
        'Gold': 50,        # Increased from 10
        'PalSphere': 10,   # Added Pal Spheres
        'Wood': 100,       # Added Wood
        'Stone': 50,       # Added Stone
    },
    'daily_reward_exp': 100  # Increased from 50
},
```

**Save and restart the bot!**

---

### Change Rank Requirements

**File to edit:** `rank_system.py`

**Find this section:**

```python
'Gym Leader': {
    'min_dogcoin': 1000,  # ← Need 1,000 DC to become Gym Leader
    'max_dogcoin': 4999,
    ...
},
```

**Example - Make ranks easier to get:**

```python
'Gym Leader': {
    'min_dogcoin': 500,   # Changed from 1000
    'max_dogcoin': 2499,
    ...
},
'Champion': {
    'min_dogcoin': 2500,  # Changed from 5000
    'max_dogcoin': 999999,
    ...
},
```

**Save and restart the bot!**

---

### Change Streak Bonuses

**File to edit:** `rank_system.py`

**Find this section:**

```python
self.streak_bonuses = {
    3: {'Gold': 50, 'exp': 100},
    7: {'Gold': 150, 'PalSphere': 10, 'exp': 250},
    14: {'Gold': 500, 'MegaSphere': 5, 'exp': 500},
    30: {'Gold': 1500, 'GigaSphere': 3, 'exp': 1000}
}
```

**Example - Increase bonuses:**

```python
self.streak_bonuses = {
    3: {'Gold': 100, 'exp': 200},           # Doubled
    7: {'Gold': 300, 'PalSphere': 20, 'exp': 500},
    14: {'Gold': 1000, 'MegaSphere': 10, 'exp': 1000},
    30: {'Gold': 3000, 'GigaSphere': 10, 'exp': 2000}
}
```

**Save and restart the bot!**

---

## 📋 Available Item IDs

Common items you can give (must match PalGuard's item names):

### Currency & Spheres:
- `Gold` - Gold coins
- `PalSphere` - Pal Sphere
- `MegaSphere` - Mega Sphere
- `GigaSphere` - Giga Sphere
- `UltraSphere` - Ultra Sphere

### Resources:
- `Wood` - Wood
- `Stone` - Stone
- `Ore` - Ore
- `Coal` - Coal
- `Sulfur` - Sulfur
- `Fiber` - Fiber

### Ingots:
- `IronIngot` - Iron Ingot
- `CopperIngot` - Copper Ingot
- `SteelIngot` - Steel Ingot

### Special Items:
- `Cake` - Cake
- `HighQualityPalOil` - High Quality Pal Oil
- `Gunpowder` - Gunpowder
- `Cement` - Cement

**Note:** Item names are case-sensitive and must match exactly!

---

## 🔧 Common Configurations

### Configuration 1: Generous Rewards
```python
'Trainer': {
    'daily_reward_items': {
        'Gold': 100,
        'PalSphere': 20,
        'Wood': 200,
        'Stone': 100,
    },
    'daily_reward_exp': 200
},
```

### Configuration 2: Minimal Rewards
```python
'Trainer': {
    'daily_reward_items': {
        'Gold': 5,
    },
    'daily_reward_exp': 25
},
```

### Configuration 3: Resource Focus
```python
'Trainer': {
    'daily_reward_items': {
        'Wood': 500,
        'Stone': 300,
        'Ore': 100,
        'Fiber': 200,
    },
    'daily_reward_exp': 50
},
```

---

## ❓ Troubleshooting

### ❌ "RCON connection refused"
**Fix:**
1. Check if PalGuard is installed
2. Check if `Enabled=true` in PalGuard.cfg
3. Restart Palworld server after changing config
4. Make sure port is not blocked by firewall

### ❌ "RCON authentication failed"
**Fix:**
1. Password in bot_config.json must match PalGuard.cfg exactly
2. Check for typos
3. No spaces before/after password

### ❌ Players get notification but no items
**Fix:**
1. Check bot console for RCON errors
2. Verify RCON is configured (see above)
3. Make sure item IDs are correct (case-sensitive!)
4. Try giving items manually via RCON to test

### ❌ Wrong items given
**Fix:**
1. Item IDs must match PalGuard's item database
2. Check spelling and capitalization
3. Some mods change item names
4. Test with simple items like `Gold` first

---

## 📝 Quick Reference

### Files You Might Edit:
- **`bot_config.json`** - RCON connection settings
- **`rank_system.py`** - Rewards, ranks, and bonuses
- **`log_parser.py`** - Base DogCoin values (advanced)

### After Making Changes:
1. Save the file
2. Restart the bot
3. Test with a player login

### Testing RCON:
Use an RCON client or command:
```
give steam_76561198012345678 Gold 100
```

---

## 🎯 Recommended Starting Configuration

**For a new server:**

```python
# In rank_system.py

'Trainer': {
    'min_dogcoin': 0,
    'max_dogcoin': 999,
    'daily_reward_items': {
        'Gold': 25,
        'PalSphere': 5,
    },
    'daily_reward_exp': 100
},

'Gym Leader': {
    'min_dogcoin': 1000,
    'max_dogcoin': 4999,
    'daily_reward_items': {
        'Gold': 50,
        'PalSphere': 10,
        'MegaSphere': 2,
    },
    'daily_reward_exp': 250
},

'Champion': {
    'min_dogcoin': 5000,
    'max_dogcoin': 999999,
    'daily_reward_items': {
        'Gold': 100,
        'PalSphere': 20,
        'MegaSphere': 5,
        'GigaSphere': 1,
    },
    'daily_reward_exp': 500
},
```

**This gives:**
- Balanced progression
- Meaningful rewards
- Incentive to log in daily
- Exciting rank-ups

---

## 💡 Pro Tips

1. **Start conservative** - You can always increase rewards later
2. **Test first** - Try with one player before announcing
3. **Monitor economy** - Make sure rewards don't break game balance
4. **Adjust based on feedback** - Ask players what they think
5. **Backup configs** - Save a copy before making big changes

---

**Need more help? Check `REWARDS_SETUP_GUIDE.md` for detailed info!** 🚀
