import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from datetime import datetime
import json
import re
from typing import Optional, List, Union

from bot.utils.db_utils import fetch_one
from bot.database.models import TaskTranslation, TelegramGroup, Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = Router()


async def get_task_translations(task_id: int, session: AsyncSession) -> list:
    """
    Получает все переводы для указанной задачи по её ID.

    Args:
        task_id (int): ID задачи.
        session (AsyncSession): Асинхронная сессия SQLAlchemy.

    Returns:
        list: Список объектов TaskTranslation, связанных с задачей.
    """
    query = select(TaskTranslation).where(TaskTranslation.task_id == task_id)
    translations = (await session.execute(query)).scalars().all()
    return translations


async def get_channel_info(chat_id: int, session: AsyncSession) -> Optional[dict]:
    """
    Получает информацию о канале или группе по их Telegram ID.

    Args:
        chat_id (int): Telegram ID канала или группы.
        session (AsyncSession): Асинхронная сессия SQLAlchemy.

    Returns:
        Optional[dict]: Словарь с данными о канале/группе (id, name) или None, если не найдено.
    """
    query = select(TelegramGroup).where(TelegramGroup.group_id == chat_id)
    group = await fetch_one(session, query)
    if group:
        return {
            "id": group.group_id,
            "name": group.group_name
        }
    return None


async def get_incorrect_answers(answers: Union[str, list], correct_answer: str) -> List[str]:
    """
    Извлекает неверные ответы из списка или JSON-строки, исключая правильный ответ.

    Args:
        answers (Union[str, list]): Список ответов или строка в формате JSON.
        correct_answer (str): Правильный ответ для фильтрации.

    Returns:
        List[str]: Список неверных ответов.
    """
    if isinstance(answers, str):
        try:
            answers = json.loads(answers)
        except json.JSONDecodeError:
            return []
    return [a for a in answers if a != correct_answer]


@router.channel_post(F.photo & F.caption)
async def handle_photo_with_caption(message: Message, bot: Bot, db_session: AsyncSession):
    """
    Обрабатывает сообщение с изображением и подписью.
    Поскольку вебхуки отправляются из функций публикации, здесь их отправка не требуется.
    """
    try:
        logger.info(f"📩 Обработка message_id: {message.message_id} из chat_id: {message.chat.id}")

        # Извлечение подписи
        caption = message.caption

        # Извлечение task_id из подписи с использованием регулярного выражения
        match = re.search(r'Task ID:\s*(\d+)', caption)
        if not match:
            logger.warning(f"⚠️ Task ID не найден в подписи message_id: {message.message_id}")
            return

        task_id = int(match.group(1))

        # Получение задачи по task_id
        query = select(Task).where(Task.id == task_id)
        task = await fetch_one(db_session, query)
        if not task:
            logger.warning(f"⚠️ Задача не найдена для task_id: {task_id}")
            return

        logger.info(f"✅ Задача найдена: {task.id} (message_id: {task.message_id})")

        # Получение всех переводов задачи
        translations = await get_task_translations(task.id, db_session)
        if not translations:
            logger.warning(f"⚠️ Переводы не найдены для task_id: {task.id}")
            return

        logger.info(f"📚 Найдено {len(translations)} переводов для task_id: {task.id}")

        # Получение информации о канале
        channel_info = await get_channel_info(message.chat.id, db_session)
        if not channel_info:
            logger.warning(f"⚠️ Информация о канале не найдена для chat_id: {message.chat.id}")
            channel_info = {"id": message.chat.id, "name": "Unknown Channel"}

        logger.info(f"📝 Информация о канале: {channel_info}")

        # Проверка наличия username у канала
        chat_username = message.chat.username
        if not chat_username:
            logger.error("❌ Username канала не найден. Убедитесь, что канал публичный и имеет username.")
            raise ValueError("Username канала не найден. Канал должен быть публичным и иметь установленный username.")

        # Формирование ссылки на сообщение
        poll_link = f"https://t.me/{chat_username}/{message.message_id}"
        logger.debug(f"🔗 Сформированная poll_link: {poll_link}")

        # Здесь нет необходимости отправлять вебхуки, так как они отправляются из функций публикации

    except Exception as e:
        logger.exception(f"❌ Ошибка при обработке message_id: {message.message_id} из chat_id: {message.chat.id}")

        # Попытка получить информацию о канале, если она была ранее определена
        channel_name = channel_info["name"] if 'channel_info' in locals() and channel_info else "Unknown Channel"

        # Формирование данных об ошибке
        error_data = {
            "type": "error",
            "error": str(e),
            "chat_id": message.chat.id,
            "channel_name": channel_name,
            "message_id": message.message_id,
            "caption": message.caption or "",
            "create_date": datetime.utcnow().isoformat()
        }

        # Логирование информации об ошибке
        logger.error(f"❌ Ошибка при обработке сообщения:\n{json.dumps(error_data, ensure_ascii=False, indent=2)}")