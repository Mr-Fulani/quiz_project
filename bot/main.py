# bot/main.py

# импорты Django
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quiz_backend.config.settings")
django.setup()

# импорты Бота
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bot.handlers.admin import router as admin_router  # Импортируйте admin_router
from bot.handlers.admin_menu import router as admin_menu_router
from bot.services.deletion_service import router as delete_task_router
from bot.handlers.poll_handler import router as poll_router
from bot.handlers.start import router as start_router
from bot.handlers.statistics_handler import router as statistics_router
from bot.handlers.test import router as test_router
from bot.handlers.upload_json import router as upload_json_router
from bot.handlers.user_handler import router as user_router
from bot.handlers.webhook_handler import router as webhook_router
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.user_middleware import UserMiddleware
from mini_app.app_handlers.handlers import router as mini_app_router
from bot.config import (
    TELEGRAM_BOT_TOKEN,
    DATABASE_URL
)
from database.database import Base
from mini_app.config import WEBAPP_URL  # Импортируем переменную


# настройки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quiz_project.settings")  # замените на ваш путь к настройкам
django.setup()

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

# ------------------------------------------------------------------------
# Глобальная регистрация middleware (на все типы апдейтов):
# dp.update.middleware(...) — в Aiogram 3.x применится к любому Update.
# ------------------------------------------------------------------------
publication_dp.update.middleware(DbSessionMiddleware(async_session_maker))
publication_dp.update.middleware(UserMiddleware())


# Подключение всех необходимых роутеров
publication_dp.include_router(start_router)
publication_dp.include_router(admin_menu_router)
publication_dp.include_router(delete_task_router)
publication_dp.include_router(upload_json_router)
publication_dp.include_router(webhook_router)
publication_dp.include_router(test_router)
publication_dp.include_router(admin_router)  # Подключение admin_router
publication_dp.include_router(user_router)
publication_dp.include_router(statistics_router)
publication_dp.include_router(poll_router)
publication_dp.include_router(mini_app_router)

logger.info("📌 Все роутеры подключены к диспетчеру публикационного бота")

# Логирование зарегистрированных роутеров
logger.debug("Зарегистрированные роутеры:")


for router in publication_dp.sub_routers:
    logger.debug(f"- {router.name}")




async def init_db():
    """Инициализирует базу данных."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()  # Закрываем соединение после создания таблиц
    logger.info("✅ База данных инициализирована")


async def delete_webhook():
    """Удаляет вебхук перед запуском бота (если установлен)."""
    try:
        await publication_bot.delete_webhook()
        logger.info("✅ Вебхук публикационного бота успешно удалён")
    except Exception as e:
        logger.exception(f"❌ Ошибка при удалении вебхука публикационного бота: {e}")



async def setup_telegram_menu(bot: Bot):
    """Очистить все /команды и установить одну кнопку в меню – Web App."""
    await bot.set_my_commands([])
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Меню",
            web_app=WebAppInfo(url=WEBAPP_URL)  # Используем импортированную переменную
        )
    )
    logger.info("✅ Меню Telegram обновлено — одна кнопка запускает Web App.")





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

        await setup_telegram_menu(publication_bot)

        # Запуск публикационного бота
        await start_publication_bot()
    except Exception as e:
        logger.exception("❌ Ошибка в функции main")
    finally:
        logger.info("🛑 Завершение работы приложения...")


if __name__ == "__main__":
    asyncio.run(main())