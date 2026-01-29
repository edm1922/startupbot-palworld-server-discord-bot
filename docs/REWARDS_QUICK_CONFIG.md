# ⚡ Rewards Configuration - Quick Reference Card

## 🎯 3-Step Setup

### 1️⃣ PalGuard Config
**File:** `PalGuard.cfg` (in your server's mod folder)
```ini
[RCON]
Enabled=true
Host=127.0.0.1
Port=25575
Password=YourPassword123
```

### 2️⃣ Bot Config
**File:** `bot_config.json`
```json
{
  "rcon_host": "127.0.0.1",
  "rcon_port": 25575,
  "rcon_password": "YourPassword123",
  "rewards_enabled": true
}
```

### 3️⃣ Restart
- Restart Palworld server
- Restart bot
- Test with player login!

---

## 🎁 Customize Rewards

**File:** `rank_system.py`

### Change Items:
```python
'daily_reward_items': {
    'Gold': 50,      # Change amounts
    'PalSphere': 10,
    'Wood': 100,     # Add new items
},
```

### Change Ranks:
```python
'Gym Leader': {
    'min_dogcoin': 1000,  # Change requirement
    ...
},
```

### Change Streaks:
```python
self.streak_bonuses = {
    3: {'Gold': 50, 'exp': 100},   # 3-day bonus
    7: {'Gold': 150, 'exp': 250},  # 7-day bonus
}
```

---

## 📦 Common Item IDs

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

---

## ✅ Testing

**Check bot console for:**
```
✅ RCON: Gave 10x Gold to steam_...
✅ RCON: Gave 50 EXP to steam_...
```

**If you see errors:**
- ❌ Connection refused → Enable RCON in PalGuard
- ❌ Auth failed → Check password matches
- ❌ Timeout → Check host/port

---

## 📝 Current Default Rewards

| Rank | DogCoin | Daily Items |
|------|---------|-------------|
| 🎓 Trainer | 0-999 | 10 Gold, 50 EXP |
| ⭐ Gym Leader | 1K-5K | 25 Gold, 5 Spheres, 150 EXP |
| 👑 Champion | 5K+ | 50 Gold, 10 Spheres, 2 Mega, 300 EXP |

**Streak Bonuses:**
- Day 3: +50 Gold, +100 EXP
- Day 7: +150 Gold, +10 Spheres, +250 EXP
- Day 14: +500 Gold, +5 Mega, +500 EXP
- Day 30: +1,500 Gold, +3 Giga, +1,000 EXP

---

**Full guide: `HOW_TO_CONFIGURE_REWARDS.md`**
