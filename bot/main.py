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
from aiogram.types import MenuButtonWebApp, WebAppInfo, MenuButtonDefault
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bot.handlers.admin import router as admin_router
from bot.handlers.admin_menu import router as admin_menu_router
from bot.services.deletion_service import router as delete_task_router
from bot.handlers.poll_handler import router as poll_router
from bot.handlers.start import router as start_router
from bot.handlers.statistics_handler import router as statistics_router
from bot.handlers.test import router as test_router
from bot.handlers.upload_json import router as upload_json_router
from bot.handlers.user_handler import router as user_router
from bot.handlers.webhook_handler import router as webhook_router
from bot.handlers.webhook import router as webhook_handler_router
from bot.handlers.payment_handler import router as payment_router
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.user_middleware import UserMiddleware
from bot.handlers.feedback import router as feedback_router
from mini_app.app_handlers.handlers import router as mini_app_router
from bot.config import (
    TELEGRAM_BOT_TOKEN,
    DATABASE_URL
)
from database.database import Base
from mini_app.config import WEBAPP_URL

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
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
publication_dp.include_router(webhook_handler_router)
publication_dp.include_router(payment_router)  # Telegram Stars payments
publication_dp.include_router(test_router)
publication_dp.include_router(admin_router)
publication_dp.include_router(user_router)
publication_dp.include_router(statistics_router)
publication_dp.include_router(poll_router)
publication_dp.include_router(feedback_router)
publication_dp.include_router(mini_app_router)



# Логирование зарегистрированных роутеров и их обработчиков
logger.info("📌 Все роутеры подключены к диспетчеру публикационного бота")
logger.debug("Зарегистрированные роутеры:")
for router in publication_dp.sub_routers:
    logger.debug(f"- {router.name}")
    # Логируем зарегистрированные callback-обработчики для каждого роутера
    callback_handlers = [
        h for h in router.callback_query.handlers
        if h.callback.__name__ not in ["__call__"]  # Исключаем middleware
    ]
    for handler in callback_handlers:
        logger.debug(f"  Callback handler: {handler.callback.__name__}, filters: {handler.filters}")



async def init_db():
    """
    Инициализирует базу данных, создавая все таблицы, определённые в моделях SQLAlchemy.

    Raises:
        Exception: Если произошла ошибка при создании таблиц.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    logger.info("✅ База данных инициализирована")

async def delete_webhook():
    """
    Удаляет вебхук публикационного бота, если он установлен.

    Raises:
        Exception: Если произошла ошибка при удалении вебхука.
    """
    try:
        await publication_bot.delete_webhook()
        logger.info("✅ Вебхук публикационного бота успешно удалён")
    except Exception as e:
        logger.exception(f"❌ Ошибка при удалении вебхука публикационного бота: {e}")

async def setup_telegram_menu(bot: Bot):
    """
    Настраивает меню Telegram: очищает команды и устанавливает кнопку Web App.
    
    Сначала сбрасывает menu button на default, чтобы очистить кэш Telegram,
    затем устанавливает новую кнопку с актуальным URL.

    Args:
        bot (Bot): Экземпляр бота aiogram.

    Raises:
        Exception: Если произошла ошибка при настройке меню.
    """
    await bot.set_my_commands([])
    
    # Формируем корректный URL для страницы профиля (чтобы initData передавался)
    profile_url = f"{WEBAPP_URL}/profile"
    
    logger.info(f"🔗 Настройка меню Telegram с URL: {profile_url}")
    
    # Шаг 1: Сбрасываем menu button на default для всех чатов, чтобы очистить кэш Telegram
    logger.info("🧹 Сброс menu button на default для очистки кэша...")
    await bot.set_chat_menu_button(
        menu_button=MenuButtonDefault()
    )
    
    # Небольшая задержка для применения изменений на стороне Telegram
    await asyncio.sleep(0.5)
    
    # Шаг 2: Устанавливаем новый menu button с актуальным URL
    logger.info("🔧 Установка нового menu button с актуальным URL...")
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Профиль", # Изменим текст для ясности
            web_app=WebAppInfo(url=profile_url)
        )
    )
    
    # Шаг 3: Обновляем описание бота для кнопки "ОТКРЫТЬ" в списке чатов
    logger.info("📝 Обновление описания бота для кнопки в списке чатов...")
    try:
        await bot.set_my_description(description=f"Quiz Bot with Mini App: {WEBAPP_URL}")
        await bot.set_my_short_description(short_description="Quiz Bot with Mini App")
        logger.info("✅ Описание бота обновлено")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось обновить описание бота: {e}")
    
    logger.info("✅ Меню Telegram успешно настроено")
    logger.info(f"💡 Если кнопка не обновилась, перезапустите чат с ботом: /start")

async def start_publication_bot():
    """
    Запускает публикационного бота в режиме polling.

    Raises:
        Exception: Если произошла ошибка при запуске бота.
    """
    try:
        logger.info("🚀 Запуск публикационного бота с поллингом...")
        await publication_dp.start_polling(publication_bot)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске публикационного бота: {e}")
    finally:
        await asyncio.sleep(2)
        await publication_bot.close()
        logger.info("🛑 Публикационный бот остановлен")

async def main():
    """
    Главная функция для инициализации и запуска бота.

    Raises:
        Exception: Если произошла ошибка во время выполнения.
    """
    try:
        # Инициализация базы данных
        await init_db()

        # Удаление вебхука
        await delete_webhook()

        # Настройка меню Telegram
        await setup_telegram_menu(publication_bot)

        # Запуск бота
        await start_publication_bot()
    except Exception as e:
        logger.exception("❌ Ошибка в функции main")
    finally:
        logger.info("🛑 Завершение работы приложения...")

if __name__ == "__main__":
    asyncio.run(main())