import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GPRO_API_TOKEN = os.getenv('GPRO_API_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))
CALENDAR_FILE = 'gpro_calendar.json'
GPRO_LANG = 'gb'
