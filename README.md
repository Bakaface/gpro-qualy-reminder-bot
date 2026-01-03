# GPRO Bot

Telegram bot for Grand Prix Racing Online (GPRO) that sends qualification deadline notifications and provides race status/schedule commands.

## 🚀 Public version
[t.me/gproremindbot](https://t.me/gproremindbot) - Public version!

## Features

### Notifications
- **Automatic quali notifications:** 48h, 24h, 2h, 10min before quali closes
- **Custom notification times:** Set up to 2 custom notification times (20m-70h)
- **Quali open detection:** API-based detection when qualification opens (2-3.5h after race)
- **Race live notifications:** Get notified when race goes live
- **Replay notifications:** Get notified when race replay is available
- **Weather forecast:** Automatic weather data fetch when quali opens (Practice/Q1, Q2/Start, race quarters)
- **User control:** "✅ Quali Done" button stops notifications for that race

### Personalization
- **Interactive onboarding:** New users select language and group during /start
- **Dual language support:** Bot UI in English/Russian + 31 languages for GPRO links
- **Group settings:** Personalized race/replay links (Elite, Master 1-5, Pro, Amateur, Rookie)
- **Notification preferences:** Toggle individual notification types on/off
- **Full i18n support:** All messages, buttons, and notifications are localized

### Commands
- `/status` - Next race with full details, qualifying link, and weather button
- `/calendar` - Full season calendar with all 17 races
- `/next` - Next season calendar (when published)
- `/settings` - Configure language, group, and notification preferences

### Technical
- **API Integration:** Calendar, Office (quali detection), Practice (weather)
- **Smart caching:** Weather data cached to minimize API calls
- **Retry logic:** Automatic retry if weather fetch fails
- **Optimized notifications:** Adaptive check intervals based on race proximity
- **Multi-user support:** Persistent user data with atomic writes

## Planned features

- Timezone selection with DST support (pytz named timezones)

# Hosting your own bot

## Tech Stack

- Python 3.10+ with Aiogram 3.x
- GPRO public API (no login credentials needed)
- `python-dotenv` for `TELEGRAM_BOT_TOKEN`
- `pytz` for timezone handling (planned)
- `asyncio` for concurrent notifications

## Quick Start

```bash
git clone https://github.com/nyakze/gpro-qualy-reminder-bot.git
cd gpro-qualy-reminder-bot
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN
python bot.py
```

## Configuration

**.env** (create from `.env.example`):
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here # get it from @botfather
GPRO_API_TOKEN=your_gpro_api_token # get it here https://app.gpro.net/apiaccess
ADMIN_USER_ID=your_telegram_id # to use admin commands
```

**users_data.json** (auto-generated):
```json
{
  "123456789": {
    "completed_quali": null
  }
}
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Interactive onboarding (language + group selection for new users) |
| `/status` | Next race with full details, qualifying link, and weather forecast |
| `/calendar` | Full season calendar (all 17 races) |
| `/next` | Next season calendar (when published) |
| `/settings` | Configure language, group, and notification preferences |
| `/update` | Update calendar from API (admin only) |
| `/weather` | Manually fetch weather data for testing (admin only) |
| `/users` | See user list (admin only) |

## File Structure

```
gpro-bot/
├── bot.py                      # Main Aiogram bot entry point
├── config.py                   # Environment configuration
├── gpro_calendar.py            # GPRO API integration & caching
├── i18n_setup.py               # i18n middleware setup
├── utils.py                    # Shared utilities (flags, formatting)
├── handlers/                   # Command & callback handlers
│   ├── __init__.py            # Router initialization
│   ├── commands.py            # /start, /status, /calendar, etc.
│   ├── callbacks.py           # Button interaction handlers
│   ├── states.py              # FSM state handlers
│   └── onboarding.py          # New user onboarding flow
├── notifications/              # Notification system
│   ├── __init__.py            # Module exports
│   ├── user_data.py           # User data persistence
│   ├── validation.py          # Custom notification validation
│   ├── sender.py              # Notification sending functions
│   └── checker.py             # Main notification loop
├── locales/                    # i18n translations
│   ├── en/                    # English
│   └── ru/                    # Russian
├── requirements.txt
├── .env.example               # Rename to .env and fill in your data
├── users_data.json            # User settings (auto-generated)
└── gpro_calendar.json         # Race calendar cache (auto-generated)
```

## Deployment (Ubuntu/Systemd)

```bash
sudo tee /etc/systemd/system/gpro.service > /dev/null <<EOF
[Unit]
Description=GPRO Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/gpro-qualy-reminder-bot
Environment=PATH=/home/ubuntu/gpro-qualy-reminder-bot/venv/bin
ExecStart=/home/ubuntu/gpro/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable gpro
sudo systemctl start gpro
sudo journalctl -u gpro -f
```

## Development

```bash
# Format code
black .
ruff check --fix .

# Debug
tail -f users_data.json
sudo journalctl -u gpro -f

# Test notifications
pkill -f notifications.py
source venv/bin/activate
python bot.py
```

## API Integration

Uses GPRO public calendar API:
```
GET https://gpro.net/gb/backend/api/v2/Calendar
```

🗄️ Caches results in `gpro_calendar.json`. Requires GPRO API token (.env → GPRO_API_TOKEN) 

## License
**Unlicense** - Free software, public domain. Use freely! ✨
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute this
software, either in source code form or as a compiled binary, for any purpose,
commercial or non-commercial, and by any means.

In jurisdictions that recognize copyright laws, the author or authors of this
software dedicate any and all copyright interest in the software to the public
domain. We make this dedication for the benefit of the public at large and to
the detriment of our heirs and successors. We intend this dedication to be an
overt act of relinquishment in perpetuity of all present and future rights to
this software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
