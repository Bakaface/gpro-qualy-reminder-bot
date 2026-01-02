import asyncio
import logging
import json
import os
import re
from typing import Dict
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from gpro_calendar import get_races_closing_soon, race_calendar, check_quali_status_from_api, fetch_weather_from_api
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

users_data: Dict[int, Dict] = {}

# Notification windows: (hours_before, tolerance_minutes, label)
NOTIFICATION_WINDOWS = [
    (48, 6, "48h"),      # 48h ±6min
    (24, 6, "24h"),      # 24h ±6min
    (2, 5, "2h"),        # 2h ±5min
    (10/60, 2, "10min")  # 10min ±2min
]

# GPRO URL endpoints
GPRO_LIVE_ENDPOINT = "racescreenlive.asp"
GPRO_REPLAY_ENDPOINT = "racescreen.asp"

# Language options for URL generation (user-facing)
LANGUAGE_OPTIONS = {
    'gb': '🇬🇧 English', 'de': '🇩🇪 Deutsch', 'es': '🇪🇸 Español',
    'ro': '🇷🇴 Română', 'it': '🇮🇹 Italiano', 'fr': '🇫🇷 Français',
    'pl': '🇵🇱 Polski', 'bg': '🇧🇬 Български', 'mk': '🇲🇰 Македонски',
    'nl': '🇳🇱 Nederlands', 'fi': '🇫🇮 Suomi', 'hu': '🇭🇺 Magyar',
    'tr': '🇹🇷 Türkçe', 'gr': '🇬🇷 Ελληνικά', 'dk': '🇩🇰 Dansk',
    'pt': '🇵🇹 Português', 'ru': '🇷🇺 Русский', 'rs': '🇷🇸 Српски',
    'se': '🇸🇪 Svenska', 'lt': '🇱🇹 Lietuvių', 'ee': '🇪🇪 Eesti',
    'al': '🇦🇱 Shqip', 'hr': '🇭🇷 Hrvatski', 'ch': '🇨🇳 中文',
    'my': '🇲🇾 Bahasa Melayu', 'in': '🇮🇳 हिन्दी', 'pi': '🏴‍☠️ Pirate',
    'be': '🇧🇪 Vlaams', 'br': '🇧🇷 Português (BR)', 'cz': '🇨🇿 Čeština',
    'sk': '🇸🇰 Slovenčina'
}
DEFAULT_USER_LANG = 'gb'

# Timing constants
CHECK_INTERVAL_NORMAL_SECONDS = 300  # 5 minutes between checks (normal)
CHECK_INTERVAL_FAST_SECONDS = 60  # 1 minute between checks (when race approaching)
RACE_PROXIMITY_THRESHOLD_MINUTES = 10  # Switch to fast checks when race is within 10min
RACE_LIVE_NOTIFICATION_BEFORE_MINUTES = 1  # Send race live notification up to 1min before race
RACE_LIVE_NOTIFICATION_AFTER_MINUTES = 5  # Allow up to 5min after race start (just in case)
NOTIFICATION_HISTORY_RETENTION_DAYS = 30  # Keep notification history for 30 days

# API polling configuration for quali opening detection
API_CHECK_START_HOURS = 2  # Start checking API 2 hours after race
API_CHECK_END_HOURS = 3.5  # Stop checking and send fallback at 3.5 hours
API_CHECK_INTERVAL_MINUTES = 10  # Check API every 10 minutes
FALLBACK_TOLERANCE_MINUTES = 15  # Send fallback within 15min of reaching 3.5h

# Custom notification constraints
CUSTOM_NOTIF_MIN_HOURS = 20 / 60  # 20 minutes minimum
CUSTOM_NOTIF_MAX_HOURS = 70  # 70 hours maximum
CUSTOM_NOTIF_MAX_SLOTS = 2  # Maximum 2 custom notifications per user
CUSTOM_NOTIF_TOLERANCE_MIN = 5  # ±5 minutes tolerance for custom notifications

# Use absolute path based on script location for robustness
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(_SCRIPT_DIR, 'users_data.json')

import pycountry

def country_code_to_flag(country_code: str) -> str:
    """Convert ISO 2-letter country code to flag emoji"""
    if not country_code or len(country_code) != 2:
        return ""
    REGIONAL_INDICATOR_A = 0x1F1E6
    country_code = country_code.upper()
    try:
        flag = "".join(chr(REGIONAL_INDICATOR_A + ord(char) - ord('A')) for char in country_code)
        return flag
    except (ValueError, TypeError):
        return ""

