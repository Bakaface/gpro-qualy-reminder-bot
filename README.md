# GPRO Bot

Telegram bot for Grand Prix Racing Online (GPRO) that sends qualification deadline notifications and provides race status/schedule commands.

## 🚀 Public version
[t.me/gproremindbot](https://t.me/gproremindbot) - Public version!

## Features

- Automatic notifications: 48h, 24h, 2h, 10min before quali closes
- User button "✅ Quali Done" stops notifications until next race
- Commands: `/status`, `/calendar`, `/notify`
- Fetches GPRO calendar via API: `https://gpro.net/gb/backend/api/v2/Calendar`
- Multi-user support with `users_data.json` persistence

## Planned featues

- i18n support
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
git clone https://github.com/YOUR_USERNAME/gpro-bot.git
cd gpro-bot
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
| `/start` | Welcome + subscribe to notifications |
| `/status` | Next race + time remaining |
| `/calendar` | Full season calendar |
| `/notify` | Test notification |
| `/update` | Download current season calendar (admin only, once per season) |
| `/users` | See user list (admin only) |

## File Structure

```
gpro-bot/
├── bot.py              # Main Aiogram bot + notification loop
├── handlers.py         # Command handlers (/status, /settings)
├── notifications.py    # check_notifications() loop
├── gpro_calendar.py    # API fetch + cache
├── config.py           # Load .env
├── requirements.txt
├── .env.example		 # Rename to .env and fill in your data
├── users_data.json     # User settings (auto)
└── gpro_calendar.json  # Calendar downloaded after using /update (auto)
```

## Deployment (Ubuntu/Systemd)

```bash
sudo tee /etc/systemd/system/gpro.service > /dev/null <<EOF
[Unit]
Description=GPRO Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/gpro
Environment=PATH=/home/ubuntu/gpro/venv/bin
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

Caches results in `gpro_calendar.json`. No authentication required (only API key).


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
