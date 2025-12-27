import asyncio
import logging
import json
import os
from typing import Dict
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from gpro_calendar import get_races_closing_soon, race_calendar
from datetime import datetime

logger = logging.getLogger(__name__)

users_data: Dict[int, Dict] = {}
USERS_FILE = 'users_data.json'
notification_lock = asyncio.Lock()  # CRITICAL: Prevents concurrent sends

def load_users_data():
    global users_data
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                raw_data = json.load(f)
                # TYPE FIX: Convert string keys → int keys
                clean_data = {int(k_str): status for k_str, status in raw_data.items()}
                users_data.update(clean_data)
                logger.info(f"✅ Loaded {len(users_data)} users (int keys)")
        except Exception as e:
            logger.error(f"Load failed: {e}")

def save_users_data():
    try:
        with open(USERS_FILE, 'w') as f:
            # TYPE FIX: Convert int keys → string for JSON
            save_data = {str(k): v for k, v in users_data.items()}
            json.dump(save_data, f, indent=2)
        logger.debug(f"Saved {len(users_data)} users")
    except Exception as e:
        logger.error(f"Save failed: {e}")

def get_user_status(user_id: int) -> Dict:
    global users_data
    logger.info(f"🔍 DEBUG get_user_status({user_id}): users_data.keys() = {list(users_data.keys())} (len={len(users_data)})")
    
    if not users_data:
        load_users_data()
        logger.info(f"🔍 AFTER load_users_data(): users_data.keys() = {list(users_data.keys())}")
    
    if user_id not in users_data:
        logger.warning(f"🚨 ADDING NEW user {user_id} - NOT FOUND in {list(users_data.keys())}")
        users_data[user_id] = {'completed_quali': None}
        save_users_data()
        logger.info(f"🆕 TRULY NEW user {user_id} added")
    else:
        logger.info(f"✅ User {user_id} EXISTS - no add")
    
    return users_data[user_id]

async def send_quali_notification(bot: Bot, user_id: int, race_id: int, race_data: Dict, notification_type: str = "deadline"):
    user_status = get_user_status(user_id)
    if user_status.get('completed_quali') == race_id:
        return

    track = race_data['track']
    race_date = race_data['date']
    quali_close = race_data['quali_close']

    if notification_type == "opens_soon":
        emoji = "🆕"
        title = "**Quali is open (or is opening soon)**"
        deadline = quali_close.strftime("%d.%m %H:%M UTC")
        race_time = race_date.strftime('%d.%m %H:%M UTC')
    else:
        # FIX: Calculate hours_left if missing (for /notify from race_calendar)
        now = datetime.utcnow()
        if 'hours_left' not in race_data:
            hours_left = (quali_close - now).total_seconds() / 3600
        else:
            hours_left = race_data['hours_left']
        
        if hours_left >= 24:
            time_text = f"{int(hours_left)}h"; emoji = "🔔"
        elif hours_left >= 2:
            time_text = f"{int(hours_left)}h"; emoji = "⏰"
        elif hours_left >= 0.333:
            time_text = "10min"; emoji = "⚠️"
        else:
            time_text = f"{int(hours_left*60)}min"; emoji = "🚨"

        deadline = quali_close.strftime("%d.%m %H:%M UTC")
        race_time = race_date.strftime('%d.%m %H:%M UTC')
        title = f"**Quali closes in {time_text}!**"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Quali Done", callback_data=f"done_{race_id}")]
    ])

    message = (
        f"{emoji} {title}\n\n"
        f"🏁 **Race #{race_id}**\n"
        f"📍 **{track}**\n"
        f"📅 **Quali: {deadline} | Race: {race_time}**\n\n"
        f"Click button to disable notifications for this race"
    )

    try:
        await bot.send_message(user_id, message, reply_markup=keyboard, parse_mode='Markdown')
        logger.info(f"✅ Sent {notification_type} to {user_id} for race {race_id}")
    except Exception as e:
        logger.error(f"Notify {user_id} failed: {e}")

