import json
import logging
import re
import os
import asyncio
from datetime import datetime, timedelta
import aiohttp
from config import GPRO_API_TOKEN, CALENDAR_FILE, GPRO_LANG, NEXT_SEASON_FILE

logger = logging.getLogger(__name__)

# Module-level globals
race_calendar = {}
next_season_calendar = {}

# Date parsing formats (in order of priority)
DATE_FORMATS = [
    '%d.%m %Y',    # 05.12 2025
    '%b %d, %Y',
    '%b %d %Y',
    '%d %b %Y',
    '%Y-%m-%d',
    '%d.%m.%Y'
]

# Race timing constants
RACE_START_HOUR_UTC = 19  # Races start at 19:00 UTC
RACE_START_MINUTE_UTC = 0
QUALI_CLOSES_BEFORE_RACE_HOURS = 1.5  # Quali closes 1.5 hours before race


def _load_calendar_from_file(filepath: str) -> dict:
    """Generic calendar loader from JSON file

    Returns:
        dict: Calendar data with datetime objects, or empty dict on error
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            calendar = {}
            for race_id_str, race_data in data.items():
                race_id = int(race_id_str)
                calendar[race_id] = {
                    'quali_close': datetime.fromisoformat(race_data['quali_close']),
                    'track': race_data['track'],
                    'date': datetime.fromisoformat(race_data['date']),
                    'group': race_data.get('group', 'Pro')
                }
            return calendar
    except FileNotFoundError:
        logger.warning(f"No cache file: {filepath}")
        return {}
    except Exception as e:
        logger.error(f"Cache load error from {filepath}: {e}")
        return {}


def _save_calendar_to_file(calendar: dict, filepath: str):
    """Generic calendar saver to JSON file with atomic write

    Args:
        calendar: Calendar dict with datetime objects
        filepath: Target file path

    Raises:
        Exception: If save fails
    """
    serializable = {}
    for k, v in calendar.items():
        serializable[str(k)] = {
            'quali_close': v['quali_close'].isoformat(),
            'track': v['track'],
            'date': v['date'].isoformat(),
            'group': v['group']
        }

    temp_file = filepath + '.tmp'
    try:
        with open(temp_file, 'w') as f:
            json.dump(serializable, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_file, filepath)
        logger.info(f"💾 Saved calendar to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save calendar to {filepath}: {e}")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        raise


async def load_calendar_silent() -> bool:
    """Load from cache ONLY - no API calls"""
    calendar = _load_calendar_from_file(CALENDAR_FILE)
    if calendar:
        global race_calendar
        race_calendar.clear()
        race_calendar.update(calendar)
        logger.info(f"✅ Loaded {len(calendar)} races from cache")
        return True
    return False

async def load_next_season_silent() -> bool:
    """Load next season from cache ONLY"""
    if not os.path.exists(NEXT_SEASON_FILE):
        return False

    calendar = _load_calendar_from_file(NEXT_SEASON_FILE)
    if calendar:
        global next_season_calendar
        next_season_calendar.clear()
        next_season_calendar.update(calendar)
        logger.info(f"✅ Loaded {len(calendar)} next season races from cache")
        return True
    return False

async def update_calendar() -> bool:
    """Update calendar from GPRO API - /update command"""
    if not GPRO_API_TOKEN:
        logger.error("❌ GPRO_API_TOKEN missing")
        return False
        
    url = f"https://gpro.net/{GPRO_LANG}/backend/api/v2/Calendar"
    headers = {
        "Authorization": f"Bearer {GPRO_API_TOKEN}",
        "User-Agent": "GPRO-QualiBot/1.0"
    }
    
    try:
        logger.info("🔄 Updating calendar from GPRO API...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    raw_response = await resp.json()
                    
                    # CURRENT SEASON
                    data = raw_response.get('events', [])
                    calendar = parse_gpro_events(data, is_next_season=False)
                    
                    if calendar:
                        save_calendar(calendar)
                        global race_calendar
                        race_calendar.clear()
                        race_calendar.update(calendar)
                        logger.info(f"✅ CURRENT SEASON: {len(calendar)} races!")
                    else:
                        logger.warning("No valid race events found")
                    
                    # NEXT SEASON LOGIC
                    next_season_published = raw_response.get("nextSeasonPublished", False)
                    logger.info(f"📊 API nextSeasonPublished: {next_season_published}")
                    
                    if next_season_published:
                        next_events = raw_response.get("nextSeasonEvents", [])
                        logger.info(f"📊 Found {len(next_events)} nextSeasonEvents")
                        
                        if next_events:
                            next_calendar = parse_gpro_events(next_events, is_next_season=True)
                            if next_calendar:
                                save_next_season_calendar(next_calendar)
                                global next_season_calendar
                                next_season_calendar.clear()
                                next_season_calendar.update(next_calendar)
                                logger.info(f"🌟 NEXT SEASON: {len(next_calendar)} races populated!")
                            else:
                                logger.warning("No valid next season events")
                        else:
                            logger.warning("nextSeasonPublished=true but no nextSeasonEvents")
                    else:
                        # FORCE CLEANUP
                        next_season_calendar.clear()
                        
                        if os.path.exists(NEXT_SEASON_FILE):
                            os.remove(NEXT_SEASON_FILE)
                            logger.info("🗑️ Next season file REMOVED - API says not published")
                        else:
                            logger.info("ℹ️ No next season file (already clean)")
                    
                    return True
                else:
                    logger.error(f"API {resp.status}")
    except Exception as e:
        logger.error(f"Calendar update error: {e}")
    
    return False

def parse_gpro_events(events: list, is_next_season: bool = False) -> dict:
    """Parse GPRO events - SEQUENTIAL RACE NUMBERS 1,2,3...!"""
    calendar = {}
    valid_races = []
    season_type = "🌟 NEXT" if is_next_season else "✅ CURRENT"
    
    # **1. COLLECT ALL valid races first**
    for event in events:
        if event.get('eventType') != 'R':  # Race only
            continue
            
        idx = event.get('idxReal') or event.get('idx')
        if not idx:
            continue
            
        date_str = event.get('dateEvent')
        track = event.get('trackName', f"Race {idx}")
        
        try:
            race_date = parse_gpro_date_fixed(date_str)
            if not race_date:
                continue

            # Set race start time
            race_date = race_date.replace(hour=RACE_START_HOUR_UTC, minute=RACE_START_MINUTE_UTC, second=0)
            quali_close = race_date - timedelta(hours=QUALI_CLOSES_BEFORE_RACE_HOURS)
            
            valid_races.append({
                'orig_id': int(idx),
                'quali_close': quali_close,
                'track': track[:30],
                'date': race_date,
                'group': event.get('group', 'Pro')
            })
        except Exception as e:
            logger.debug(f"Parse event {idx} error: {e}")
            continue
    
    # **2. SORT by date + RE-NUMBER 1,2,3...**
    valid_races.sort(key=lambda x: x['date'])
    
    for seq_num, race_data in enumerate(valid_races, 1):
        calendar[seq_num] = {
            'quali_close': race_data['quali_close'],
            'track': race_data['track'],
            'date': race_data['date'],
            'group': race_data['group']
        }
        logger.info(f"{season_type} Race {seq_num}: {race_data['track']} → {race_data['date'].strftime('%d.%m %Y 19:00 UTC')}")
    
    logger.info(f"{season_type} Parsed {len(calendar)} sequential race events at 19:00 UTC")
    return calendar

def parse_gpro_date_fixed(date_str: str) -> datetime:
    """Parse GPRO dates - Simple 'Today' handler!"""
    if not date_str:
        return None
    
    # **SIMPLE "Today" = CURRENT DAY 00:00**
    if 'Today' in date_str or '<font' in date_str or '<b>' in date_str:
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        logger.info(f"⏰ 'Today' → {today.strftime('%d.%m.%Y')} UTC 19:00")
        return today
        
    # **CLEAN HTML + ordinals**
    day_str = re.sub(r'<[^>]*>', '', date_str)
    day_str = re.sub(r'(?i)(st|nd|rd|th)\b', '', day_str)
    day_str = day_str.strip()
    
    now = datetime.utcnow()

    # Try all standard date formats
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(day_str, fmt)
            if dt.year < 2025:
                dt = dt.replace(year=now.year)
            return dt
        except ValueError:
            continue
    
    # Month/day only
    if not re.search(r'\d{4}', day_str):
        try:
            dt = datetime.strptime(day_str, '%b %d')
            dt = dt.replace(year=now.year)
            if dt.date() < now.date():
                dt = dt.replace(year=now.year + 1)
            return dt
        except (ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse date format '{day_str}': {e}")
            pass
    
    logger.warning(f"Cannot parse date: '{date_str}'")
    return None

def save_calendar(calendar: dict):
    """Save current season calendar with atomic write to prevent corruption"""
    _save_calendar_to_file(calendar, CALENDAR_FILE)

def save_next_season_calendar(calendar: dict):
    """Save next season calendar with atomic write to prevent corruption"""
    _save_calendar_to_file(calendar, NEXT_SEASON_FILE)

async def check_quali_status_from_api() -> dict:
    """Check real-time qualification status from GPRO /office endpoint

    Returns:
        dict: {race_id: seconds_left_quali} for races with active quali, empty dict on error
    """
    if not GPRO_API_TOKEN:
        return {}

    url = f"https://gpro.net/{GPRO_LANG}/backend/api/v2/office"
    headers = {
        "Authorization": f"Bearer {GPRO_API_TOKEN}",
        "User-Agent": "GPRO-QualiBot/1.0"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    seconds_left = data.get('secondsLeftQual')

                    if seconds_left and int(seconds_left) > 0:
                        # Figure out which race this quali is for
                        # by matching quali close time
                        seconds = int(seconds_left)
                        now = datetime.utcnow()
                        expected_close = now + timedelta(seconds=seconds)

                        # Find matching race (within 1 hour tolerance)
                        for race_id, race_data in race_calendar.items():
                            time_diff = abs((race_data['quali_close'] - expected_close).total_seconds())
                            if time_diff < 3600:  # Within 1 hour
                                logger.info(f"✅ API: Race {race_id} quali open, {seconds//3600}h remaining")
                                return {race_id: seconds}

                        logger.debug(f"API returned secondsLeftQual={seconds} but no matching race found")
                    else:
                        logger.debug("API: No active qualification")
                    return {}
                else:
                    logger.warning(f"Office API returned {resp.status}")
                    return {}
    except asyncio.TimeoutError:
        logger.warning("Office API timeout")
        return {}
    except Exception as e:
        logger.error(f"Office API error: {e}")
        return {}

def get_races_closing_soon(hours_before: float = 720) -> dict:
    """Get races closing within 30 days - SORTED by time!"""
    now = datetime.utcnow()
    upcoming = {}

    for race_id, data in race_calendar.items():
        time_to_close = (data['quali_close'] - now).total_seconds() / 3600
        if 0 < time_to_close <= hours_before:
            data_copy = data.copy()
            data_copy['hours_left'] = time_to_close
            upcoming[race_id] = data_copy

    # Sort by closest first
    sorted_upcoming = dict(sorted(upcoming.items(), key=lambda x: x[1]['hours_left']))
    logger.debug(f"Upcoming races ({len(sorted_upcoming)}): {list(sorted_upcoming.keys())}")
    return sorted_upcoming
