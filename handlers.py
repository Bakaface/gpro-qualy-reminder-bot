import logging
import math
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from gpro_calendar import race_calendar, next_season_calendar, get_races_closing_soon, update_calendar, load_next_season_silent
from notifications import get_user_status, mark_quali_done, reset_user_status, set_user_group, toggle_notification, is_notification_enabled, users_data, save_users_data, send_quali_notification, LANGUAGE_OPTIONS, set_user_language, get_user_language
from config import ADMIN_USER_IDS

logger = logging.getLogger(__name__)
router = Router()

# Notification type labels - used across multiple commands
NOTIFICATION_LABELS = {
    '48h': '48h before quali closes',
    '24h': '24h before quali closes',
    '2h': '2h before quali closes',
    '10min': '10min before quali closes',
    'opens_soon': 'Quali is open',
    'race_replay': 'Race replay available',
    'race_live': 'Race is live'
}

class SetGroupStates(StatesGroup):
    waiting_for_group = State()


def format_full_calendar(calendar_data, title="Full Season", is_current_season=True):
    """Generic formatter for current/next season"""
    if not calendar_data:
        return "No races scheduled"

    now = datetime.utcnow()
    race_list = []
    
    # Collect races 1-17 in sequential order
    if isinstance(calendar_data, dict):
        for race_id in range(1, 18):
            if race_id in calendar_data and isinstance(calendar_data[race_id], dict):
                race_data = calendar_data[race_id].copy()
                race_data['race_id'] = race_id
                race_list.append(race_data)
    
    # 🔥 Next race ТОЛЬКО для current season
    next_race_id = None
    if is_current_season:
        for race in race_list:
            if race.get('quali_close', now) > now:
                next_race_id = race['race_id']
                break
    
    text = ""
    for race in race_list:
        track = race.get('track', f'Race {race["race_id"]}')
        race_date = race.get('date', now)
        quali_close = race.get('quali_close', now)
        race_id = race['race_id']
        
        date_str = race_date.strftime("%a %d.%m")
        time_text = format_time_until_quali(quali_close)
        
        time_info = date_str
        if time_text:
            time_info += f" • {time_text}"
        
        # 🔥 ONLY для current season next race
        if next_race_id and race_id == next_race_id:
            text += f"🔥 **#{race_id} {track}** - {time_info}\n"
        else:
            text += f"**#{race_id} {track}** - {time_info}\n"
    
    return text.rstrip()

def format_race_beautiful(race_data):
    if not race_data: return "None"

    track = race_data.get('track', 'Unknown')
    hours_left = race_data.get('hours_left', 0)
    quali_close = race_data.get('quali_close', datetime.utcnow())
    
    hours_display = math.floor(hours_left)
    deadline = quali_close.strftime("%d.%m %H:%M")
    
    return f"Qualification closes in {hours_display}h\n**({deadline})** - {track}"

def format_time_until_quali(quali_close):
    """Time remaining until quali deadline - human friendly"""
    now = datetime.utcnow()
    delta = quali_close - now
    
    total_minutes = delta.total_seconds() / 60
    if total_minutes <= 0:
        return ""
    
    total_hours = total_minutes / 60
    total_days = total_hours / 24
    
    if total_minutes < 100:  # Less than 100 minutes → show minutes or H:M
        hours = math.floor(total_minutes / 60)
        minutes = math.floor(total_minutes % 60)
        if hours > 0:
            return f"{hours}h{minutes}m"  # "2h45m"
        else:
            return f"{minutes}m"         # "45m"
    elif total_days >= 30:   # 30+ days → months + days
        months = math.floor(total_days / 30)
        remaining_days = math.floor(total_days % 30)
        if remaining_days > 0:
            return f"{months}mo {remaining_days}d"  # "1m 5d"
        else:
            return f"{months}mo"                   # "1m"
    elif total_hours >= 120:  # 5+ days → just days
        days = math.floor(total_hours / 24)
        return f"{days}d"
    elif total_hours >= 24:   # 1+ day → "1d 14h"
        days = math.floor(total_hours / 24)
        remaining_hours = math.floor(total_hours % 24)
        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h"  # "1d 14h"
        else:
            return f"{days}d"                   # "1d"
    else:
        hours = math.floor(total_hours)
        return f"{hours}h"  # "23h"

