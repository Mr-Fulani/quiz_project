# bot/handlers/test.py

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command(commands=["test"]))
async def test_handler(message: Message):
    logger.info("Обработчик /test вызван")
    try:
        await message.answer("🔧 Это тестовое сообщение.")
        logger.debug("Тестовое сообщение отправлено")
    except Exception as e:
        logger.exception(f"Ошибка при отправке тестового сообщения: {e}")