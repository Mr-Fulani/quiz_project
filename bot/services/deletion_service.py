import logging
from typing import Optional, Dict, Any

import aioboto3
from aiogram import Router
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import S3_BUCKET_NAME, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
from bot.database.models import Task, Topic, TaskTranslation, TaskPoll, TelegramGroup
from bot.services.s3_services import extract_s3_key_from_url


# Настройка логгера
logger = logging.getLogger(__name__)


# Создание роутера
router = Router()



async def delete_from_s3(image_url: str) -> bool:
    """
    Удаляет изображение из S3 хранилища по указанному URL.

    Args:
        image_url (str): URL изображения в S3.

    Returns:
        bool: True, если удаление успешно, иначе False.
    """
    try:
        if not image_url:
            return True

        s3_key = extract_s3_key_from_url(image_url)
        if not s3_key:
            logger.warning("Не удалось извлечь ключ S3 из URL")
            return False

        session = aioboto3.Session()
        async with session.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=S3_REGION
        ) as s3:
            await s3.delete_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key
            )
            logger.info(f"✅ Изображение успешно удалено из S3: {s3_key}")
            return True

    except Exception as e:
        logger.error(f"❌ Ошибка при удалении изображения из S3: {e}")
        return False



async def delete_task_by_id(task_id: int, db_session: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Удаляет задачу, её переводы, опросы и изображения из S3.

    Args:
        task_id (int): ID задачи для удаления.
        db_session (AsyncSession): Асинхронная сессия SQLAlchemy.

    Returns:
        Optional[Dict[str, Any]]: Информация об удалённых данных или None, если задача не найдена.

    Raises:
        Exception: Если произошла ошибка при удалении.
    """
    try:
        # Начинаем транзакцию
        async with db_session.begin():
            # Получаем информацию о задаче
            task_query = select(Task.id, Task.topic_id, Task.translation_group_id, Task.image_url).where(
                Task.id == task_id)
            task_result = await db_session.execute(task_query)
            task_info = task_result.first()

            if not task_info:
                logger.warning(f"Задача с ID {task_id} не найдена")
                return None

            task_id, topic_id, translation_group_id, image_url = task_info
            logger.debug(
                f"ID группы переводов: {translation_group_id}, ID топика: {topic_id}, URL изображения: {image_url}")

            # Получаем связанные задачи
            related_tasks_query = select(Task.id, Task.group_id, Task.image_url).where(
                Task.translation_group_id == translation_group_id
            )
            related_tasks_result = await db_session.execute(related_tasks_query)
            related_tasks = related_tasks_result.fetchall()
            deleted_task_ids = [task.id for task in related_tasks]

            # Собираем URL изображений
            image_urls = [task.image_url for task in related_tasks if task.image_url]
            logger.debug(f"Найдены URL изображений для удаления: {image_urls}")

            # Получаем название топика
            topic_query = select(Topic.name).where(Topic.id == topic_id)
            topic_result = await db_session.execute(topic_query)
            topic_name = topic_result.scalar()

            # Получаем переводы
            translations_query = select(TaskTranslation.id, TaskTranslation.language).where(
                TaskTranslation.task_id.in_(deleted_task_ids)
            )
            translations_result = await db_session.execute(translations_query)
            translations = translations_result.fetchall()
            deleted_translation_ids = [tr.id for tr in translations]
            translation_languages = [tr.language for tr in translations]

            # Получаем названия групп
            group_ids = [task.group_id for task in related_tasks]
            groups_query = select(TelegramGroup.group_name).where(TelegramGroup.id.in_(group_ids))
            groups_result = await db_session.execute(groups_query)
            group_names = [group[0] for group in groups_result.fetchall()]

            # Удаляем опросы
            polls_query = select(TaskPoll.id).where(TaskPoll.translation_id.in_(deleted_translation_ids))
            polls_result = await db_session.execute(polls_query)
            poll_ids = [poll.id for poll in polls_result.fetchall()]

            if poll_ids:
                await db_session.execute(
                    TaskPoll.__table__.delete().where(TaskPoll.id.in_(poll_ids))
                )
                logger.info(f"✅ Опросы с ID {poll_ids} успешно удалены.")

            # Удаляем переводы
            await db_session.execute(
                TaskTranslation.__table__.delete().where(TaskTranslation.id.in_(deleted_translation_ids))
            )
            logger.info(f"✅ Переводы с ID {deleted_translation_ids} успешно удалены.")

            # Удаляем задачи
            await db_session.execute(
                Task.__table__.delete().where(Task.translation_group_id == translation_group_id)
            )
            logger.info(f"✅ Задачи с ID {deleted_task_ids} успешно удалены.")

            # Удаляем изображения из S3
            deleted_images = []
            for img_url in image_urls:
                if await delete_from_s3(img_url):
                    deleted_images.append(img_url)
                    logger.info(f"🗑️ Изображение успешно удалено из S3: {img_url}")
                else:
                    logger.warning(f"⚠️ Не удалось удалить изображение из S3: {img_url}")

            logger.info(f"✅ Транзакция по удалению задачи {task_id} успешно завершена.")

            deletion_info = {
                'deleted_task_ids': deleted_task_ids,
                'topic_name': topic_name,
                'deleted_translation_count': len(deleted_translation_ids),
                'deleted_translation_languages': translation_languages,
                'group_names': group_names,
                'deleted_images': deleted_images
            }
            logger.debug(f"Информация об удалении: {deletion_info}")

            return deletion_info

    except Exception as e:
        logger.error(f"❌ Ошибка при удалении задачи: {e}")
        raise

