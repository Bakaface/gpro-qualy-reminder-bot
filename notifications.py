import asyncio
import logging
import json
import os
from typing import Dict
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from gpro_calendar import get_races_closing_soon, race_calendar
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

users_data: Dict[int, Dict] = {}
USERS_FILE = 'users_data.json'

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
        # SHOW STATUS for manual /notify, but skip automatic notifications
        if notification_type != "manual":
            return  # Skip automatic notifications
        
        # SPECIAL "DONE" message for manual /notify
        track = race_data['track']
        message = (
            f"✅ **Race {race_id} - QUALI DONE**\n\n"
            f"📍 **{track}**\n"
            f"⏰ Notifications **disabled** for this race\n\n"
            f"Use /reset to re-enable"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Reset Status", callback_data=f"reset_{race_id}")]
        ])
        
        try:
            await bot.send_message(user_id, message, reply_markup=keyboard, parse_mode='Markdown')
            logger.info(f"ℹ️ Sent DONE status to {user_id} for race {race_id}")
        except Exception as e:
            logger.error(f"Status notify failed: {e}")
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
    logger.info("🔔 Pre-calculating notifications")
    load_users_data()
    
    now = datetime.utcnow()
    scheduled_sends = []
    
    # 1. CLOSING SOON notifications (before quali_close)
    races_closing = get_races_closing_soon(72)
    for race_id, race_data in races_closing.items():
        quali_close = race_data['quali_close']
        
        send_times = [
            (quali_close - timedelta(hours=48), "48h"),
            (quali_close - timedelta(hours=24), "24h"), 
            (quali_close - timedelta(hours=2), "2h"),
            (quali_close - timedelta(minutes=10), "10min")
        ]
        
        for send_time, label in send_times:
            if send_time > now:
                delay = (send_time - now).total_seconds()
                scheduled_sends.append((delay, race_id, race_data, label))
    
    # 2. NEXT RACE quali opens 2.5h after CURRENT race finishes
    if races_closing:
        current_race_id = min(races_closing.keys())
        if current_race_id + 1 in race_calendar:
            next_race_data = race_calendar[current_race_id + 1]
            current_race_finish = races_closing[current_race_id]['date']
            opens_time = current_race_finish + timedelta(hours=2.5)
            
            if opens_time > now:
                delay = (opens_time - now).total_seconds()
                scheduled_sends.append((delay, current_race_id + 1, next_race_data, "opens_soon"))
    
    # Sort by soonest first
    scheduled_sends.sort(key=lambda x: x[0])
    
    logger.info(f"📅 Scheduled {len(scheduled_sends)} notifications")
    for delay, race_id, _, label in scheduled_sends[:5]:
        logger.info(f"  → Race {race_id} {label} in {delay/3600:.1f}h")
    
    # Execute in sequence
    for delay, race_id, race_data, label in scheduled_sends:
        await asyncio.sleep(delay)
        for user_id in list(users_data.keys()):
            await send_quali_notification(bot, user_id, race_id, race_data, label)
        logger.info(f"🎯 Sent {label} for race {race_id}")

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
