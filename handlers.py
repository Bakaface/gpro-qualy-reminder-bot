import asyncio
import logging
import math
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from datetime import datetime
from gpro_calendar import race_calendar, get_races_closing_soon
from notifications import get_user_status, mark_quali_done

logger = logging.getLogger(__name__)
router = Router()

def format_race_beautiful(race_data):
    if not race_data: return "None"
    
    track = race_data.get('track', 'Unknown')
    hours_left = race_data.get('hours_left', 0)
    quali_close = race_data.get('quali_close', datetime.now())
    
    hours_display = math.floor(hours_left)
    deadline = quali_close.strftime("%d.%m %H:%M")
    
    return f"Qualification closes in {hours_display}h\n**({deadline})** - {track}"

def format_time_until_quali(quali_close):
    """Time remaining until quali deadline"""
    now = datetime.now()
    delta = quali_close - now
    
    total_hours = delta.total_seconds() / 3600
    if total_hours > 72:
        days = math.floor(total_hours / 24)
        return f"{days}d"
    elif total_hours > 36:
        return "Tomorrow"
    elif total_hours > 0:
        hours = math.floor(total_hours)
        return f"{hours}h"
    else:
        return ""

def format_full_calendar():
    """Fire next race + quali time remaining"""
    if not race_calendar:
        return "No races scheduled"
    
    now = datetime.now()
    race_list = []
    
    # Handle dict or list
    if isinstance(race_calendar, dict):
        race_list = list(race_calendar.values())
    else:
        race_list = race_calendar
    
    # Find next race (first with future quali)
    next_race_index = -1
    for i, race in enumerate(race_list):
        if isinstance(race, dict):
            quali_close = race.get('quali_close', now)
            if quali_close > now:
                next_race_index = i
                break
    
    text = ""
    for i, race in enumerate(race_list[:17], 1):
        if isinstance(race, dict):
            track = race.get('track', f'Race {i}')
            race_date = race.get('date', now)
            quali_close = race.get('quali_close', now)
            race_id = race.get('race_id', i)
            
            date_str = race_date.strftime("%a %d.%m")
            time_text = format_time_until_quali(quali_close)
            
            time_info = date_str
            if time_text:
                time_info += f" • {time_text}"
            
            # FIRE NEXT RACE
            if i - 1 == next_race_index:
                text += f"🔥 **#{race_id} {track}** - {time_info}\n"
            else:
                text += f"**#{race_id} {track}** - {time_info}\n"
        else:
            track = str(race)
            text += f"**{track}** - Date TBD\n"
    
    return text.rstrip()

@router.message(Command("start"))
async def cmd_start(message: Message):
    from notifications import get_user_status, users_data
    user_id = message.from_user.id
    
    # Check BEFORE adding
    was_new = user_id not in users_data
    get_user_status(user_id)
    
    if was_new:
        logger.info(f"🆕 NEW user {user_id} registered via /start")
    else:
        logger.debug(f"👤 Existing user {user_id} used /start")
    
    await message.answer("🏁 GPRO Bot LIVE!\n/status - Next race\n/calendar - Full season\n/notify - Test alert")

@router.message(Command("status"))
async def cmd_status(message: Message):
    status = get_user_status(message.from_user.id)
    races_soon = get_races_closing_soon()
    
    next_race = "No upcoming races"
    if races_soon:
        if isinstance(races_soon, dict) and races_soon:
            next_race = format_race_beautiful(list(races_soon.values())[0])
        elif isinstance(races_soon, list) and len(races_soon) > 0:
            next_race = format_race_beautiful(races_soon[0])
    
    status_text = ""
    if status.get('completed_quali'):
        race_num = status['completed_quali']
        status_text = f"✅ **Race {race_num} qualification done**\n*Next race notifications active*"
    else:
        status_text = "🔔 **Notifications active**"
    
    text = (
        f"🏁 **GPRO Status**\n\n"
        f"🎯 **Next race:**\n{next_race}\n\n"
        f"{status_text}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Reset notifications", callback_data="reset_all")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode='Markdown')

@router.message(Command("notify"))
async def cmd_notify(message: Message, bot):
    from notifications import send_quali_notification
    races_soon = get_races_closing_soon(48.1)
    if not races_soon:
        await message.answer("🔔 No upcoming races")
        return
    
    first_race_id = list(races_soon.keys())[0]
    first_race_data = races_soon[first_race_id]
    await send_quali_notification(bot, message.from_user.id, first_race_id, first_race_data)

@router.message(Command("calendar"))
async def cmd_calendar(message: Message):
    calendar_text = format_full_calendar()
    text = f"🏁 **Full Season**\n\n{calendar_text}"
    await message.answer(text, parse_mode='Markdown')

@router.message(Command("schedule"))
async def cmd_schedule(message: Message):
    await cmd_calendar(message)

@router.message(Command("update"))
async def cmd_update(message: Message):
    from config import ADMIN_USER_ID
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ Admin only")
        return
    
    from gpro_calendar import update_calendar_secret
    from notifications import users_data, reset_user_status
    
    await update_calendar_secret()
    
    reset_count = 0
    for user_id in list(users_data.keys()):
        reset_user_status(user_id)
        reset_count += 1
    
    await message.answer(
        f"✅ **Calendar**: {len(race_calendar)} races\n"
        f"🔄 **{reset_count} users** reset",
        parse_mode='Markdown'
    )

@router.message(Command("users"))
async def cmd_users(message: Message):
    from config import ADMIN_USER_ID
    print(f"USERS DEBUG - User: {message.from_user.id} ({type(message.from_user.id)}), Admin: {ADMIN_USER_ID} ({type(ADMIN_USER_ID)})")
    
    if message.from_user.id != ADMIN_USER_ID:
        print("USERS: Access denied")
        await message.answer("❌ Admin only")
        return
    
    print("USERS: Admin access granted")
    
    try:
        from notifications import users_data
        print(f"USERS: Loaded {len(users_data)} users from notifications")
        
        if not users_data:
            await message.answer("📊 **0 users** in database", parse_mode='Markdown')
            return
            
        text = f"📊 **{len(users_data)} users**:\n\n"
        for uid, status in users_data.items():
            quali = status.get("completed_quali", "None")
            # Use HTML to avoid Markdown backtick issues with user IDs
            text += f"• `<code>{uid}</code>`: Race {quali}\n"
        
        await message.answer(text, parse_mode='HTML')
        
    except Exception as e:
        print(f"USERS ERROR: {e}")
        await message.answer("❌ Error loading user data", parse_mode='Markdown')

@router.callback_query(F.data.startswith("done_"))
async def handle_quali_done(callback: CallbackQuery):
    race_id = int(callback.data.split("_")[1])
    mark_quali_done(callback.from_user.id, race_id)
    await callback.message.edit_text(callback.message.text + "\n\n✅ *Race marked done!*")
    await callback.answer("✅ Done!")

@router.callback_query(F.data == "reset_all")
async def reset_all(callback: CallbackQuery):
    from notifications import reset_user_status
    reset_user_status(callback.from_user.id)
    await callback.message.edit_text(callback.message.text + "\n\n🔄 *Notifications reset!*")
    await callback.answer("🔄 Reset!")

logger.info("✅ handlers.py loaded - Aiogram 3.x Router ready")