async def check_notifications(bot: Bot):
    """NUCLEAR FIX: Lock + Single instance only"""
    global notification_lock
    logger.info("🔔 Notification checker started (SINGLE THREAD)")
    
    # Kill any existing loops
    tasks = [t for t in asyncio.all_tasks() if 'check_notifications' in str(t)]
    for task in tasks:
        task.cancel()
        logger.info("🛑 Killed duplicate notification task")
    
    notify_history: Dict[int, set] = {}
    last_alert_time: Dict[int, float] = {}
    load_users_data()
    
    while True:
        async with notification_lock:  # CRITICAL: Only ONE loop runs at a time
            try:
                logger.debug(f"Checking... ({len(users_data)} users)")
                
                # Get races closing soon AND full calendar for race times
                races_closing = get_races_closing_soon(48.1)
                current_time = asyncio.get_event_loop().time()
                now = datetime.utcnow()
                
                # NEW: Check QUALI OPENS notifications using full calendar
                for race_id, race_data in race_calendar.items():
                    if race_id in notify_history and "opens_soon" in notify_history[race_id]:
                        continue
                    
                    race_time = race_data['date']
                    time_since_race = (now - race_time).total_seconds() / 3600
                    
                    # Within 20min window of 2.5h after race
                    if 2.4 <= time_since_race <= 2.6:
                        if race_id not in notify_history:
                            notify_history[race_id] = set()
                        
                        if "opens_soon" not in notify_history[race_id]:
                            # SINGLE SEND ONLY
                            for user_id in list(users_data.keys()):
                                await send_quali_notification(bot, user_id, race_id, race_data, "opens_soon")
                            
                            notify_history[race_id].add("opens_soon")
                            last_alert_time[race_id] = current_time
                            logger.info(f"🆕 Sent 'quali is open' for race {race_id} ({time_since_race:.1f}h after race)")
                            break  # Only one opens notification per check
                
                # Existing CLOSING SOON notifications (unchanged)
                for race_id, race_data in races_closing.items():
                    hours_left = race_data['hours_left']
                    
                    # 30min cooldown
                    if race_id in last_alert_time and (current_time - last_alert_time[race_id]) < 1800:
                        continue
                    
                    notify_windows = [
                        (48, 0.1, "48h"), (24, 0.1, "24h"), 
                        (2, 0.08, "2h"), (0.1667, 0.03, "10min")
                    ]
                    
                    for target_h, window, label in notify_windows:
                        if abs(hours_left - target_h) <= window:
                            if race_id not in notify_history or label not in notify_history[race_id]:
                                # SINGLE SEND ONLY
                                for user_id in list(users_data.keys()):
                                    await send_quali_notification(bot, user_id, race_id, race_data)
                                
                                notify_history.setdefault(race_id, set()).add(label)
                                last_alert_time[race_id] = current_time
                                logger.info(f"🎯 EXACT: Sent {label} for race {race_id} ({hours_left:.2f}h)")
                                break
                
                # Cleanup old history
                active_race_ids = set(races_closing.keys()) | set(race_calendar.keys())
                notify_history = {k: v for k, v in notify_history.items() if k in active_race_ids}
                last_alert_time = {k: v for k, v in last_alert_time.items() if k in active_race_ids}
                
            except Exception as e:
                logger.error(f"Loop error: {e}")
        
        await asyncio.sleep(300)

def mark_quali_done(user_id: int, race_id: int):
    get_user_status(user_id)
    users_data[user_id]['completed_quali'] = race_id
    save_users_data()
    logger.info(f"User {user_id} marked race {race_id} done")

def reset_user_status(user_id: int):
    if user_id in users_data:
        users_data[user_id]['completed_quali'] = None
        save_users_data()
        logger.info(f"User {user_id} reset")

load_users_data()
