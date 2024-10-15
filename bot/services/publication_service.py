import logging
from datetime import datetime
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import Task
from bot.services.image_service import generate_image_if_needed



logger = logging.getLogger(__name__)


async def publish_task_by_id(task_id: int, message, db_session: AsyncSession, bot: Bot):
    """
    Публикует задачу по её ID. Генерирует изображение, отправляет сообщение с текстом и картинкой в Telegram.
    """
    try:
        # Логируем начало публикации задачи
        logger.info(f"Начало публикации задачи с ID {task_id}")

        # Получаем задачу из базы данных
        logger.info("Попытка выполнить запрос к базе данных для получения задачи.")
        logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
        result = await db_session.execute(
            select(Task)
            .options(
                joinedload(Task.translations),  # Жадная загрузка translations
                joinedload(Task.topic),  # Жадная загрузка topic
                joinedload(Task.subtopic),  # Жадная загрузка subtopic
                joinedload(Task.group)  # Жадная загрузка group
            )
            .where(Task.id == task_id)
        )
        logger.info("Запрос выполнен успешно, извлечение данных задачи.")
        task = result.unique().scalar_one_or_none()

        if task is None:
            logger.error(f"Задача с ID {task_id} не найдена.")
            await message.answer(f"Задача с ID {task_id} не найдена.")
            return False

        if task.published:
            logger.info(f"Задача с ID {task_id} уже была опубликована.")
            await message.answer(f"Задача с ID {task_id} уже опубликована.")
            return False

        # Проверка привязки задачи к группе
        if not task.group:
            logger.error(f"Группа для задачи с ID {task_id} не указана.")
            await message.answer("Группа для задачи не найдена.")
            return False

        # Ищем перевод на 'ru', если его нет, берем первый доступный перевод
        logger.info(f"Поиск перевода задачи с ID {task_id}.")
        translation = next((t for t in task.translations if t.language == 'ru'), None)
        if not translation:
            translation = task.translations[0] if task.translations else None

        if not translation or not translation.question:
            logger.error(f"Перевод или текст задачи с ID {task_id} не найден.")
            await message.answer("Перевод задачи или текст вопроса не найден.")
            return False

        task_text = translation.question  # Извлекаем текст задачи
        logger.info(f"Текст задачи: {task_text}")

        # Генерация изображения для задачи, если нужно
        logger.info(f"Попытка сгенерировать изображение для задачи с ID {task_id}.")
        image_url = await generate_image_if_needed(task)
        if not image_url:
            logger.error(f"Ошибка при генерации изображения для задачи с ID {task_id}.")
            await message.answer("Ошибка при генерации изображения.")
            return False

        # Формируем сообщение для отправки в Telegram
        logger.info(f"Формирование сообщения для отправки в Telegram для задачи с ID {task_id}.")
        message_text = f"{task_text}\n\nСсылка на ресурс: {task.external_link}"

        if len(message_text) > 4096:
            logger.error(f"Сообщение для задачи с ID {task_id} превышает лимит символов Telegram (4096).")
            await message.answer("Сообщение слишком длинное для публикации.")
            return False

        # Публикуем сообщение в группу
        logger.info(f"Попытка отправить сообщение в группу {task.group.group_name} с ID {task.group.group_id}.")
        await bot.send_photo(
            chat_id=task.group.group_id,
            photo=task.image_url,
            caption=message_text
        )
        logger.info(f"Сообщение для задачи с ID {task_id} успешно отправлено в группу {task.group.group_name}.")

        # Обновляем статус задачи на "опубликована"
        task.published = True
        task.publish_date = datetime.now()

        logger.info(f"Попытка зафиксировать транзакцию в базе данных для задачи с ID {task_id}.")
        logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
        await db_session.commit()
        logger.info(f"Транзакция выполнена успешно для задачи с ID {task_id}.")

        await message.answer(f"Задача с ID {task_id} успешно опубликована.")
        logger.info(f"Задача с ID {task_id} успешно опубликована.")
        return True

    except Exception as e:
        logger.error(f"Ошибка при публикации задачи с ID {task_id}: {e}")
        logger.info(f"db_session is async: {isinstance(db_session, AsyncSession)}")
        await db_session.rollback()
        logger.error(f"Выполнен откат транзакции для задачи с ID {task_id}.")
        await message.answer("Ошибка при публикации задачи.")
        return False