# main.py

import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bot.middlewares.db_session import DbSessionMiddleware
from config import (
    TELEGRAM_BOT_TOKEN,
    DATABASE_URL, ALLOWED_USERS
)

from bot.handlers.start import router as start_router
from bot.handlers.admin_menu import router as admin_menu_router
from bot.handlers.delete_task import router as delete_task_router
from bot.handlers.upload_json import router as upload_json_router
from bot.handlers.webhook_handler import router as webhook_router
from bot.handlers.test import router as test_router
from bot.handlers.admin import router as admin_router  # Импортируйте admin_router
from database.database import Base
from database.models import Admin

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,  # Устанавливаем уровень DEBUG для детального логирования
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация публикационного бота
try:
    publication_bot = Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("✅ Публикационный бот инициализирован")
except Exception as e:
    logger.exception(f"❌ Ошибка при инициализации Публикационного бота: {e}")
    exit(1)

# Инициализация диспетчера публикационного бота
publication_storage = MemoryStorage()
publication_dp = Dispatcher(storage=publication_storage)

# Настройка базы данных
engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Подключение middleware к диспетчеру публикационного бота
publication_dp.message.middleware(DbSessionMiddleware(async_session_maker))
publication_dp.callback_query.middleware(DbSessionMiddleware(async_session_maker))

# Подключение всех необходимых роутеров
publication_dp.include_router(start_router)
publication_dp.include_router(admin_menu_router)
publication_dp.include_router(delete_task_router)
publication_dp.include_router(upload_json_router)
publication_dp.include_router(webhook_router)
publication_dp.include_router(test_router)
publication_dp.include_router(admin_router)  # Подключение admin_router

logger.info("📌 Все роутеры подключены к диспетчеру публикационного бота")

# Логирование зарегистрированных роутеров
logger.debug("Зарегистрированные роутеры:")
for router in publication_dp.sub_routers:
    logger.debug(f"- {router.name}")

async def init_db():
    """Инициализирует базу данных и добавляет начальных администраторов."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_maker() as session:
        for user_id in ALLOWED_USERS:
            query = select(Admin).where(Admin.telegram_id == user_id)
            result = await session.execute(query)
            admin = result.scalar_one_or_none()
            if not admin:
                admin = Admin(telegram_id=user_id, username=None)  # Вы можете установить username, если доступен
                session.add(admin)
                logger.info(f"Добавлен начальный администратор с Telegram ID: {user_id}")
        await session.commit()

async def delete_webhook():
    """Удаляет вебхук перед запуском бота (если установлен)."""
    try:
        await publication_bot.delete_webhook()
        logger.info("✅ Вебхук публикационного бота успешно удалён")
    except Exception as e:
        logger.exception(f"❌ Ошибка при удалении вебхука публикационного бота: {e}")

async def start_publication_bot():
    """Запуск публикационного бота с использованием Polling."""
    try:
        logger.info("🚀 Запуск публикационного бота с поллингом...")
        await publication_dp.start_polling(publication_bot)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске публикационного бота: {e}")
    finally:
        await publication_bot.close()
        logger.info("🛑 Публикационный бот остановлен")

async def main():
    """Главная функция запуска."""
    try:
        # Инициализация базы данных и добавление начальных администраторов
        await init_db()

        # Удаляем существующий вебхук перед запуском бота
        await delete_webhook()

        # Запуск публикационного бота
        await start_publication_bot()
    except Exception as e:
        logger.exception("❌ Ошибка в функции main")
    finally:
        logger.info("🛑 Завершение работы приложения...")

if __name__ == "__main__":
    asyncio.run(main())