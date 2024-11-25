# publication_bot_test.py

import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

from config import TELEGRAM_BOT_TOKEN
from bot.handlers.admin_menu import router as publication_router

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверка загруженного токена
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не загружен. Проверьте файл .env и конфигурацию.")
    exit(1)
else:
    logger.info(f"✅ TELEGRAM_BOT_TOKEN успешно загружен: {TELEGRAM_BOT_TOKEN}")

# Инициализируем бота и диспетчер
try:
    publication_bot = Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("✅ Бот публикации инициализирован")
except Exception as e:
    logger.exception(f"❌ Ошибка при инициализации бота публикации: {e}")
    exit(1)

publication_storage = MemoryStorage()
publication_dp = Dispatcher(storage=publication_storage)

# Регистрируем роутеры
try:
    publication_dp.include_router(publication_router)
    logger.info("📌 Publication Router подключен к диспетчеру")
except Exception as e:
    logger.exception(f"❌ Ошибка при подключении роутера публикации: {e}")
    exit(1)

async def start_publication_bot():
    try:
        await publication_dp.start_polling(publication_bot)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске поллинга: {e}")

async def main():
    try:
        asyncio.create_task(start_publication_bot())
        logger.info("🚀 Публикационный бот запущен с поллингом")
        await asyncio.Event().wait()
    except Exception as e:
        logger.exception("❌ Ошибка в main")
        raise
    finally:
        logger.info("🛑 Завершение работы...")
        await publication_bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
