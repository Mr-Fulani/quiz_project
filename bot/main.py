# main.py

import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bot.middlewares.db_session import DbSessionMiddleware
from config import (
    PUBLICATION_BOT_TOKEN, WEBHOOK_BOT_TOKEN,
    MAKE_WEBHOOK_URL, MAKE_WEBHOOK_TIMEOUT, MAKE_WEBHOOK_RETRIES, MAKE_WEBHOOK_RETRY_DELAY,
    DATABASE_URL
)

from handlers.start import router as start_router
from handlers.admin_menu import router as admin_menu_router
from handlers.delete_task import router as delete_task_router
from handlers.upload_json import router as upload_json_router
from handlers.webhook_handler import router as webhook_router

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,  # Устанавливаем уровень DEBUG для максимального логирования
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализируем ботов
try:
    publication_bot = Bot(token=PUBLICATION_BOT_TOKEN)
    logger.info("✅ Публикационный бот инициализирован")
except Exception as e:
    logger.exception(f"❌ Ошибка при инициализации Публикационного бота: {e}")
    exit(1)

try:
    webhook_bot = Bot(token=WEBHOOK_BOT_TOKEN)
    logger.info("✅ Webhook Bot инициализирован")
except Exception as e:
    logger.exception(f"❌ Ошибка при инициализации Webhook Bot: {e}")
    exit(1)

# Инициализируем диспетчеры
publication_storage = MemoryStorage()
publication_dp = Dispatcher(storage=publication_storage)

# Настройка базы данных
engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Подключаем мидлварь к диспетчеру публикационного бота
publication_dp.update.middleware(DbSessionMiddleware(async_session_maker))

# Подключаем роутеры к диспетчеру публикационного бота
publication_dp.include_router(start_router)
publication_dp.include_router(admin_menu_router)
publication_dp.include_router(delete_task_router)
publication_dp.include_router(upload_json_router)
# Убедитесь, что webhook_router подключен только к webhook_dp
# publication_dp.include_router(webhook_router)  # Удалено

logger.info("📌 Роутеры подключены к диспетчеру публикационного бота")
logger.debug(f"Зарегистрированные обработчики сообщений: {publication_dp.message.handlers}")

# Инициализируем диспетчер для webhook бота
webhook_dp = Dispatcher(bot=webhook_bot)

# **Добавляем регистрацию middleware для webhook_dp**
webhook_dp.update.middleware(DbSessionMiddleware(async_session_maker))

# Подключаем роутеры к диспетчеру webhook бота
webhook_dp.include_router(webhook_router)
logger.info("📌 Webhook Router подключен к диспетчеру Webhook бота")


# Функции для запуска ботов через Polling
async def start_publication_bot():
    """Запуск публикационного бота с поллингом"""
    try:
        await publication_dp.start_polling(publication_bot)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске поллинга публикационного бота: {e}")


async def start_webhook_bot():
    """Запуск webhook бота с поллингом"""
    try:
        await webhook_dp.start_polling(webhook_bot)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске поллинга webhook бота: {e}")


async def delete_webhooks():
    """Удаление вебхуков для обоих ботов"""
    try:
        await publication_bot.delete_webhook()
        logger.info("✅ Вебхук публикационного бота удалён")
    except Exception as e:
        logger.exception(f"❌ Ошибка при удалении вебхука публикационного бота: {e}")

    try:
        await webhook_bot.delete_webhook()
        logger.info("✅ Вебхук webhook бота удалён")
    except Exception as e:
        logger.exception(f"❌ Ошибка при удалении вебхука webhook бота: {e}")


async def main():
    try:
        # Удаляем вебхуки перед запуском polling
        await delete_webhooks()

        # Создаем задачи для обоих ботов
        publication_task = asyncio.create_task(start_publication_bot())
        webhook_task = asyncio.create_task(start_webhook_bot())
        logger.info("🚀 Оба бота запущены с поллингом")

        # Ожидаем завершения обоих задач
        await asyncio.gather(publication_task, webhook_task)
    except Exception as e:
        logger.exception("❌ Ошибка в main")
    finally:
        logger.info("🛑 Завершение работы...")
        await publication_bot.close()
        await webhook_bot.close()


if __name__ == "__main__":
    asyncio.run(main())