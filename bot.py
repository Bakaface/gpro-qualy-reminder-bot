import asyncio
import logging
import sys
sys.path.insert(0, '.')

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from gpro_calendar import load_calendar_silent
from notifications import check_notifications, load_users_data  # ADD load_users_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found!")
        return

    # CRITICAL: Load users BEFORE anything
    load_users_data()
    logger.info("✅ users_data loaded at startup")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    from handlers import router
    dp.include_router(router)
    logger.info("✅ Handlers router loaded")

    await load_calendar_silent()
    asyncio.create_task(check_notifications(bot))
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