def build_language_keyboard(page: int = 1, current_lang: str = 'gb') -> InlineKeyboardMarkup:
    """Build paginated language selection keyboard

    Args:
        page: Page number (1-4)
        current_lang: User's current language code

    Returns:
        InlineKeyboardMarkup with language options and navigation
    """
    # Language codes distributed across 4 pages (31 total)
    pages = [
        ['gb', 'de', 'es', 'ro', 'it', 'fr', 'pl', 'bg'],
        ['mk', 'nl', 'fi', 'hu', 'tr', 'gr', 'dk', 'pt'],
        ['ru', 'rs', 'se', 'lt', 'ee', 'al', 'hr', 'ch'],
        ['my', 'in', 'pi', 'be', 'br', 'cz', 'sk']
    ]

    buttons = []

    # Language selection buttons
    for lang_code in pages[page - 1]:
        is_current = lang_code == current_lang
        prefix = "✅ " if is_current else ""
        button_text = f"{prefix}{LANGUAGE_OPTIONS[lang_code]}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"lang_{lang_code}"
        )])

    # Add reset button on last page
    if page == len(pages):
        buttons.append([InlineKeyboardButton(
            text="🔄 Reset to Default (English)",
            callback_data="lang_reset_default"
        )])

    # Navigation footer
    footer = []
    if page > 1:
        footer.append(InlineKeyboardButton(text="◀ Previous", callback_data=f"lang_page_{page-1}"))
    footer.append(InlineKeyboardButton(text="🏠 Main Menu", callback_data="lang_back_main"))
    if page < len(pages):
        footer.append(InlineKeyboardButton(text="Next ▶", callback_data=f"lang_page_{page+1}"))

    buttons.append(footer)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id

    # Check BEFORE adding
    was_new = user_id not in users_data
    get_user_status(user_id)

    if was_new:
        logger.info(f"🆕 NEW user {user_id} registered via /start")
    else:
        logger.debug(f"👤 Existing user {user_id} used /start")

    await message.answer("🏁 GPRO Bot LIVE!\n/status - Next race\n/calendar - Full season\n/next - Next season\n/setgroup - Set your race group\n/settings - Notification preferences")

@router.message(Command("setgroup"))
async def cmd_setgroup(message: Message, state: FSMContext):
    """Start group setup process"""
    await state.set_state(SetGroupStates.waiting_for_group)
    await message.answer(
        "🏁 **Set Your GPRO Group**\n\n"
        "Enter your group in one of these formats:\n"
        "• **E** (Elite)\n"
        "• **M12** (Master 12)\n"
        "• **P3** (Pro 3)\n"
        "• **A5** (Amateur 5)\n"
        "• **R11** (Rookie 11)\n\n"
        "Numbers can be 1-3 digits.",
        parse_mode='Markdown'
    )

