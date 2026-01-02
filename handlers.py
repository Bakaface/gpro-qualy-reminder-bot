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
from notifications import get_user_status, mark_quali_done, reset_user_status, set_user_group, toggle_notification, is_notification_enabled, users_data, save_users_data, send_quali_notification, LANGUAGE_OPTIONS, set_user_language, get_user_language, get_custom_notifications, set_custom_notification, parse_time_input, format_custom_notification_time, CUSTOM_NOTIF_MIN_HOURS, CUSTOM_NOTIF_MAX_HOURS
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

class CustomNotificationStates(StatesGroup):
    waiting_for_time = State()
    slot_index = State()

class OnboardingStates(StatesGroup):
    waiting_for_group = State()

import pycountry

def country_code_to_flag(country_code: str) -> str:
    """Convert ISO 2-letter country code to flag emoji

    Flag emojis are composed of regional indicator symbols.
    Each letter is converted to a regional indicator symbol.

    Examples:
        "US" -> "🇺🇸"
        "GB" -> "🇬🇧"
        "FR" -> "🇫🇷"
    """
    if not country_code or len(country_code) != 2:
        return ""

    # Regional indicator symbols start at 0x1F1E6 (for 'A')
    REGIONAL_INDICATOR_A = 0x1F1E6
    country_code = country_code.upper()

    try:
        flag = "".join(chr(REGIONAL_INDICATOR_A + ord(char) - ord('A')) for char in country_code)
        return flag
    except (ValueError, TypeError):
        return ""

def get_country_iso_code(country_name: str) -> str:
    """Automatically get ISO code for any country name using pycountry

    Handles variations and common names automatically.
    Returns empty string if country not found.
    """
    if not country_name:
        return ""

    # Try exact match first
    try:
        country = pycountry.countries.get(name=country_name)
        if country:
            return country.alpha_2
    except (KeyError, AttributeError):
        pass

    # Try fuzzy search
    try:
        results = pycountry.countries.search_fuzzy(country_name)
        if results:
            return results[0].alpha_2
    except (KeyError, LookupError, AttributeError):
        pass

    return ""

def add_flag_to_track(track: str) -> str:
    """Replace country name in parentheses with flag emoji

    Automatically detects country and converts to flag emoji.
    Works for any country without needing manual mapping.

    Examples:
        "Yas Marina GP (United Arab Emirates)" -> "Yas Marina GP 🇦🇪"
        "Sakhir GP (Bahrain)" -> "Sakhir GP 🇧🇭"
        "Silverstone GP (United Kingdom)" -> "Silverstone GP 🇬🇧"
    """
    if not track or '(' not in track:
        return track

    try:
        track_name = track.split('(')[0].strip()
        country = track.split('(')[1].split(')')[0].strip()

        # Get ISO code automatically
        iso_code = get_country_iso_code(country)
        if iso_code:
            flag = country_code_to_flag(iso_code)
            return f"{track_name} {flag}"
        else:
            # If country not found, keep original format
            return track
    except (IndexError, AttributeError):
        return track

def format_group_display(group: str) -> str:
    """Convert group code to human-readable format

    Examples:
        E -> Elite
        M3 -> Master - 3
        P15 -> Pro - 15
        A42 -> Amateur - 42
        R11 -> Rookie - 11
    """
    if not group:
        return "Not set"

    group = group.strip().upper()
    if group == 'E':
        return "Elite"

    import re
    match = re.match(r'^([MPAR])(\d{1,3})$', group)
    if not match:
        return group  # Return as-is if invalid format

    letter, number = match.groups()
    group_names = {
        'M': 'Master',
        'P': 'Pro',
        'A': 'Amateur',
        'R': 'Rookie'
    }

    return f"{group_names[letter]} - {number}"


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
        track = add_flag_to_track(track)  # Add flag emoji
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
    track = add_flag_to_track(track)  # Add flag emoji
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

