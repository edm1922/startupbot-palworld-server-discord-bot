# 📊 Live Stats Display & Reward System

## Overview
The Live Stats Display automatically updates a Discord channel with real-time server statistics, player leaderboards, and activity metrics every 5 minutes.

---

## 🚀 Setup Instructions

### 1. **Configure Stats Channel**
Use the `/setup_channels` command to set the stats channel:

```
/setup_channels stats_channel:#your-stats-channel
```

The bot will:
- ✅ Create a live stats message in the channel
- ✅ Update it automatically every 5 minutes
- ✅ Show server activity and leaderboards

---

## 📊 What's Displayed

The live stats message shows:

### **Server Activity**
- 👥 Active players today
- 💰 DogCoin earned today
- 🏗️ Structures built today
- ⚒️ Items crafted today
- 📈 All-time totals

### **Top Players Leaderboard**
- 🥇 Top 5 players by DogCoin
- Shows player rank (Trainer/Gym Leader/Champion)
- Real-time updates

---

## 🎮 Reward System

### **How It Works**
The bot monitors PalDefender logs and automatically rewards players for:

#### **Building** 🏗️
- Wooden structures: 5 DogCoin
- Stone structures: 10 DogCoin
- Metal structures: 15 DogCoin

#### **Crafting** ⚒️
- Common items: 2 DogCoin
- Advanced items: 5-15 DogCoin
- Special items (Cake, Spheres): 10-15 DogCoin

#### **Technology Unlocks** 🎓
- Each tech unlock: 50 DogCoin

#### **Daily Login** 🎉
- Daily bonus: 25 DogCoin
- Login streak multiplier

#### **Playtime** ⏰
- Automatic tracking
- Hourly bonuses (future feature)

---

## 🏆 Rank System

### **Ranks**
1. **Trainer** 🎓 - Starting rank (1x multiplier)
2. **Gym Leader** ⭐ - Mid-tier rank (2x multiplier)
3. **Champion** 👑 - Top rank (3x multiplier)

### **Rank Benefits**
- Higher ranks earn MORE DogCoin for the same activities
- Example: A Champion earns 3x the DogCoin of a Trainer

### **Rank Progression**
Ranks are currently managed by admins using:
```
/addrank @player Gym Leader
/removerank @player
```

---

## 🔧 Admin Commands

### **Manage Ranks**
```
/addrank @player [rank]     - Assign rank to player
/removerank @player         - Remove player's rank
/listrank                   - Show all available ranks
```

### **View Stats**
```
/profile [@player]          - View player profile
/leaderboard [category]     - View leaderboards
/stats [type]               - View detailed statistics
```

---

## 📁 Database

Player data is stored in `player_stats.db` with:
- Player information (Steam ID, Discord ID, name)
- Activity stats (buildings, crafts, tech unlocks)
- Session tracking (login/logout times)
- Reward history
- Daily statistics

### **Backup Recommendation**
Regularly backup `player_stats.db` to prevent data loss.

---

## 🔄 How Rewards Are Calculated

```python
Base Reward × Rank Multiplier = Final Reward

Example:
- Activity: Build Metal Foundation
- Base Reward: 15 DogCoin
- Player Rank: Gym Leader (2x)
- Final Reward: 15 × 2 = 30 DogCoin
```

---

## ⚙️ Configuration

### **Enable/Disable Rewards**
Edit `bot_config.json`:
```json
{
    "rewards_enabled": true
}
```

### **Stats Update Interval**
Default: 300 seconds (5 minutes)

To change, edit `live_stats.py`:
```python
self.update_interval = 300  # Change this value
```

---

## 🐛 Troubleshooting

### **Stats not updating?**
1. Check if stats channel is configured: `/setup_channels`
2. Verify bot has permissions to send messages in the channel
3. Check console for error messages

### **Rewards not working?**
1. Ensure `rewards_enabled` is `true` in config
2. Verify log directory path is correct
3. Check PalDefender is running and generating logs

### **Database errors?**
1. Stop the bot
2. Delete `player_stats.db`
3. Restart the bot (database will be recreated)

---

## 📝 Future Features

- [ ] Player profile command (`/profile`)
- [ ] Leaderboard command (`/leaderboard`)
- [ ] Achievement system
- [ ] Reward vouchers for in-game items
- [ ] Weekly/monthly competitions
- [ ] Custom rank progression system
- [ ] Playtime-based rewards
- [ ] Chat activity rewards (anti-spam)

---

## 🎯 Example Stats Display

```
📊 PALWORLD SERVER STATISTICS
Live server statistics and leaderboards

🌟 Server Activity
👥 Active Players Today: 12
💰 DogCoin Earned Today: 45,892
🏗️ Structures Built Today: 2,341
⚒️ Items Crafted Today: 8,765

📈 All-Time Totals:
🏗️ Total Structures: 125,432
⚒️ Total Items Crafted: 456,789

🏆 Top Players (DogCoin)
🥇 👑 AMEN - 12,450 DogCoin
🥈 ⭐ King Ragnar - 8,920 DogCoin
🥉 🎓 Your Mom - 6,540 DogCoin
4️⃣ 🎓 Dinorado - 4,230 DogCoin
5️⃣ 🎓 98 - 3,100 DogCoin

Powered by Paltastic • Updates every 5 minutes
```

---

## 💡 Tips

1. **Create a dedicated #stats channel** for clean display
2. **Pin the stats message** for easy access
3. **Set channel to read-only** to prevent spam
4. **Use channel permissions** to control who sees stats
5. **Monitor database size** and backup regularly

---

**Created by Paltastic - Powering your Palworld experience.**