def get_country_iso_code(country_name: str) -> str:
    """Automatically get ISO code for any country name using pycountry"""
    if not country_name:
        return ""
    try:
        country = pycountry.countries.get(name=country_name)
        if country:
            return country.alpha_2
    except (KeyError, AttributeError):
        pass
    try:
        results = pycountry.countries.search_fuzzy(country_name)
        if results:
            return results[0].alpha_2
    except (KeyError, LookupError, AttributeError):
        pass
    return ""

def add_flag_to_track(track: str) -> str:
    """Replace country name in parentheses with flag emoji (automatic)"""
    if not track or '(' not in track:
        return track
    try:
        track_name = track.split('(')[0].strip()
        country = track.split('(')[1].split(')')[0].strip()
        iso_code = get_country_iso_code(country)
        if iso_code:
            flag = country_code_to_flag(iso_code)
            return f"{track_name} {flag}"
        else:
            return track
    except (IndexError, AttributeError):
        return track

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
    """Save user data with atomic write to prevent corruption"""
    try:
        # Write to temporary file first
        temp_file = USERS_FILE + '.tmp'
        with open(temp_file, 'w') as f:
            # TYPE FIX: Convert int keys → string for JSON
            save_data = {str(k): v for k, v in users_data.items()}
            json.dump(save_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ensure data is written to disk

        # Atomic rename (overwrites USERS_FILE)
        os.replace(temp_file, USERS_FILE)
        logger.debug(f"Saved {len(users_data)} users")
    except Exception as e:
        logger.error(f"Save failed: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

def get_default_notification_preferences():
    """Default notification settings - all enabled by default"""
    return {
        '48h': True,
        '24h': True,
        '2h': True,
        '10min': True,
        'opens_soon': True,
        'race_replay': True,
        'race_live': True
    }

def get_default_custom_notifications():
    """Default custom notification settings - empty slots"""
    return [
        {'enabled': False, 'hours_before': None},
        {'enabled': False, 'hours_before': None}
    ]

def get_user_status(user_id: int) -> Dict:
    global users_data
    logger.debug(f"get_user_status({user_id}): {len(users_data)} users in cache")

    if not users_data:
        load_users_data()
        logger.debug(f"Loaded {len(users_data)} users from file")

    if user_id not in users_data:
        logger.info(f"🆕 New user {user_id} registered")
        users_data[user_id] = {
            'completed_quali': None,
            'group': None,
            'notifications': get_default_notification_preferences(),
            'custom_notifications': get_default_custom_notifications(),
            'gpro_lang': DEFAULT_USER_LANG
        }
        save_users_data()
    else:
        # Ensure existing users have required fields (migration)
        # Batch migrations to avoid multiple saves
        needs_save = False
        if 'group' not in users_data[user_id]:
            users_data[user_id]['group'] = None
            logger.debug(f"Added 'group' field to user {user_id}")
            needs_save = True
        if 'notifications' not in users_data[user_id]:
            users_data[user_id]['notifications'] = get_default_notification_preferences()
            logger.debug(f"Added 'notifications' field to user {user_id}")
            needs_save = True
        if 'custom_notifications' not in users_data[user_id]:
            users_data[user_id]['custom_notifications'] = get_default_custom_notifications()
            logger.debug(f"Added 'custom_notifications' field to user {user_id}")
            needs_save = True
        if 'gpro_lang' not in users_data[user_id]:
            users_data[user_id]['gpro_lang'] = DEFAULT_USER_LANG
            logger.debug(f"Added 'gpro_lang' field to user {user_id}")
            needs_save = True

        # Save only once if any migrations were applied
        if needs_save:
            save_users_data()

    return users_data[user_id]

def set_user_group(user_id: int, group: str):
    """Set user's GPRO group for race links"""
    get_user_status(user_id)
    users_data[user_id]['group'] = group
    save_users_data()
    logger.info(f"User {user_id} set group to: {group}")

def toggle_notification(user_id: int, notification_type: str):
    """Toggle a specific notification type for a user"""
    user_status = get_user_status(user_id)
    current_state = user_status['notifications'].get(notification_type, True)
    user_status['notifications'][notification_type] = not current_state
    save_users_data()
    new_state = "enabled" if not current_state else "disabled"
    logger.info(f"User {user_id} {new_state} '{notification_type}' notifications")
    return not current_state

def is_notification_enabled(user_id: int, notification_type: str) -> bool:
    """Check if a notification type is enabled for a user"""
    user_status = get_user_status(user_id)
    return user_status['notifications'].get(notification_type, True)

def validate_custom_notification_hours(hours: float) -> tuple[bool, str]:
    """Validate custom notification time

    Args:
        hours: Hours before quali closes

    Returns:
        (is_valid, error_message)
    """
    if hours is None:
        return False, "Time cannot be empty"

    if hours < CUSTOM_NOTIF_MIN_HOURS:
        return False, f"Minimum time is 20 minutes"

    if hours > CUSTOM_NOTIF_MAX_HOURS:
        return False, f"Maximum time is 70 hours"

    return True, ""

def parse_time_input(time_str: str) -> tuple[float, str]:
    """Parse user time input into hours

    Supported formats:
    - "20m", "30min", "45 minutes" -> minutes
    - "2h", "12 hours" -> hours
    - "1h 30m", "2h30m" -> hours + minutes

    Returns:
        (hours_float, error_message)
    """
    if not time_str:
        return None, "Please enter a time"

    time_str = time_str.strip().lower()

    # Try to match "Xh Ym" or "XhYm" format
    match = re.match(r'^(\d+)\s*h(?:ours?)?\s*(\d+)\s*m(?:in(?:utes?)?)?$', time_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        total_hours = hours + minutes / 60
        return total_hours, ""

    # Try to match hours only: "Xh" or "X hours"
    match = re.match(r'^(\d+)\s*h(?:ours?)?$', time_str)
    if match:
        hours = int(match.group(1))
        return float(hours), ""

    # Try to match minutes only: "Xm" or "X minutes"
    match = re.match(r'^(\d+)\s*m(?:in(?:utes?)?)?$', time_str)
    if match:
        minutes = int(match.group(1))
        return minutes / 60, ""

    return None, "Invalid format. Use: 2h, 30m, or 1h 30m"

def format_custom_notification_time(hours: float) -> str:
    """Format hours into human-readable string

    Examples:
        0.333 -> "20m"
        1.5 -> "1h 30m"
        12 -> "12h"
    """
    if hours is None:
        return "Not set"

    total_minutes = hours * 60
    h = int(hours)
    m = int(total_minutes % 60)

    if h > 0 and m > 0:
        return f"{h}h {m}m"
    elif h > 0:
        return f"{h}h"
    else:
        return f"{m}m"

def set_custom_notification(user_id: int, slot: int, hours_before: float) -> tuple[bool, str]:
    """Set or update a custom notification slot

    Args:
        user_id: User ID
        slot: Slot index (0 or 1)
        hours_before: Hours before quali closes (None to disable)

    Returns:
        (success, message)
    """
    if slot < 0 or slot >= CUSTOM_NOTIF_MAX_SLOTS:
        return False, f"Invalid slot (must be 0-{CUSTOM_NOTIF_MAX_SLOTS-1})"

    # Validate hours if provided
    if hours_before is not None:
        is_valid, error_msg = validate_custom_notification_hours(hours_before)
        if not is_valid:
            return False, error_msg

    user_status = get_user_status(user_id)
    custom_notifs = user_status.get('custom_notifications', get_default_custom_notifications())

    # Ensure list has correct size
    while len(custom_notifs) < CUSTOM_NOTIF_MAX_SLOTS:
        custom_notifs.append({'enabled': False, 'hours_before': None})

    # Update slot
    if hours_before is None:
        custom_notifs[slot] = {'enabled': False, 'hours_before': None}
    else:
        custom_notifs[slot] = {'enabled': True, 'hours_before': hours_before}

    user_status['custom_notifications'] = custom_notifs
    save_users_data()

    time_str = format_custom_notification_time(hours_before)
    logger.info(f"User {user_id} set custom notification {slot+1} to: {time_str}")
    return True, f"Custom notification {slot+1} set to {time_str}"

def get_custom_notifications(user_id: int) -> list:
    """Get user's custom notifications

    Returns:
        List of custom notification dicts
    """
    user_status = get_user_status(user_id)
    return user_status.get('custom_notifications', get_default_custom_notifications())

def is_valid_language(lang_code: str) -> bool:
    """Validate language code against supported languages"""
    return lang_code in LANGUAGE_OPTIONS

def set_user_language(user_id: int, lang: str) -> bool:
    """Set user's preferred language for GPRO URLs

    Args:
        user_id: Telegram user ID
        lang: Language code (e.g., 'gb', 'de', 'fr')

    Returns:
        bool: True if language was set successfully, False if invalid
    """
    lang = lang.strip().lower()
    if not is_valid_language(lang):
        logger.warning(f"Invalid language code: {lang}")
        return False

    get_user_status(user_id)
    users_data[user_id]['gpro_lang'] = lang
    save_users_data()
    logger.info(f"User {user_id} set language to: {lang}")
    return True

def get_user_language(user_id: int) -> str:
    """Get user's preferred language for GPRO URLs

    Args:
        user_id: Telegram user ID

    Returns:
        str: Language code (defaults to 'gb' if not set)
    """
    user_status = get_user_status(user_id)
    return user_status.get('gpro_lang', DEFAULT_USER_LANG)

def generate_gpro_link(group: str, lang: str = 'gb', link_type: str = 'live') -> str:
    """Generate GPRO race link based on group format and type

    Args:
        group: User's GPRO group (E, M3, R11, etc.)
        lang: Language code for URL (e.g., 'gb', 'de', 'fr')
        link_type: 'live' for live race, 'replay' for replay

    Examples: E → Elite, M3 → Master - 3, A42 → Amateur - 42, R11 → Rookie - 11"""

    # Validate and fallback for language
    if not is_valid_language(lang):
        logger.warning(f"Invalid language code '{lang}', falling back to 'gb'")
        lang = 'gb'

    # Determine endpoint based on link type
    endpoint = GPRO_LIVE_ENDPOINT if link_type == 'live' else GPRO_REPLAY_ENDPOINT
    base_url = f"https://gpro.net/{lang}/{endpoint}?Group="

    if not group:
        return base_url

    group = group.strip().upper()

    # Elite has no number
    if group == 'E':
        return f"{base_url}Elite"

    # Parse group letter and number (e.g., M3, R11, P15, A42)
    match = re.match(r'^([MPAR])(\d{1,3})$', group)
    if not match:
        # Invalid format, return default
        return base_url

    letter, number = match.groups()
    group_names = {
        'M': 'Master',
        'P': 'Pro',
        'A': 'Amateur',
        'R': 'Rookie'
    }

    group_name = group_names[letter]
    # URL encode: "Rookie - 11" → "Rookie%20-%2011"
    encoded = f"{group_name}%20-%20{number}"
    return f"{base_url}{encoded}"

def generate_race_link(group: str, lang: str = 'gb') -> str:
    """Generate race live link - wrapper for backwards compatibility"""
    return generate_gpro_link(group, lang, 'live')

def generate_replay_link(group: str, lang: str = 'gb') -> str:
    """Generate race replay link - wrapper for backwards compatibility"""
    return generate_gpro_link(group, lang, 'replay')

def format_weather_data(weather: dict) -> str:
    """Format weather data into human-readable text

    Args:
        weather: Weather data from Practice API

    Returns:
        str: Formatted weather message
    """
    if not weather:
        return "⚠️ Weather data not available"

    # Practice / Qualify 1
    q1_weather = weather.get('q1WeatherTransl', weather.get('q1Weather', 'Unknown'))
    q1_temp = weather.get('q1Temp', '?')
    q1_hum = weather.get('q1Hum', '?')

    # Qualify 2 / Race Start
    q2_weather = weather.get('q2WeatherTransl', weather.get('q2Weather', 'Unknown'))
    q2_temp = weather.get('q2Temp', '?')
    q2_hum = weather.get('q2Hum', '?')

    message = "🌤️ **Race Weather Forecast**\n\n"
    message += f"**Practice / Qualify 1:** {q1_weather}\n"
    message += f"Temp: {q1_temp}°C • Humidity: {q1_hum}%\n\n"
    message += f"**Qualify 2 / Race Start:** {q2_weather}\n"
    message += f"Temp: {q2_temp}°C • Humidity: {q2_hum}%\n\n"

    # Race Quarters
    message += "**Race Conditions:**\n"

    quarters = [
        ("Start - 0h30m", "raceQ1"),
        ("0h30m - 1h00m", "raceQ2"),
        ("1h00m - 1h30m", "raceQ3"),
        ("1h30m - 2h00m", "raceQ4")
    ]

    for label, prefix in quarters:
        temp_low = weather.get(f"{prefix}TempLow", '?')
        temp_high = weather.get(f"{prefix}TempHigh", '?')
        hum_low = weather.get(f"{prefix}HumLow", '?')
        hum_high = weather.get(f"{prefix}HumHigh", '?')
        rain_low = weather.get(f"{prefix}RainPLow", '?')
        rain_high = weather.get(f"{prefix}RainPHigh", '?')

        # Format ranges - show single value if min == max
        temp_str = f"{temp_low}°" if temp_low == temp_high else f"{temp_low}°-{temp_high}°"
        hum_str = f"{hum_low}%" if hum_low == hum_high else f"{hum_low}%-{hum_high}%"
        rain_str = f"{rain_low}%" if rain_low == rain_high else f"{rain_low}%-{rain_high}%"

        message += f"\n**{label}:**\n"
        message += f"Temp: {temp_str} • Humidity: {hum_str}\n"
        message += f"Rain probability: {rain_str}\n"

    return message

async def send_race_live_notification(bot: Bot, user_id: int, race_id: int, race_data: Dict):
    """Send notification when race goes live"""
    user_status = get_user_status(user_id)
    group = user_status.get('group')
    user_lang = user_status.get('gpro_lang', DEFAULT_USER_LANG)

    track = add_flag_to_track(race_data['track'])
    race_date = race_data['date']
    race_time = race_date.strftime('%d.%m %H:%M UTC')

    race_link = generate_race_link(group, user_lang)

    # Build message based on whether group is set
    if group:
        message = (
            f"🏁 **Race #{race_id} is LIVE!**\n\n"
            f"📍 **{track}**\n"
            f"🕐 **{race_time}**\n\n"
            f"🔗 [Watch Live Race]({race_link})"
        )
    else:
        message = (
            f"🏁 **Race #{race_id} is LIVE!**\n\n"
            f"📍 **{track}**\n"
            f"🕐 **{race_time}**\n\n"
            f"⚠️ Set your group in /settings for a direct link!\n\n"
            f"🔗 [Watch Live Race]({race_link})"
        )

    try:
        await bot.send_message(user_id, message, parse_mode='Markdown')
        logger.info(f"🏁 Sent race live notification to {user_id} for race {race_id}")
    except Exception as e:
        logger.error(f"Race live notify {user_id} failed: {e}")

async def send_race_replay_notification(bot: Bot, user_id: int, race_id: int, race_data: Dict):
    """Send race replay notification when next quali opens"""
    user_status = get_user_status(user_id)
    group = user_status.get('group')
    user_lang = user_status.get('gpro_lang', DEFAULT_USER_LANG)

    track = add_flag_to_track(race_data['track'])
    race_date = race_data['date']
    race_time = race_date.strftime('%d.%m %H:%M UTC')

    replay_link = generate_replay_link(group, user_lang)

    # Build message based on whether group is set
    if group:
        message = (
            f"📺 **Race #{race_id} Replay Available**\n\n"
            f"📍 **{track}**\n"
            f"🕐 **{race_time}**\n\n"
            f"If the race has already been calculated, replay is available here:\n\n"
            f"🔗 [Watch Replay]({replay_link})"
        )
    else:
        message = (
            f"📺 **Race #{race_id} Replay Available**\n\n"
            f"📍 **{track}**\n"
            f"🕐 **{race_time}**\n\n"
            f"If the race has already been calculated, replay is available here:\n\n"
            f"⚠️ For personalized links, set your group in /settings!\n\n"
            f"🔗 [Watch Replay]({replay_link})"
        )

    try:
        await bot.send_message(user_id, message, parse_mode='Markdown')
        logger.info(f"📺 Sent race replay notification to {user_id} for race {race_id}")
    except Exception as e:
        logger.error(f"Race replay notify {user_id} failed: {e}")

async def send_quali_notification(bot: Bot, user_id: int, race_id: int, race_data: Dict, notification_type: str = "deadline"):
    user_status = get_user_status(user_id)

    # Skip automatic notifications if user marked quali done
    if user_status.get('completed_quali') == race_id and notification_type != "manual":
        return

    track = add_flag_to_track(race_data['track'])
    race_date = race_data['date']
    quali_close = race_data['quali_close']
    user_lang = user_status.get('gpro_lang', DEFAULT_USER_LANG)

    # Generate qualifying link
    quali_link = f"https://gpro.net/{user_lang}/Qualify.asp"

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

    # Check if user already marked this race done
    is_marked_done = user_status.get('completed_quali') == race_id

    # Check if weather data is available
    has_weather = race_id in race_calendar and 'weather' in race_calendar[race_id]

    if is_marked_done:
        keyboard_buttons = [
            [InlineKeyboardButton(text=f"🔄 Re-enable Race {race_id} notifications", callback_data=f"reset_{race_id}")]
        ]
        if has_weather:
            keyboard_buttons.append([InlineKeyboardButton(text="🌤️ Show Weather", callback_data=f"weather_{race_id}")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        message = (
            f"{emoji} {title}\n\n"
            f"🏁 **Race #{race_id}**\n"
            f"📍 **{track}**\n"
            f"📅 **Quali: {deadline} | Race: {race_time}**\n\n"
            f"🔗 [Go to Qualifying]({quali_link})\n\n"
            f"ℹ️ **Automatic notifications disabled** for this race\n"
            f"Click button to re-enable notifications"
        )
    else:
        keyboard_buttons = [
            [InlineKeyboardButton(text="✅ Quali Done", callback_data=f"done_{race_id}")]
        ]
        if has_weather:
            keyboard_buttons.append([InlineKeyboardButton(text="🌤️ Show Weather", callback_data=f"weather_{race_id}")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        message = (
            f"{emoji} {title}\n\n"
            f"🏁 **Race #{race_id}**\n"
            f"📍 **{track}**\n"
            f"📅 **Quali: {deadline} | Race: {race_time}**\n\n"
            f"🔗 [Go to Qualifying]({quali_link})\n\n"
            f"Click button to disable notifications for this race"
        )

    try:
        await bot.send_message(user_id, message, reply_markup=keyboard, parse_mode='Markdown')
        logger.info(f"✅ Sent {notification_type} to {user_id} for race {race_id}")
    except Exception as e:
        logger.error(f"Notify {user_id} failed: {e}")

notification_lock = asyncio.Lock()
notify_history = {}  # {(race_id, window): sent_timestamp}
last_api_check_time = None  # Track last API check to limit calls


def _check_quali_closing_notifications(now: datetime) -> list:
    """Check for races with qualifying closing soon

    Returns:
        list: Notifications to send [(type, race_id, race_data, label, history_key), ...]
    """
    notifications = []
    races_closing = get_races_closing_soon(48)

    for race_id, race_data in races_closing.items():
        quali_close = race_data['quali_close']

        # Check each preset notification window
        for hours_before, tolerance_min, label in NOTIFICATION_WINDOWS:
            time_until = (quali_close - now).total_seconds() / 3600
            target_hours = hours_before
            tolerance_hours = tolerance_min / 60

            # Check if we're in the notification window
            if abs(time_until - target_hours) <= tolerance_hours:
                history_key = (race_id, label)

                # Only send if not sent before
                if history_key not in notify_history:
                    notifications.append(('quali', race_id, race_data, label, history_key))

    return notifications

def _check_custom_notifications(now: datetime) -> list:
    """Check for custom notification times

    Returns:
        list: Notifications to send [(type, race_id, race_data, label, history_key, user_id), ...]
    """
    notifications = []
    races_closing = get_races_closing_soon(72)  # Check up to 72 hours (max custom time + buffer)

    # Check each user's custom notifications
    for user_id, user_data in users_data.items():
        custom_notifs = user_data.get('custom_notifications', [])

        for slot_idx, custom_notif in enumerate(custom_notifs):
            if not custom_notif.get('enabled', False):
                continue

            hours_before = custom_notif.get('hours_before')
            if hours_before is None:
                continue

            # Check each race
            for race_id, race_data in races_closing.items():
                quali_close = race_data['quali_close']
                time_until = (quali_close - now).total_seconds() / 3600

                # Check if we're within the custom notification window
                tolerance_hours = CUSTOM_NOTIF_TOLERANCE_MIN / 60
                if abs(time_until - hours_before) <= tolerance_hours:
                    # Create unique history key for this user+race+custom slot
                    label = f"custom_{slot_idx+1}"
                    history_key = (user_id, race_id, label)

                    # Only send if not sent before
                    if history_key not in notify_history:
                        notifications.append(('custom', race_id, race_data, label, history_key, user_id))

    return notifications


async def _check_quali_open_notifications(now: datetime) -> list:
    """Check for qualifications that just opened using API when appropriate

    Returns:
        list: Notifications to send [(type, race_id, race_data, label, history_key), ...]
    """
    global last_api_check_time
    notifications = []

    # Determine if we should check the API
    should_check_api = False
    races_in_polling_window = []
    races_for_fallback = []

    for race_id, race_data in race_calendar.items():
        # Skip race 1 (no previous race)
        if race_id == 1:
            continue

        # Check if already notified
        history_key = (race_id, "opens_soon")
        if history_key in notify_history:
            continue

        # Find previous race
        prev_race_id = race_id - 1
        if prev_race_id not in race_calendar:
            continue

        prev_race_time = race_calendar[prev_race_id]['date']
        hours_since_race = (now - prev_race_time).total_seconds() / 3600

        # Check if we're in the API polling window (2-3.5 hours after race)
        if API_CHECK_START_HOURS <= hours_since_race <= API_CHECK_END_HOURS:
            races_in_polling_window.append((race_id, race_data, prev_race_id, hours_since_race))
            should_check_api = True
        # Check if we've reached fallback time (3.5 hours, within tolerance)
        elif hours_since_race > API_CHECK_END_HOURS:
            minutes_since_fallback = (hours_since_race - API_CHECK_END_HOURS) * 60
            if minutes_since_fallback <= FALLBACK_TOLERANCE_MINUTES:
                races_for_fallback.append((race_id, race_data, prev_race_id, hours_since_race))

    # Check API if needed (rate limited to every 10 minutes)
    api_result = {}
    if should_check_api:
        # Only call API every 10 minutes
        if last_api_check_time is None or (now - last_api_check_time).total_seconds() >= API_CHECK_INTERVAL_MINUTES * 60:
            logger.info(f"🔍 Checking API for quali open status ({len(races_in_polling_window)} races in window)")
            api_result = await check_quali_status_from_api()
            last_api_check_time = now
        else:
            time_until_next = API_CHECK_INTERVAL_MINUTES * 60 - (now - last_api_check_time).total_seconds()
            logger.debug(f"API check skipped (next in {int(time_until_next)}s)")

    # Process results from API
    for race_id, race_data, prev_race_id, hours_since in races_in_polling_window:
        if race_id in api_result:
            # API confirmed quali is open!
            logger.info(f"🆕 API confirmed: Race {race_id} quali opened!")

            # Fetch weather data with retry (if not already fetched)
            if 'weather' not in race_calendar[race_id]:
                weather_data = await fetch_weather_from_api(race_id)

                # Retry once if failed
                if not weather_data:
                    logger.warning(f"Weather fetch failed for race {race_id}, retrying in 5s...")
                    await asyncio.sleep(5)
                    weather_data = await fetch_weather_from_api(race_id)

                    if not weather_data:
                        logger.error(f"Weather fetch failed after retry for race {race_id}")
                    else:
                        logger.info(f"Weather fetch succeeded on retry for race {race_id}")
            else:
                logger.debug(f"Weather data already cached for race {race_id}")

            history_key = (race_id, "opens_soon")
            notifications.append(('opens', race_id, race_data, "opens_soon", history_key))

            # Also send race replay notification for the previous race
            replay_history_key = (prev_race_id, "race_replay")
            if replay_history_key not in notify_history:
                prev_race_data = race_calendar[prev_race_id]
                notifications.append(('replay', prev_race_id, prev_race_data, "race_replay", replay_history_key))

    # Fallback: Send notification if we've reached 3.5h without API detection
    for race_id, race_data, prev_race_id, hours_since in races_for_fallback:
        logger.info(f"⏰ Fallback: Sending quali open for race {race_id} at {hours_since:.1f}h (API didn't detect)")

        # Fetch weather data with retry (if not already fetched)
        if 'weather' not in race_calendar[race_id]:
            weather_data = await fetch_weather_from_api(race_id)

            # Retry once if failed
            if not weather_data:
                logger.warning(f"Weather fetch failed for race {race_id}, retrying in 5s...")
                await asyncio.sleep(5)
                weather_data = await fetch_weather_from_api(race_id)

                if not weather_data:
                    logger.error(f"Weather fetch failed after retry for race {race_id}")
                else:
                    logger.info(f"Weather fetch succeeded on retry for race {race_id}")
        else:
            logger.debug(f"Weather data already cached for race {race_id}")

        history_key = (race_id, "opens_soon")
        notifications.append(('opens', race_id, race_data, "opens_soon", history_key))

        # Also send race replay notification for the previous race
        replay_history_key = (prev_race_id, "race_replay")
        if replay_history_key not in notify_history:
            prev_race_data = race_calendar[prev_race_id]
            notifications.append(('replay', prev_race_id, prev_race_data, "race_replay", replay_history_key))

    return notifications


def _check_race_live_notifications(now: datetime) -> list:
    """Check for races that are about to start or just started

    Returns:
        list: Notifications to send [(type, race_id, race_data, label, history_key), ...]
    """
    notifications = []

    for race_id, race_data in race_calendar.items():
        race_time = race_data['date']
        time_since_race = (now - race_time).total_seconds() / 60

        # Send if we're within window: 5min before to 2min after race starts
        # This ensures notification is sent early (at 18:55 check for 19:00 race)
        if -RACE_LIVE_NOTIFICATION_BEFORE_MINUTES <= time_since_race <= RACE_LIVE_NOTIFICATION_AFTER_MINUTES:
            history_key = (race_id, "race_live")
            if history_key not in notify_history:
                notifications.append(('live', race_id, race_data, "race_live", history_key))

    return notifications


async def _send_notifications_to_users(bot: Bot, notifications_to_send: list):
    """Send notifications to all eligible users

    Args:
        bot: Telegram bot instance
        notifications_to_send: List of notifications [(type, race_id, race_data, label, history_key, [user_id]), ...]
    """
    for notification_data in notifications_to_send:
        # Handle both formats: regular (5 items) and custom (6 items with user_id)
        if len(notification_data) == 6:
            notif_type, race_id, race_data, label, history_key, target_user_id = notification_data
            is_custom = True
        else:
            notif_type, race_id, race_data, label, history_key = notification_data
            target_user_id = None
            is_custom = False

        logger.info(f"🔔 Sending {label} notification for race {race_id}")
        sent_count = 0
        total_users = len(users_data)

        # For custom notifications, send to specific user only
        if is_custom:
            try:
                # Custom notifications are always quali-type
                await send_quali_notification(bot, target_user_id, race_id, race_data, label)
                sent_count = 1
                logger.info(f"✅ Sent custom notification ({label}) for race {race_id} to user {target_user_id}")
            except Exception as e:
                logger.error(f"Failed to send custom {label} to user {target_user_id}: {e}")
        else:
            # Regular notifications - send to all users with that notification enabled
            for user_id in users_data:
                if is_notification_enabled(user_id, label):
                    try:
                        if notif_type == 'quali' or notif_type == 'opens':
                            await send_quali_notification(bot, user_id, race_id, race_data, label)
                        elif notif_type == 'replay':
                            await send_race_replay_notification(bot, user_id, race_id, race_data)
                        elif notif_type == 'live':
                            await send_race_live_notification(bot, user_id, race_id, race_data)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send {label} to user {user_id}: {e}")

            logger.info(f"✅ Sent {label} for race {race_id} to {sent_count}/{total_users} users")

        # Update history after sending (re-acquire lock briefly)
        async with notification_lock:
            notify_history[history_key] = datetime.utcnow()


def _get_next_check_interval(now: datetime) -> int:
    """Determine next check interval based on proximity to upcoming races

    Returns faster checks when race is approaching for better timing precision.

    Returns:
        int: Seconds until next check
    """
    # Check if any race is approaching
    for race_id, race_data in race_calendar.items():
        race_time = race_data['date']
        minutes_until_race = (race_time - now).total_seconds() / 60

        # If race is within threshold, use fast checking
        if -RACE_LIVE_NOTIFICATION_AFTER_MINUTES <= minutes_until_race <= RACE_PROXIMITY_THRESHOLD_MINUTES:
            return CHECK_INTERVAL_FAST_SECONDS

    # Default to normal interval
    return CHECK_INTERVAL_NORMAL_SECONDS

async def check_notifications(bot: Bot):
    """Continuous notification loop - adaptive check interval based on race proximity"""
    global notify_history
    logger.info(f"🔔 Starting notification checker (adaptive: {CHECK_INTERVAL_NORMAL_SECONDS//60}min normal, {CHECK_INTERVAL_FAST_SECONDS}s when race approaching)")
    load_users_data()

    while True:
        try:
            # Determine what notifications to send (quick check under lock)
            async with notification_lock:
                now = datetime.utcnow()

                # Check all notification types
                notifications_to_send = []
                notifications_to_send.extend(_check_quali_closing_notifications(now))
                notifications_to_send.extend(await _check_quali_open_notifications(now))
                notifications_to_send.extend(_check_race_live_notifications(now))
                notifications_to_send.extend(_check_custom_notifications(now))

                # Clean old history entries
                cutoff = now - timedelta(days=NOTIFICATION_HISTORY_RETENTION_DAYS)
                notify_history = {k: v for k, v in notify_history.items() if v > cutoff}

                # Determine next check interval based on race proximity
                next_interval = _get_next_check_interval(now)

            # Send notifications outside the lock (slow operation)
            await _send_notifications_to_users(bot, notifications_to_send)

        except Exception as e:
            logger.error(f"❌ Notification check error: {e}")
            next_interval = CHECK_INTERVAL_NORMAL_SECONDS  # Fallback on error

        # Wait before next check (adaptive interval)
        await asyncio.sleep(next_interval)

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
