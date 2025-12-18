# bot/utils/webhook_utils.py

import json
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any

import pytz
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import TaskTranslation, TelegramGroup, Task, Topic, Subtopic, GlobalWebhookLink, TaskPoll
from sqlalchemy import select
from bot.settings import get_settings

logger = logging.getLogger(__name__)


async def create_bulk_webhook_data(tasks: List[Task], db_session: AsyncSession) -> Dict[str, Any]:
    """
    Создает сводный payload для вебхука, аналогично Django.
    """
    logger.debug("Формируем сводный вебхук для %s задач", len(tasks))
    tasks_payload = []

    for task in tasks:
        full_data = await create_full_webhook_data_for_task(task, db_session)
        tasks_payload.append({
            "task": full_data.get("task"),
            "translations": full_data.get("translations")
        })

    # Получаем глобальные ссылки
    result = await db_session.execute(
        select(GlobalWebhookLink).where(GlobalWebhookLink.is_active == True)
    )
    global_links_db = result.scalars().all()
    global_links_payload = [{"name": link.name, "url": link.url} for link in global_links_db]

    bulk_payload = {
        "type": "quiz_published_bulk",
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(tz=pytz.utc).isoformat(),
        "published_tasks": tasks_payload,
        "global_custom_links": global_links_payload,
    }
    logger.debug("Сводный payload готов.")
    return bulk_payload


def _serialize_datetime(value: datetime) -> str | None:
    return value.isoformat() if value else None


def _normalize_answers(answers: Any) -> List[str]:
    if isinstance(answers, str):
        try:
            return json.loads(answers)
        except json.JSONDecodeError:
            return []
    return list(answers) if answers else []


def _get_incorrect_answers(answers: Any, correct_answer: str) -> List[str]:
    normalized_answers = _normalize_answers(answers)
    return [ans for ans in normalized_answers if ans != correct_answer]


async def create_full_webhook_data_for_task(task: Task, db_session: AsyncSession) -> Dict[str, Any]:
    """
    Создает полный payload для одной задачи, включая все ее переводы.
    """
    settings = get_settings()

    # Формируем URL изображения с учетом окружения
    image_url = task.image_url
    if image_url and not settings.DEBUG and settings.AWS_PUBLIC_MEDIA_DOMAIN:
        # В боте image_url уже полный, но может быть не от того бакета
        # Просто заменяем домен
        from urllib.parse import urlparse, urlunparse
        try:
            parsed_url = urlparse(image_url)
            prod_url_parts = parsed_url._replace(netloc=settings.AWS_PUBLIC_MEDIA_DOMAIN)
            image_url = urlunparse(prod_url_parts)
        except Exception as e:
            logger.error(f"Ошибка при формировании URL изображения для вебхука (бот): {e}")

    task_payload = {
        "id": task.id,
        "difficulty": task.difficulty,
        "published": task.published,
        "create_date": _serialize_datetime(task.create_date),
        "publish_date": _serialize_datetime(task.publish_date),
        "image_url": image_url,
        "external_link": task.external_link,
        "video_url": task.video_url,
        "translation_group_id": str(task.translation_group_id),
        "message_id": task.message_id,
        "error": task.error,
        "topic": {"id": task.topic.id, "name": task.topic.name} if task.topic else None,
        "subtopic": {"id": task.subtopic.id, "name": task.subtopic.name} if task.subtopic else None,
        "group": {
            "id": task.group.id,
            "group_name": task.group.group_name,
            "group_id": task.group.group_id,
            "username": task.group.username,
            "language": task.group.language,
            "location_type": task.group.location_type,
        } if task.group else None,
    }

    translations_payload = []
    # Загружаем все опросы для задачи явно через db_session
    polls_result = await db_session.execute(
        select(TaskPoll).where(TaskPoll.task_id == task.id)
    )
    all_polls = polls_result.scalars().all()
    
    for trans in task.translations:
        polls_payload = []
        # Фильтруем опросы по translation_id
        for poll in all_polls:
            if poll.translation_id == trans.id:
                polls_payload.append({
                    "id": poll.id,
                    "poll_id": poll.poll_id,
                    "poll_question": poll.poll_question,
                    "poll_link": poll.poll_link,
                })

        translations_payload.append({
            "id": trans.id,
            "language": trans.language,
            "question": trans.question,
            "answers": _normalize_answers(trans.answers),
            "correct_answer": trans.correct_answer,
            "incorrect_answers": _get_incorrect_answers(trans.answers, trans.correct_answer),
            "explanation": trans.explanation,
            "publish_date": _serialize_datetime(trans.publish_date),
            "polls": polls_payload,
        })
    
    return {
        "task": task_payload,
        "translations": translations_payload,
    }