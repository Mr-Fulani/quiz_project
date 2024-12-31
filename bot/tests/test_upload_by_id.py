import pytest
from bot.services.publication_service import publish_task_by_id
from bot.database.database import AsyncSessionMaker
import logging

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_publish_task_by_id():
    """Минимальный тест для функции publish_task_by_id."""

    task_id = 1  # Замените на реальный ID задачи или используйте фикстуру для её создания

    async with AsyncSessionMaker() as db_session:
        # Создаем тестовое сообщение, которое будет имитировать сообщение из бота
        class MockMessage:
            chat = type('chat', (), {"id": 12345})

            async def answer(self, text):
                logger.info(f"Ответ бота: {text}")

        # Создаем тестовый экземпляр бота
        class MockBot:
            async def send_photo(self, chat_id, photo, caption):
                logger.info(f"Отправка фото: {photo}, сообщение: {caption}")

        # Вызываем функцию публикации задачи
        message = MockMessage()
        bot = MockBot()

        success = await publish_task_by_id(task_id, message, db_session, bot)

        if success:
            logger.info(f"Задача с ID {task_id} успешно опубликована.")
        else:
            logger.error(f"Задача с ID {task_id} не опубликована.")