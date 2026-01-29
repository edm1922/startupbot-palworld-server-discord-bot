# 🎁 Daily Login Rewards System

## Overview
Players automatically earn **PalMarks** rewards every time they log into the server! The longer their login streak, the bigger the bonus!

---

## 💰 Base Daily Login Reward

**Every login:** 25 PalMarks (base)
- Multiplied by player rank (Trainer 1x, Gym Leader 2x, Champion 3x)

---

## 🔥 Streak Bonuses

Keep your login streak alive to earn massive bonuses!

| Streak Days | Bonus | Total Reward* | Message |
|-------------|-------|---------------|---------|
| 1 day | 0 | 25 PM | 🎉 Daily login! |
| 2 days | 0 | 25 PM | 🎉 2-day streak! |
| **3 days** | **+50 PM** | **75 PM** | ⭐ 3-DAY STREAK BONUS! |
| 4-6 days | +50 PM | 75 PM | ⭐ Streak continues! |
| **7 days** | **+100 PM** | **125 PM** | 🔥 7-DAY STREAK BONUS! |
| 8-13 days | +100 PM | 125 PM | 🔥 Week+ streak! |
| **14 days** | **+250 PM** | **275 PM** | 🎉 14-DAY STREAK BONUS! |
| 15-29 days | +250 PM | 275 PM | 🎉 2-week+ streak! |
| **30+ days** | **+500 PM** | **525 PM** | 🎊 30-DAY STREAK BONUS! |

*Base amounts before rank multiplier

---

## 👑 Rank Multipliers

Your rank multiplies ALL rewards, including streak bonuses!

### Example: 30-Day Streak

| Rank | Calculation | Total Reward |
|------|-------------|--------------|
| **Trainer** (1x) | (25 + 500) × 1 | **525 PalMarks** |
| **Gym Leader** (2x) | (25 + 500) × 2 | **1,050 PalMarks** |
| **Champion** (3x) | (25 + 500) × 3 | **1,575 PalMarks** |

---

## 📢 Notifications

### In Discord
When you log in, the bot posts in the chat channel:
```
🎉 **AMEN** logged in! +75 PalMarks (🔥 3-day streak!)
⭐ 3-DAY STREAK BONUS! +50 bonus!
```

### In-Game
You'll see a broadcast message:
```
✨ AMEN earned 75 PalMarks!
```

---

## ⚠️ Streak Rules

### ✅ Streak Continues When:
- You log in at least once every 24 hours
- You log in on consecutive days

### ❌ Streak Breaks When:
- You miss a full day (24+ hours since last login)
- You don't log in for an entire calendar day

### 📅 Streak Calculation:
- Based on **calendar days**, not 24-hour periods
- Login at 11:59 PM, then 12:01 AM = 2-day streak!
- Login Monday, skip Tuesday, login Wednesday = streak resets to 1

---

## 🎯 Maximizing Your Rewards

### Daily Strategy:
1. **Log in every day** - Even for 1 minute!
2. **Maintain your streak** - Set a reminder
3. **Rank up** - Higher ranks = bigger rewards
4. **Aim for milestones** - 3, 7, 14, 30 days

### Monthly Potential:
If you log in every day for 30 days:

| Rank | Total from Logins |
|------|-------------------|
| Trainer | ~6,000 PalMarks |
| Gym Leader | ~12,000 PalMarks |
| Champion | ~18,000 PalMarks |

*Plus all the PalMarks from building, crafting, and tech unlocks!*

---

## 📊 Tracking Your Streak

### Check Your Streak:
```
/profile
```

Shows:
- Current login streak
- Total PalMarks earned
- Last login date
- Next milestone

---

## 🏆 Streak Leaderboard

The live stats display shows:
- Top players by total PalMarks
- Most active players
- Longest current streaks (coming soon!)

---

## 💡 Pro Tips

1. **Set a Daily Reminder** - Don't break your streak!
2. **Log in before server restart** - Counts as that day
3. **Check /nextrestart** - Plan your login
4. **Coordinate with friends** - Compete for longest streak
5. **Rank up early** - Multiplier applies to ALL past logins

---

## 🔧 Admin Configuration

### Enable/Disable Login Rewards:
Edit `bot_config.json`:
```json
{
    "rewards_enabled": true
}
```

### Adjust Base Reward:
Edit `log_parser.py`:
```python
self.rewards = {
    'daily_login': 25  # Change this value
}
```

### Adjust Streak Bonuses:
Edit `log_parser.py` in the `process_activity` function:
```python
if streak >= 30:
    streak_bonus = 500  # Adjust bonuses here
elif streak >= 14:
    streak_bonus = 250
# etc...
```

---

## 🎊 Special Events (Future)

Coming soon:
- **Double Login Days** - 2x rewards on weekends
- **Streak Recovery** - One free "miss" per month
- **Streak Milestones** - Achievements at 50, 100, 365 days
- **Seasonal Bonuses** - Extra rewards during events

---

## 📈 Example Progression

### Week 1:
```
Day 1: 25 PM (Trainer)
Day 2: 25 PM
Day 3: 75 PM (3-day bonus!)
Day 4: 75 PM
Day 5: 75 PM
Day 6: 75 PM
Day 7: 125 PM (7-day bonus!)
Total: 475 PM
```

### Week 2 (After ranking up to Gym Leader):
```
Day 8: 250 PM (125 × 2)
Day 9: 250 PM
Day 10: 250 PM
Day 11: 250 PM
Day 12: 250 PM
Day 13: 250 PM
Day 14: 550 PM (14-day bonus!)
Total: 2,050 PM
```

---

## ❓ FAQ

**Q: What happens if I log in multiple times per day?**
A: You only get the reward once per day.

**Q: Does my streak reset if the server restarts?**
A: No! Streaks are tracked in the database.

**Q: Can I see other players' streaks?**
A: Use `/leaderboard streaks` (coming soon!)

**Q: What if I'm on vacation?**
A: Your streak will break, but you can start a new one when you return!

**Q: Do admin logins count?**
A: Yes! Everyone gets login rewards.

---

**Keep that streak alive and watch your PalMarks grow! 🚀**

*Powered by Paltastic*
