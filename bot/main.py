import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import image_sender
from bot.handlers import start, admin_menu, upload_json, delete_task  # Импортируем start.py
import asyncio

from bot.middlewares.db_session import DbSessionMiddleware
from config import BOT_TOKEN, WEBHOOK_BOT_TOKEN

from sqlalchemy.orm import configure_mappers




# Настройка логирования
logging.basicConfig(level=logging.DEBUG)  # Для более подробных логов
logger = logging.getLogger(__name__)




# Пересоздание маппинга моделей
configure_mappers()




# Инициализация бота
bot = Bot(token=BOT_TOKEN)
webhook_bot = Bot(token=WEBHOOK_BOT_TOKEN)
storage = MemoryStorage()



# Инициализация диспетчера с хранилищем
dp = Dispatcher(storage=MemoryStorage())



# Подключаем Middleware для передачи сессии базы данных
dp.update.middleware(DbSessionMiddleware())



# Регистрация маршрутизаторов
dp.include_router(start.router)
dp.include_router(admin_menu.router)
dp.include_router(delete_task.router)
dp.include_router(upload_json.router)
dp.include_router(image_sender.router)



async def main():
    logger.info("Бот запущен и готов к работе...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())