def build_language_keyboard(page: int = 1, current_lang: str = 'gb', onboarding: bool = False) -> InlineKeyboardMarkup:
    """Build paginated language selection keyboard

    Args:
        page: Page number (1-4)
        current_lang: User's current language code
        onboarding: If True, use onboarding callbacks and add Skip button

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
    callback_prefix = "onboard_lang_" if onboarding else "lang_"

    # Language selection buttons
    for lang_code in pages[page - 1]:
        is_current = lang_code == current_lang
        prefix = "✅ " if is_current else ""
        button_text = f"{prefix}{LANGUAGE_OPTIONS[lang_code]}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"{callback_prefix}{lang_code}"
        )])

    # Add reset button on last page (only in settings, not onboarding)
    if page == len(pages) and not onboarding:
        buttons.append([InlineKeyboardButton(
            text="🔄 Reset to Default (English)",
            callback_data="lang_reset_default"
        )])

    # Navigation footer
    footer = []
    if page > 1:
        if onboarding:
            footer.append(InlineKeyboardButton(text="◀ Previous", callback_data=f"onboard_lang_page_{page-1}"))
        else:
            footer.append(InlineKeyboardButton(text="◀ Previous", callback_data=f"lang_page_{page-1}"))

    if onboarding:
        footer.append(InlineKeyboardButton(text="⏭️ Skip", callback_data="onboard_skip_lang"))
    else:
        footer.append(InlineKeyboardButton(text="🏠 Main Menu", callback_data="lang_back_main"))

    if page < len(pages):
        if onboarding:
            footer.append(InlineKeyboardButton(text="Next ▶", callback_data=f"onboard_lang_page_{page+1}"))
        else:
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
        # Show interactive onboarding for new users
        keyboard = build_language_keyboard(page=1, current_lang='gb', onboarding=True)
        await message.answer(
            "👋 **Welcome to GPRO Bot!**\n\n"
            "Let's get you set up. First, choose your preferred language for GPRO race links:\n\n"
            "🌍 **Select your language** (or skip to use English):",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    else:
        logger.debug(f"👤 Existing user {user_id} used /start")
        # Show normal command list for existing users
        await message.answer("🏁 GPRO Bot LIVE!\n/status - Next race\n/calendar - Full season\n/next - Next season\n/settings - Preferences")

@router.message(SetGroupStates.waiting_for_group)
async def process_group_input(message: Message, state: FSMContext):
    """Process user's group input from settings"""
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
            "• **M3** (Master 3) - Master has groups 1-5\n"
            "• **P15**, **A42**, **R11** etc.\n\n"
            "Try again:",
            parse_mode='Markdown'
        )
        return

    # Save the group
    set_user_group(message.from_user.id, group_input)
    group_display = format_group_display(group_input)
    await state.clear()

    # Show success with back to settings button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ Back to Settings", callback_data="settings_main")]
    ])

    await message.answer(
        f"✅ **Group set to: {group_display}**\n\n"
        f"Race and replay notifications will include direct links to your group!",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Show main settings menu"""
    user_id = message.from_user.id
    user_status = get_user_status(user_id)
    current_lang = user_status.get('gpro_lang', 'gb')
    current_group = user_status.get('group')

    # Build main settings menu
    keyboard_buttons = []

    # Language button
    lang_display = LANGUAGE_OPTIONS.get(current_lang, current_lang)
    keyboard_buttons.append([InlineKeyboardButton(
        text=f"🌍 Language: {lang_display}",
        callback_data="lang_menu"
    )])

    # Group button
    group_display = format_group_display(current_group)
    keyboard_buttons.append([InlineKeyboardButton(
        text=f"🏁 Group: {group_display}",
        callback_data="group_menu"
    )])

    # Notifications button (opens sub-menu)
    keyboard_buttons.append([InlineKeyboardButton(
        text="🔔 Notifications",
        callback_data="notif_menu"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(
        "⚙️ **Settings**\n\n"
        "Configure your preferences:",
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

    # Rebuild the notification sub-menu with updated states (user_status already fetched above)
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

    # Back button
    keyboard_buttons.append([InlineKeyboardButton(
        text="◀ Back",
        callback_data="settings_main"
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

@router.callback_query(F.data == "settings_main")
async def handle_settings_main(callback: CallbackQuery):
    """Return to main settings menu"""
    user_id = callback.from_user.id
    user_status = get_user_status(user_id)
    current_lang = user_status.get('gpro_lang', 'gb')
    current_group = user_status.get('group')

    # Build main settings keyboard
    keyboard_buttons = []

    # Language button
    lang_display = LANGUAGE_OPTIONS.get(current_lang, current_lang)
    keyboard_buttons.append([InlineKeyboardButton(
        text=f"🌍 Language: {lang_display}",
        callback_data="lang_menu"
    )])

    # Group button
    group_display = format_group_display(current_group)
    keyboard_buttons.append([InlineKeyboardButton(
        text=f"🏁 Group: {group_display}",
        callback_data="group_menu"
    )])

    # Notifications button
    keyboard_buttons.append([InlineKeyboardButton(
        text="🔔 Notifications",
        callback_data="notif_menu"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        "⚙️ **Settings**\n\n"
        "Configure your preferences:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

# Alias for backwards compatibility
@router.callback_query(F.data == "lang_back_main")
async def handle_language_back(callback: CallbackQuery):
    """Alias for returning to main settings"""
    await handle_settings_main(callback)

@router.callback_query(F.data == "notif_menu")
async def handle_notifications_menu(callback: CallbackQuery):
    """Show notifications sub-menu"""
    user_id = callback.from_user.id
    user_status = get_user_status(user_id)
    notifications = user_status.get('notifications', {})

    # Build notification toggles keyboard
    keyboard_buttons = []

    for notif_type, label in NOTIFICATION_LABELS.items():
        enabled = notifications.get(notif_type, True)
        icon = "✅" if enabled else "❌"
        button_text = f"{icon} {label}"
        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"toggle_{notif_type}"
        )])

    # Custom notifications button
    keyboard_buttons.append([InlineKeyboardButton(
        text="⏱️ Custom Notifications",
        callback_data="custom_notif_menu"
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

    # Back button
    keyboard_buttons.append([InlineKeyboardButton(
        text="◀ Back",
        callback_data="settings_main"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        "🔔 **Notification Settings**\n\n"
        "Click to toggle notifications on/off:\n"
        "✅ = Enabled | ❌ = Disabled\n\n"
        "ℹ️ *These are global switches for all races. Use the 'Quali Done' button in notifications to disable a specific race.*",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data == "custom_notif_menu")
async def handle_custom_notifications_menu(callback: CallbackQuery):
    """Show custom notifications menu"""
    user_id = callback.from_user.id
    custom_notifs = get_custom_notifications(user_id)

    # Build keyboard with custom notification slots
    keyboard_buttons = []

    for slot_idx, custom_notif in enumerate(custom_notifs):
        enabled = custom_notif.get('enabled', False)
        hours_before = custom_notif.get('hours_before')

        if enabled and hours_before is not None:
            time_str = format_custom_notification_time(hours_before)
            button_text = f"⏱️ Custom {slot_idx+1}: {time_str}"
        else:
            button_text = f"➕ Set Custom Notification {slot_idx+1}"

        keyboard_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"custom_notif_edit_{slot_idx}"
        )])

    # Back button
    keyboard_buttons.append([InlineKeyboardButton(
        text="◀ Back to Notifications",
        callback_data="notif_menu"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    min_time = int(CUSTOM_NOTIF_MIN_HOURS * 60)  # Convert to minutes
    max_time = int(CUSTOM_NOTIF_MAX_HOURS)  # Already in hours

    await callback.message.edit_text(
        "⏱️ **Custom Notifications**\n\n"
        f"Set your own notification times ({min_time}m - {max_time}h before quali closes).\n\n"
        f"You can have up to 2 custom notifications.\n\n"
        "Click a slot to set or edit it.",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("custom_notif_edit_"))
async def handle_custom_notification_edit(callback: CallbackQuery, state: FSMContext):
    """Handle editing a custom notification slot"""
    user_id = callback.from_user.id

    try:
        slot_idx = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid slot", show_alert=True)
        return

    custom_notifs = get_custom_notifications(user_id)
    custom_notif = custom_notifs[slot_idx]

    # Build preset buttons
    preset_times = [
        ("20m", 20/60), ("30m", 30/60), ("1h", 1),
        ("3h", 3), ("6h", 6), ("12h", 12),
        ("24h", 24), ("48h", 48), ("70h", 70)
    ]

    keyboard_buttons = []

    # Add preset buttons in rows of 3
    for i in range(0, len(preset_times), 3):
        row = []
        for label, hours in preset_times[i:i+3]:
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=f"custom_notif_set_{slot_idx}_{hours}"
            ))
        keyboard_buttons.append(row)

    # Add "Custom time" button
    keyboard_buttons.append([InlineKeyboardButton(
        text="✏️ Enter Custom Time",
        callback_data=f"custom_notif_input_{slot_idx}"
    )])

    # Add "Disable" button if currently enabled
    if custom_notif.get('enabled', False):
        keyboard_buttons.append([InlineKeyboardButton(
            text="🔕 Disable This Notification",
            callback_data=f"custom_notif_disable_{slot_idx}"
        )])

    # Back button
    keyboard_buttons.append([InlineKeyboardButton(
        text="◀ Back",
        callback_data="custom_notif_menu"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    current_status = ""
    if custom_notif.get('enabled', False):
        time_str = format_custom_notification_time(custom_notif.get('hours_before'))
        current_status = f"\n\n**Current:** {time_str}"

    await callback.message.edit_text(
        f"⏱️ **Custom Notification {slot_idx+1}**{current_status}\n\n"
        "Select a preset time or enter a custom time:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("custom_notif_set_"))
async def handle_custom_notification_set(callback: CallbackQuery):
    """Handle setting a custom notification with a preset value"""
    user_id = callback.from_user.id

    try:
        parts = callback.data.split("_")
        slot_idx = int(parts[3])
        hours_before = float(parts[4])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid data", show_alert=True)
        return

    success, message = set_custom_notification(user_id, slot_idx, hours_before)

    if success:
        await callback.answer(f"✅ {message}")
        # Return to custom notifications menu
        await handle_custom_notifications_menu(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)

@router.callback_query(F.data.startswith("custom_notif_disable_"))
async def handle_custom_notification_disable(callback: CallbackQuery):
    """Handle disabling a custom notification"""
    user_id = callback.from_user.id

    try:
        slot_idx = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid slot", show_alert=True)
        return

    success, message = set_custom_notification(user_id, slot_idx, None)

    if success:
        await callback.answer(f"✅ Custom notification {slot_idx+1} disabled")
        # Return to custom notifications menu
        await handle_custom_notifications_menu(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)

@router.callback_query(F.data.startswith("custom_notif_input_"))
async def handle_custom_notification_input_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt user to enter custom time"""
    try:
        slot_idx = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid slot", show_alert=True)
        return

    # Store slot index in state
    await state.update_data(slot_index=slot_idx)
    await state.set_state(CustomNotificationStates.waiting_for_time)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="custom_notif_menu")]
    ])

    await callback.message.edit_text(
        f"⏱️ **Custom Notification {slot_idx+1}**\n\n"
        "Enter your custom notification time.\n\n"
        "**Accepted formats:**\n"
        "• `20m` or `45 minutes` (20m-70h)\n"
        "• `2h` or `12 hours`\n"
        "• `1h 30m` or `2h30m`\n\n"
        "**Examples:**\n"
        "• `20m` - 20 minutes before\n"
        "• `6h` - 6 hours before\n"
        "• `1h 30m` - 1 hour 30 minutes before",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

@router.message(CustomNotificationStates.waiting_for_time)
async def process_custom_notification_time_input(message: Message, state: FSMContext):
    """Process user's custom time input"""
    user_id = message.from_user.id
    time_input = message.text.strip()

    # Get slot index from state
    state_data = await state.get_data()
    slot_idx = state_data.get('slot_index', 0)

    # Parse time input
    hours, error_msg = parse_time_input(time_input)

    if error_msg:
        await message.answer(
            f"❌ **Error:** {error_msg}\n\n"
            "Please try again with a valid format like: `2h`, `30m`, or `1h 30m`",
            parse_mode='Markdown'
        )
        return

    # Set custom notification
    success, result_msg = set_custom_notification(user_id, slot_idx, hours)

    # Clear state
    await state.clear()

    if success:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Back to Custom Notifications", callback_data="custom_notif_menu")]
        ])

        await message.answer(
            f"✅ **{result_msg}**\n\n"
            "Your custom notification has been set!",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Try Again", callback_data=f"custom_notif_input_{slot_idx}")],
            [InlineKeyboardButton(text="◀ Back", callback_data="custom_notif_menu")]
        ])

        await message.answer(
            f"❌ **Error:** {result_msg}\n\n"
            "Please try again.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

@router.callback_query(F.data == "group_menu")
async def handle_group_menu(callback: CallbackQuery, state: FSMContext):
    """Show group settings menu"""
    user_id = callback.from_user.id
    user_status = get_user_status(user_id)
    current_group = user_status.get('group')
    group_display = format_group_display(current_group)

    # Prompt for group input
    await state.set_state(SetGroupStates.waiting_for_group)
    await callback.message.edit_text(
        f"🏁 **Group Settings**\n\n"
        f"Current group: **{group_display}**\n\n"
        f"Enter your group in one of these formats:\n"
        f"• **E** (Elite)\n"
        f"• **M3** (Master 3) - Master has groups 1-5\n"
        f"• **P15** (Pro 15)\n"
        f"• **A42** (Amateur 42)\n"
        f"• **R11** (Rookie 11)\n\n"
        f"Numbers can be 1-3 digits.",
        parse_mode='Markdown'
    )
    await callback.answer()

# ============= ONBOARDING HANDLERS =============

@router.callback_query(F.data.startswith("onboard_lang_page_"))
async def handle_onboarding_language_page(callback: CallbackQuery):
    """Handle language pagination during onboarding"""
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid page", show_alert=True)
        return

    keyboard = build_language_keyboard(page=page, current_lang='gb', onboarding=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("onboard_lang_") & ~F.data.in_(["onboard_lang_page_1", "onboard_lang_page_2", "onboard_lang_page_3", "onboard_lang_page_4"]))
async def handle_onboarding_language_select(callback: CallbackQuery):
    """Handle language selection during onboarding"""
    user_id = callback.from_user.id

    # Extract language code
    lang_code = callback.data.replace("onboard_lang_", "")

    # Set user language
    if set_user_language(user_id, lang_code):
        lang_display = LANGUAGE_OPTIONS.get(lang_code, lang_code)
        await callback.answer(f"✅ Language set to {lang_display}")
    else:
        await callback.answer("❌ Invalid language", show_alert=True)
        return

    # Proceed to group selection
    await show_onboarding_group_menu(callback.message, user_id)

@router.callback_query(F.data == "onboard_skip_lang")
async def handle_onboarding_skip_language(callback: CallbackQuery):
    """Skip language selection during onboarding"""
    user_id = callback.from_user.id
    await callback.answer("⏭️ Using default language (English)")

    # Proceed to group selection
    await show_onboarding_group_menu(callback.message, user_id)

async def show_onboarding_group_menu(message: Message, user_id: int):
    """Show group selection menu during onboarding"""
    keyboard_buttons = [
        [
            InlineKeyboardButton(text="Elite", callback_data="onboard_group_E"),
            InlineKeyboardButton(text="Master 3", callback_data="onboard_group_M3")
        ],
        [
            InlineKeyboardButton(text="Pro 15", callback_data="onboard_group_P15"),
            InlineKeyboardButton(text="Amateur 42", callback_data="onboard_group_A42")
        ],
        [
            InlineKeyboardButton(text="Rookie 11", callback_data="onboard_group_R11")
        ],
        [
            InlineKeyboardButton(text="✏️ Enter Custom Group", callback_data="onboard_group_custom")
        ],
        [
            InlineKeyboardButton(text="⏭️ Skip", callback_data="onboard_skip_group")
        ]
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.edit_text(
        "🏁 **Group Selection**\n\n"
        "Choose your GPRO group to get personalized race links:\n\n"
        "Select a common group or enter your own:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@router.callback_query(F.data.startswith("onboard_group_") & (F.data != "onboard_group_custom"))
async def handle_onboarding_group_select(callback: CallbackQuery):
    """Handle preset group selection during onboarding"""
    user_id = callback.from_user.id

    # Extract group code
    group_code = callback.data.replace("onboard_group_", "")

    # Set user group
    set_user_group(user_id, group_code)
    group_display = format_group_display(group_code)
    await callback.answer(f"✅ Group set to {group_display}")

    # Show welcome complete message
    await show_onboarding_complete(callback.message)

@router.callback_query(F.data == "onboard_group_custom")
async def handle_onboarding_group_custom(callback: CallbackQuery, state: FSMContext):
    """Prompt for custom group input during onboarding"""
    await state.set_state(OnboardingStates.waiting_for_group)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Skip", callback_data="onboard_skip_group")]
    ])

    await callback.message.edit_text(
        "🏁 **Custom Group**\n\n"
        "Enter your group in one of these formats:\n"
        "• **E** (Elite)\n"
        "• **M3** (Master 3) - Master has groups 1-5\n"
        "• **P15** (Pro 15)\n"
        "• **A42** (Amateur 42)\n"
        "• **R11** (Rookie 11)\n\n"
        "Numbers can be 1-3 digits.",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()

@router.message(OnboardingStates.waiting_for_group)
async def process_onboarding_group_input(message: Message, state: FSMContext):
    """Process custom group input during onboarding"""
    user_id = message.from_user.id
    group_input = message.text.strip().upper()

    # Validate format
    if group_input == 'E':
        valid = True
    elif re.match(r'^[MPAR]\d{1,3}$', group_input):
        valid = True
    else:
        await message.answer(
            "❌ Invalid format!\n\n"
            "Please use:\n"
            "• **E** for Elite\n"
            "• **M3** (Master 3)\n"
            "• **P15**, **A42**, **R11** etc.\n\n"
            "Try again or use /start to restart:",
            parse_mode='Markdown'
        )
        return

    # Save the group
    set_user_group(user_id, group_input)
    group_display = format_group_display(group_input)
    await state.clear()

    # Show welcome complete message
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Got it!", callback_data="onboard_complete")]
    ])

    await message.answer(
        f"✅ **Setup Complete!**\n\n"
        f"Group: **{group_display}**\n\n"
        f"🏁 **GPRO Bot is ready!**\n\n"
        f"**Available commands:**\n"
        f"/status - Next race\n"
        f"/calendar - Full season\n"
        f"/next - Next season\n"
        f"/settings - Preferences",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@router.callback_query(F.data == "onboard_skip_group")
async def handle_onboarding_skip_group(callback: CallbackQuery, state: FSMContext):
    """Skip group selection during onboarding"""
    await state.clear()
    await callback.answer("⏭️ Skipped group selection")

    # Show welcome complete message
    await show_onboarding_complete(callback.message)

async def show_onboarding_complete(message: Message):
    """Show onboarding complete message"""
    await message.edit_text(
        "✅ **Setup Complete!**\n\n"
        "🏁 **GPRO Bot is ready!**\n\n"
        "**Available commands:**\n"
        "/status - Next race\n"
        "/calendar - Full season\n"
        "/next - Next season\n"
        "/settings - Preferences\n\n"
        "💡 *You can change these settings anytime using /settings*",
        parse_mode='Markdown'
    )

@router.callback_query(F.data == "onboard_complete")
async def handle_onboarding_complete(callback: CallbackQuery):
    """Acknowledge onboarding complete"""
    await callback.answer("✅ Welcome aboard!")

logger.info("✅ handlers.py loaded - Aiogram 3.x Router ready (group settings + notifications)")
