import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GPRO_API_TOKEN = os.getenv('GPRO_API_TOKEN')

# Validate ADMIN_USER_ID
admin_id = os.getenv('ADMIN_USER_ID')
if not admin_id:
    raise ValueError("ADMIN_USER_ID not set in .env file")
try:
    ADMIN_USER_ID = int(admin_id)
except ValueError:
    raise ValueError(f"ADMIN_USER_ID must be a valid integer, got: {admin_id}")

NEXT_SEASON_FILE = 'next_season_calendar.json'
CALENDAR_FILE = 'gpro_calendar.json'
GPRO_LANG = 'gb'
