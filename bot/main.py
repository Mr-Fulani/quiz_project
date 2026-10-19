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
from bot.tenancy import TenantContextMiddleware, load_bot_tenants, register_bot
import os

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Боты тенантов создаются в main() (по Tenant.bot_token из БД, см. bot/tenancy.py)

# Инициализация диспетчера публикационного бота (один на всех ботов)
publication_storage = MemoryStorage()
publication_dp = Dispatcher(storage=publication_storage)

# Настройка базы данных
engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# ------------------------------------------------------------------------
# Глобальная регистрация middleware (на все типы апдейтов):
# dp.update.middleware(...) — в Aiogram 3.x применится к любому Update.
# ------------------------------------------------------------------------
# Тенант определяется первым: от него зависят все запросы к БД в остальных middleware и хендлерах
publication_dp.update.outer_middleware(TenantContextMiddleware())
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

async def delete_webhook(bot: Bot):
    """
    Удаляет вебхук бота, если он установлен (бот работает через polling).
    """
    try:
        await bot.delete_webhook()
        logger.info(f"✅ Вебхук бота {bot.id} успешно удалён")
    except Exception as e:
        logger.exception(f"❌ Ошибка при удалении вебхука бота {bot.id}: {e}")

async def setup_telegram_menu(bot: Bot, webapp_url: str = WEBAPP_URL):
    """
    Настраивает меню Telegram: очищает команды и устанавливает кнопку Web App.
    
    Сначала сбрасывает menu button на default, чтобы очистить кэш Telegram,
    затем устанавливает новую кнопку с актуальным URL.
    
    Описание и краткое описание бота берутся из переменных окружения,
    чтобы не перезаписывать пользовательские настройки при каждом деплое.

    Args:
        bot (Bot): Экземпляр бота aiogram.

    Raises:
        Exception: Если произошла ошибка при настройке меню.
    """
    await bot.set_my_commands([])
    
    # Формируем URL для главной страницы мини-приложения (mini_app_domain тенанта бота)
    main_app_url = f"{webapp_url.rstrip('/')}/"
    
    logger.info(f"🔗 Настройка меню Telegram с URL: {main_app_url}")
    
    # Шаг 1: Сбрасываем menu button на default для всех чатов, чтобы очистить кэш Telegram
    logger.info("🧹 Сброс menu button на default для очистки кэша...")
    await bot.set_chat_menu_button(
        menu_button=MenuButtonDefault()
    )
    
    # Небольшая задержка для применения изменений на стороне Telegram
    await asyncio.sleep(0.5)
    
    # Шаг 2: Устанавливаем новый menu button с актуальным URL
    logger.info("🔧 Установка нового menu button с актуальным URL...")
    # Текст кнопки можно настроить через переменную окружения (по умолчанию: "Запустить приложение")
    menu_button_text = os.getenv('TELEGRAM_MENU_BUTTON_TEXT', 'Запустить приложение')
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text=menu_button_text,
            web_app=WebAppInfo(url=main_app_url)
        )
    )
    
    # Шаг 3: Обновляем описание бота только если указаны переменные окружения
    # Это позволяет сохранить пользовательские настройки, установленные через BotFather
    logger.info("📝 Проверка настроек описания бота...")
    try:
        # Получаем желаемые значения из переменных окружения
        # Если переменные не установлены, НЕ обновляем настройки, чтобы сохранить пользовательские значения
        desired_description = os.getenv('TELEGRAM_BOT_DESCRIPTION')
        desired_short_description = os.getenv('TELEGRAM_BOT_SHORT_DESCRIPTION')
        
        # Обновляем описание только если переменная окружения установлена
        if desired_description:
            logger.info(f"📝 Обновление описания бота из переменной окружения: {desired_description}")
            await bot.set_my_description(description=desired_description)
            logger.info("✅ Описание бота обновлено")
        else:
            logger.info("ℹ️  TELEGRAM_BOT_DESCRIPTION не установлена - используем существующие настройки")
            logger.info("   Установите TELEGRAM_BOT_DESCRIPTION в .env для автоматического обновления описания")
        
        # Обновляем краткое описание только если переменная окружения установлена
        if desired_short_description:
            logger.info(f"📝 Обновление краткого описания бота из переменной окружения: {desired_short_description}")
            await bot.set_my_short_description(short_description=desired_short_description)
            logger.info("✅ Краткое описание бота обновлено")
        else:
            logger.info("ℹ️  TELEGRAM_BOT_SHORT_DESCRIPTION не установлена - используем существующие настройки")
            logger.info("   Установите TELEGRAM_BOT_SHORT_DESCRIPTION в .env для автоматического обновления краткого описания")
        
        logger.info("✅ Настройки описания бота проверены")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось обновить описание бота: {e}")
        logger.warning("   Это нормально, если настройки уже установлены через BotFather")
    
    logger.info("✅ Меню Telegram успешно настроено")
    logger.info(f"💡 Если кнопка не обновилась, перезапустите чат с ботом: /start")

async def create_tenant_bots():
    """
    Создаёт ботов всех активных тенантов (Tenant.bot_token) и глобального TELEGRAM_BOT_TOKEN,
    регистрирует связь «бот → тенант» и настраивает каждому бота меню Mini App его тенанта.
    """
    pairs, tenants_by_id = await load_bot_tenants(async_session_maker, TELEGRAM_BOT_TOKEN)
    bots = []
    for token, tenant_id in pairs:
        try:
            bot = Bot(token=token)
        except Exception as e:
            logger.error(f"❌ Некорректный токен бота для тенанта {tenant_id}: {e}")
            continue
        register_bot(bot, tenant_id)
        tenant = tenants_by_id.get(tenant_id)
        webapp_url = f"https://{tenant.mini_app_domain}" if tenant and tenant.mini_app_domain else WEBAPP_URL
        await delete_webhook(bot)
        try:
            await setup_telegram_menu(bot, webapp_url)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось настроить меню бота {bot.id}: {e}")
        logger.info(f"✅ Бот {bot.id} запущен для тенанта {tenant.slug if tenant else '— (без тенанта)'}")
        bots.append(bot)
    return bots


async def start_publication_bot(bots):
    """
    Запускает ботов всех тенантов в режиме polling в одном диспетчере.
    """
    try:
        logger.info(f"🚀 Запуск {len(bots)} бот(ов) с поллингом...")
        await publication_dp.start_polling(*bots)
    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске ботов: {e}")
    finally:
        await asyncio.sleep(2)
        for bot in bots:
            await bot.session.close()
        logger.info("🛑 Боты остановлены")

async def main():
    """
    Главная функция для инициализации и запуска бота.

    Raises:
        Exception: Если произошла ошибка во время выполнения.
    """
    try:
        # Инициализация базы данных
        await init_db()

        # Боты тенантов: вебхуки сброшены, меню настроены
        bots = await create_tenant_bots()
        if not bots:
            logger.error("❌ Нет ни одного бота: задайте bot_token тенантам в админке или TELEGRAM_BOT_TOKEN")
            return

        # Запуск ботов
        await start_publication_bot(bots)
    except Exception as e:
        logger.exception("❌ Ошибка в функции main")
    finally:
        logger.info("🛑 Завершение работы приложения...")

if __name__ == "__main__":
    asyncio.run(main())