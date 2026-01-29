# 🎮 Instant Item Rewards System - Setup Guide

## ✅ What's Been Implemented

### 1. **RCON Utility** (`rcon_utility.py`)
- Connects to PalGuard/PalDefender RCON
- Sends commands to give items and experience to players
- Automatic error handling and retry logic

### 2. **Rank Progression System** (`rank_system.py`)
- **3 Ranks**: Trainer → Gym Leader → Champion
- **Automatic Rank-Ups** based on total DogCoin earned
- **Rank-Based Rewards** - higher ranks get better daily rewards

### 3. **Updated Rewards** (`log_parser.py`)
- Now gives **ACTUAL IN-GAME ITEMS** via RCON
- Rewards scale with player rank
- Automatic rank-up detection and notifications

### 4. **Enhanced Live Stats** (`live_stats.py`)
- Shows rank progression bars
- Displays progress to next rank
- Shows percentage and DogCoin needed

---

## 🏆 Rank System

### Rank Progression:
| Rank | DogCoin Required | Multiplier | Daily Rewards |
|------|------------------|------------|---------------|
| 🎓 **Trainer** | 0 - 999 | 1.0x | 10 Gold, 50 EXP |
| ⭐ **Gym Leader** | 1,000 - 4,999 | 2.0x | 25 Gold, 5 Pal Spheres, 150 EXP |
| 👑 **Champion** | 5,000+ | 3.0x | 50 Gold, 10 Pal Spheres, 2 Mega Spheres, 300 EXP |

### Streak Bonuses (Added to Daily Rewards):
| Streak | Bonus Items |
|--------|-------------|
| 3 days | +50 Gold, +100 EXP |
| 7 days | +150 Gold, +10 Pal Spheres, +250 EXP |
| 14 days | +500 Gold, +5 Mega Spheres, +500 EXP |
| 30 days | +1,500 Gold, +3 Giga Spheres, +1,000 EXP |

---

## ⚙️ RCON Configuration

### Step 1: Find Your PalGuard Config

1. Navigate to your Palworld server directory
2. Find PalGuard/PalDefender config file:
   - Usually in: `Pal/Binaries/Win64/Mods/PalGuard/PalGuard.cfg`
   - Or: `Pal/Binaries/Win64/Mods/PalDefender/PalDefender.cfg`

### Step 2: Enable RCON in PalGuard

Open the config file and look for RCON settings:

```ini
[RCON]
Enabled=true
Host=127.0.0.1
Port=25575
Password=your_rcon_password_here
```

**Important:**
- Set `Enabled=true`
- Note the `Port` (usually 25575)
- Set a strong `Password`
- If bot is on same PC as server, use `127.0.0.1` as host

### Step 3: Configure Bot

Add RCON settings to your `bot_config.json`:

```json
{
  "rcon_host": "127.0.0.1",
  "rcon_port": 25575,
  "rcon_password": "your_rcon_password_here",
  "rewards_enabled": true
}
```

**OR** use the `/edit` command:

```
/edit
  rcon_host: 127.0.0.1
  rcon_port: 25575
  rcon_password: your_password
```

---

## 🧪 Testing

### Test RCON Connection:

1. Restart your bot
2. Have a player log in
3. Check bot console for:
   ```
   ✅ RCON: Gave 10x Gold to steam_76561198...
   ✅ RCON: Gave 50 EXP to steam_76561198...
   ```

### If You See Errors:

**❌ RCON connection refused**
- PalGuard RCON is not enabled
- Check PalGuard config file

**❌ RCON authentication failed**
- Wrong password in bot config
- Check password matches PalGuard config

**❌ RCON timeout**
- Wrong host or port
- Firewall blocking connection
- PalGuard not running

---

## 📊 What Players Will See

### On Login (Trainer Rank, 1-day streak):
**Discord:**
```
🎉 🎓 PlayerName logged in! +25 DogCoin
🎁 Rewards: 10x Gold, 50 EXP
```

**In-Game:**
```
✨ PlayerName received daily rewards!
```

**Inventory:**
- +10 Gold (actually in inventory!)
- +50 EXP (actually gained!)

### On Rank Up (1,000 DogCoin reached):
**Discord:**
```
🎉 🎓 PlayerName logged in! +50 DogCoin
🎁 Rewards: 25x Gold, 5x PalSphere, 150 EXP

🎊 RANK UP! ⭐ You are now a Gym Leader!
✨ Reward multiplier increased to 2.0x!
```

### On 7-Day Streak (Gym Leader):
**Discord:**
```
🎉 ⭐ PlayerName logged in! +250 DogCoin
🎁 Rewards: 175x Gold, 15x PalSphere, 400 EXP
🔥 7-day streak!
🔥 7-DAY STREAK BONUS!
```

**Inventory:**
- +175 Gold (25 base + 150 bonus)
- +15 Pal Spheres (5 base + 10 bonus)
- +400 EXP (150 base + 250 bonus)

---

## 🎯 Live Stats Display

The live stats now show:

```
🏆 ═══ TOP PLAYERS ═══

🥇 👑 ChampionPlayer
    ████████ 8,500 DC
    👑 MAX RANK

🥈 ⭐ GymLeaderPlayer
    ██████░░ 3,200 DC
    ███░░░ 64% → 👑 Champion (5,000 DC)

🥉 🎓 TrainerPlayer
    ████░░░░ 750 DC
    ███░░░ 75% → ⭐ Gym Leader (1,000 DC)
```

---

## 🔧 Customizing Rewards

### Edit `rank_system.py` to change rewards:

```python
'Trainer': {
    'daily_reward_items': {
        'Gold': 10,  # Change amount here
        'Wood': 100,  # Add new items
    },
    'daily_reward_exp': 50  # Change EXP
},
```

### Available Item IDs:
Common items you can give:
- `Gold` - Gold coins
- `PalSphere` - Pal Sphere
- `MegaSphere` - Mega Sphere
- `GigaSphere` - Giga Sphere
- `Wood` - Wood
- `Stone` - Stone
- `Ore` - Ore
- `Coal` - Coal
- `IronIngot` - Iron Ingot
- `Cake` - Cake

**Note:** Item IDs must match exactly what PalGuard expects!

---

## 🚀 Next Steps

1. **Configure RCON** in PalGuard config
2. **Add RCON settings** to bot config
3. **Restart the bot**
4. **Test with a player login**
5. **Check Discord and in-game** for rewards

---

## ❓ Troubleshooting

**Q: Players get Discord notification but no items in-game?**
A: RCON is not configured or not working. Check console for RCON errors.

**Q: How do I change rank requirements?**
A: Edit `rank_system.py` - change `min_dogcoin` and `max_dogcoin` values.

**Q: Can I add more ranks?**
A: Yes! Edit `rank_system.py` and add new rank tiers.

**Q: Items not showing in inventory?**
A: Check item IDs match PalGuard's item database. Some mods change item names.

**Q: How do I manually test RCON?**
A: Use an RCON client tool to connect and test commands like:
```
give steam_76561198... Gold 100
```

---

**Your rewards system is now LIVE!** 🎉

Players will receive actual in-game items when they log in, and ranks will automatically progress based on their activity!