@router.message(SetGroupStates.waiting_for_group)
async def process_group_input(message: Message, state: FSMContext):
    """Process user's group input"""
    group_input = message.text.strip().upper()

    # Validate format: E or M/P/A/R followed by 1-3 digits
    if group_input == 'E':
        valid = True
    elif re.match(r'^[MPAR]\d{1,3}$', group_input):
        valid = True
    else:
        await message.answer(
            "❌ Invalid format!\n\n"
            "Please use:\n"
            "• **E** for Elite\n"
            "• **M12**, **P3**, **A5**, **R11** etc.\n\n"
            "Try again:",
            parse_mode='Markdown'
        )
        return

    # Save the group
    set_user_group(message.from_user.id, group_input)
    await state.clear()

    await message.answer(
        f"✅ **Group set to: {group_input}**\n\n"
        f"Race and replay notifications will include direct links to your group!\n\n"
        f"Manage notification preferences with /settings",
        parse_mode='Markdown'
    )

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Show notification settings menu"""
    user_id = message.from_user.id
    user_status = get_user_status(user_id)
    notifications = user_status.get('notifications', {})
    current_lang = user_status.get('gpro_lang', 'gb')

    # Build inline keyboard with toggle buttons
    keyboard_buttons = []

    # Add language settings button at the top
    lang_display = LANGUAGE_OPTIONS.get(current_lang, current_lang)
    keyboard_buttons.append([InlineKeyboardButton(
        text=f"🌍 Language: {lang_display}",
        callback_data="lang_menu"
    )])

    # Notification toggles
    for notif_type, label in NOTIFICATION_LABELS.items():
        enabled = notifications.get(notif_type, True)
        icon = "✅" if enabled else "❌"
        button_text = f"{icon} {label}"
        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"toggle_{notif_type}"
        )])

    # Add "Enable All" / "Disable All" button
    all_enabled = all(notifications.get(t, True) for t in NOTIFICATION_LABELS.keys())
    if all_enabled:
        keyboard_buttons.append([InlineKeyboardButton(
            text="🔕 Disable All Notifications",
            callback_data="toggle_all_off"
        )])
    else:
        keyboard_buttons.append([InlineKeyboardButton(
            text="🔔 Enable All Notifications",
            callback_data="toggle_all_on"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(
        "⚙️ **Notification Settings**\n\n"
        "Click to toggle notifications on/off:\n"
        "✅ = Enabled | ❌ = Disabled\n\n"
        "ℹ️ *These are global switches for all races. Use the 'Quali Done' button in notifications to disable a specific race.*",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@router.message(Command("status"))
async def cmd_status(message: Message):
    status = get_user_status(message.from_user.id)
    races_soon = get_races_closing_soon()

    next_race = "No upcoming races"
    next_race_id = None

    if races_soon:
        if isinstance(races_soon, dict) and races_soon:
            race_data = list(races_soon.values())[0]
            next_race_id = list(races_soon.keys())[0]
            next_race = format_race_beautiful(race_data)
        elif isinstance(races_soon, list) and len(races_soon) > 0:
            race_data = races_soon[0]
            next_race_id = race_data.get('race_id')
            next_race = format_race_beautiful(race_data)

    status_text = ""
    completed_race = status.get('completed_quali')

    if completed_race:
        status_text = f"✅ **Quali {completed_race} done**\n*Next race notifications active*"
    else:
        status_text = "🔔 **Notifications active**"

    text = (
        f"🏁 **GPRO Status**\n\n"
        f"🎯 **Next race:**\n{next_race}\n\n"
        f"{status_text}"
    )

    # Show appropriate button based on status
    if completed_race:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🔄 Re-enable Quali {completed_race} notifications", callback_data="reset_all")]
        ])
        await message.answer(text, reply_markup=keyboard, parse_mode='Markdown')
    elif next_race_id:
        # Show "Mark Quali Done" button for the upcoming race
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Mark Quali #{next_race_id} Done", callback_data=f"done_{next_race_id}")]
        ])
        await message.answer(text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.answer(text, parse_mode='Markdown')

@router.message(Command("notify"))
async def cmd_notify(message: Message, bot):
    if not race_calendar:
        await message.answer("🔔 No races scheduled")
        return
    
    # FIXED: Sort by quali_close time to get TRUE next race
    now = datetime.utcnow()
    future_races = []
    
    # Handle dict or list
    if isinstance(race_calendar, dict):
        for race_id, race_data in race_calendar.items():
            if isinstance(race_data, dict) and race_data.get('quali_close', now) > now:
                future_races.append((race_id, race_data))
    else:
        # List format fallback
        for i, race_data in enumerate(race_calendar):
            if isinstance(race_data, dict) and race_data.get('quali_close', now) > now:
                race_id = race_data.get('race_id', i+1)
                future_races.append((race_id, race_data))
    
    # Sort by quali_close (earliest first)
    future_races.sort(key=lambda x: x[1].get('quali_close', now))
    
    if future_races:
        next_race_id, next_race_data = future_races[0]  # First = soonest
        await send_quali_notification(bot, message.from_user.id, next_race_id, next_race_data, "manual")
        logger.info(f"🔔 /notify sent for race {next_race_id} ({next_race_data.get('track', 'Unknown')}) to {message.from_user.id}")
    else:
        await message.answer("🔔 No upcoming qualifications")

@router.message(Command("calendar"))
async def cmd_calendar(message: Message):
    calendar_text = format_full_calendar(race_calendar, "Full Season", is_current_season=True)
    text = f"🏁 **Full Season**\n\n{calendar_text}"
    await message.answer(text, parse_mode='Markdown')

@router.message(Command("next"))
async def cmd_next(message: Message):
    await load_next_season_silent()
    
    if not next_season_calendar:
        await message.answer("🌟 **Next season not published yet**")
        return
    
    calendar_text = format_full_calendar(next_season_calendar, "Next Season", is_current_season=False)
    text = f"🌟 **NEXT SEASON** ({len(next_season_calendar)} races)\n\n{calendar_text}"
    await message.answer(text, parse_mode='Markdown')

@router.message(Command("schedule"))
async def cmd_schedule(message: Message):
    await cmd_calendar(message)

@router.message(Command("update"))
async def cmd_update(message: Message):
    if message.from_user.id not in ADMIN_USER_IDS:
        await message.answer("❌ Admin only")
        return

    await update_calendar()

    reset_count = 0
    for user_id in list(users_data.keys()):
        reset_user_status(user_id)
        reset_count += 1

    # Current season status
    await message.answer(
        f"✅ **Calendar**: {len(race_calendar)} races\n"
        f"🔄 **{reset_count} users** reset",
        parse_mode="Markdown",
    )

    # Next season status (no file-removed text)
    if next_season_calendar:
        await message.answer(
            f"🌟 **Next season ready!** {len(next_season_calendar)} races\nUse /next to view",
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            "ℹ️ **Next season not published**",
            parse_mode="Markdown",
        )

@router.message(Command("users"))
async def cmd_users(message: Message):
    logger.debug(f"USERS - User: {message.from_user.id} ({type(message.from_user.id)}), Admins: {ADMIN_USER_IDS}")

    if message.from_user.id not in ADMIN_USER_IDS:
        logger.warning(f"USERS: Access denied for user {message.from_user.id}")
        await message.answer("❌ Admin only")
        return

    logger.info("USERS: Admin access granted")

    try:
        logger.info(f"USERS: Loaded {len(users_data)} users from notifications")

        if not users_data:
            await message.answer("📊 **0 users** in database", parse_mode='Markdown')
            return

        text = f"📊 **{len(users_data)} users**:\n\n"
        for uid, status in users_data.items():
            quali = status.get("completed_quali", "None")
            text += f"• `{uid}`: Race {quali}\n"

        await message.answer(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"USERS ERROR: {e}")
        await message.answer("❌ Error loading user data", parse_mode='Markdown')

@router.callback_query(F.data.startswith("toggle_"))
async def handle_toggle_notification(callback: CallbackQuery):
    """Handle notification toggle button clicks"""
    user_id = callback.from_user.id

    # Handle "Enable All" / "Disable All"
    if callback.data == "toggle_all_on":
        user_status = get_user_status(user_id)
        for notif_type in user_status['notifications'].keys():
            user_status['notifications'][notif_type] = True
        save_users_data()
        feedback_text = "✅ All notifications enabled!"
    elif callback.data == "toggle_all_off":
        user_status = get_user_status(user_id)
        for notif_type in user_status['notifications'].keys():
            user_status['notifications'][notif_type] = False
        save_users_data()
        feedback_text = "🔕 All notifications disabled!"
    else:
        # Toggle individual notification
        notification_type = callback.data.replace("toggle_", "")
        new_state = toggle_notification(user_id, notification_type)

        status_text = "enabled" if new_state else "disabled"
        feedback_text = f"✅ {NOTIFICATION_LABELS[notification_type]} {status_text}!"
        # Get updated status after toggle
        user_status = get_user_status(user_id)

    # Rebuild the settings menu with updated states (user_status already fetched above)
    notifications = user_status.get('notifications', {})

    keyboard_buttons = []
    for notif_type, label in NOTIFICATION_LABELS.items():
        enabled = notifications.get(notif_type, True)
        icon = "✅" if enabled else "❌"
        button_text = f"{icon} {label}"
        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"toggle_{notif_type}"
        )])

    # Add "Enable All" / "Disable All" button
    all_enabled = all(notifications.get(t, True) for t in NOTIFICATION_LABELS.keys())
    if all_enabled:
        keyboard_buttons.append([InlineKeyboardButton(
            text="🔕 Disable All Notifications",
            callback_data="toggle_all_off"
        )])
    else:
        keyboard_buttons.append([InlineKeyboardButton(
            text="🔔 Enable All Notifications",
            callback_data="toggle_all_on"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    # Update the message
    await callback.message.edit_reply_markup(reply_markup=keyboard)

    # Show feedback
    await callback.answer(feedback_text)

@router.callback_query(F.data.startswith("done_"))
async def handle_quali_done(callback: CallbackQuery):
    try:
        race_id = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid race ID", show_alert=True)
        return

    mark_quali_done(callback.from_user.id, race_id)
    await callback.message.edit_text(callback.message.text + "\n\n✅ *Race marked done!*")
    await callback.answer("✅ Done!")

@router.callback_query(F.data.startswith("reset_"))
async def handle_reset(callback: CallbackQuery):
    if callback.data == "reset_all":
        reset_user_status(callback.from_user.id)
        await callback.message.edit_text(callback.message.text + "\n\n🔄 *Notifications reset!*")
        await callback.answer("🔄 Reset!")
    else:
        # reset_{race_id} format
        try:
            race_id = int(callback.data.split("_")[1])
        except (ValueError, IndexError):
            await callback.answer("❌ Invalid race ID", show_alert=True)
            return

        reset_user_status(callback.from_user.id)
        await callback.message.edit_text(callback.message.text + "\n\n🔄 *Notifications re-enabled!*")
        await callback.answer("🔄 Re-enabled!")

@router.callback_query(F.data == "lang_menu")
async def handle_language_menu(callback: CallbackQuery):
    """Open language selection menu (page 1)"""
    user_id = callback.from_user.id
    current_lang = get_user_language(user_id)

    keyboard = build_language_keyboard(page=1, current_lang=current_lang)

    await callback.message.edit_text(
        f"🌍 **Language Settings**\n\n"
        f"Current: {LANGUAGE_OPTIONS.get(current_lang, current_lang)}\n\n"
        f"Select your preferred language for GPRO race links:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("lang_page_"))
async def handle_language_page(callback: CallbackQuery):
    """Handle language pagination"""
    user_id = callback.from_user.id
    current_lang = get_user_language(user_id)

    try:
        page = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid page", show_alert=True)
        return

    keyboard = build_language_keyboard(page=page, current_lang=current_lang)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("lang_") & ~F.data.in_(["lang_menu", "lang_back_main", "lang_reset_default"]))
async def handle_language_select(callback: CallbackQuery):
    """Handle language selection"""
    user_id = callback.from_user.id

    # Extract language code from callback data (e.g., "lang_de" -> "de")
    lang_code = callback.data.replace("lang_", "")

    # Handle pagination separately (already handled by handle_language_page)
    if lang_code.startswith("page_"):
        return

    # Set user language
    if set_user_language(user_id, lang_code):
        lang_display = LANGUAGE_OPTIONS.get(lang_code, lang_code)

        # Get current page to rebuild keyboard with updated selection
        current_lang = get_user_language(user_id)
        # Determine which page this language is on
        pages = [
            ['gb', 'de', 'es', 'ro', 'it', 'fr', 'pl', 'bg'],
            ['mk', 'nl', 'fi', 'hu', 'tr', 'gr', 'dk', 'pt'],
            ['ru', 'rs', 'se', 'lt', 'ee', 'al', 'hr', 'ch'],
            ['my', 'in', 'pi', 'be', 'br', 'cz', 'sk']
        ]
        current_page = 1
        for i, page_langs in enumerate(pages, 1):
            if lang_code in page_langs:
                current_page = i
                break

        keyboard = build_language_keyboard(page=current_page, current_lang=current_lang)

        await callback.message.edit_text(
            f"🌍 **Language Settings**\n\n"
            f"Current: {lang_display}\n\n"
            f"Select your preferred language for GPRO race links:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        await callback.answer(f"✅ Language set to {lang_display}")
    else:
        await callback.answer("❌ Invalid language", show_alert=True)

@router.callback_query(F.data == "lang_reset_default")
async def handle_language_reset(callback: CallbackQuery):
    """Reset language to default (English GB)"""
    user_id = callback.from_user.id

    if set_user_language(user_id, 'gb'):
        keyboard = build_language_keyboard(page=1, current_lang='gb')

        await callback.message.edit_text(
            f"🌍 **Language Settings**\n\n"
            f"Current: {LANGUAGE_OPTIONS['gb']}\n\n"
            f"Select your preferred language for GPRO race links:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        await callback.answer("✅ Language reset to English")
    else:
        await callback.answer("❌ Reset failed", show_alert=True)

@router.callback_query(F.data == "lang_back_main")
async def handle_language_back(callback: CallbackQuery):
    """Return to main settings menu"""
    user_id = callback.from_user.id
    user_status = get_user_status(user_id)
    notifications = user_status.get('notifications', {})
    current_lang = user_status.get('gpro_lang', 'gb')

    # Rebuild main settings keyboard
    keyboard_buttons = []

    # Language button
    lang_display = LANGUAGE_OPTIONS.get(current_lang, current_lang)
    keyboard_buttons.append([InlineKeyboardButton(
        text=f"🌍 Language: {lang_display}",
        callback_data="lang_menu"
    )])

    # Notification toggles
    for notif_type, label in NOTIFICATION_LABELS.items():
        enabled = notifications.get(notif_type, True)
        icon = "✅" if enabled else "❌"
        button_text = f"{icon} {label}"
        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"toggle_{notif_type}"
        )])

    # Enable/Disable All button
    all_enabled = all(notifications.get(t, True) for t in NOTIFICATION_LABELS.keys())
    if all_enabled:
        keyboard_buttons.append([InlineKeyboardButton(
            text="🔕 Disable All Notifications",
            callback_data="toggle_all_off"
        )])
    else:
        keyboard_buttons.append([InlineKeyboardButton(
            text="🔔 Enable All Notifications",
            callback_data="toggle_all_on"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        "⚙️ **Notification Settings**\n\n"
        "Click to toggle notifications on/off:\n"
        "✅ = Enabled | ❌ = Disabled\n\n"
        "ℹ️ *These are global switches for all races. Use the 'Quali Done' button in notifications to disable a specific race.*",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

logger.info("✅ handlers.py loaded - Aiogram 3.x Router ready (/setgroup + race live notifications added)")
