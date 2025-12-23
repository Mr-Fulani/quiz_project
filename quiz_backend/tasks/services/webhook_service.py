import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from django.utils import timezone
from django.conf import settings
from urllib.parse import urlparse, urlunparse

from tasks.models import Task
from .default_link_service import DefaultLinkService
from webhooks.models import GlobalWebhookLink

logger = logging.getLogger(__name__)


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    """Возвращает ISO-представление даты или None при отсутствии."""
    return value.isoformat() if value else None


def _normalize_answers(answers: Any) -> List[str]:
    """Гарантирует список ответов независимо от формата хранения."""
    if isinstance(answers, str):
        try:
            parsed = json.loads(answers)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    if isinstance(answers, Iterable):
        return [str(answer) for answer in answers]
    return []


def _get_incorrect_answers(answers: Any, correct_answer: str) -> List[str]:
    """Возвращает все варианты ответа, кроме правильного."""
    normalized = _normalize_answers(answers)
    return [option for option in normalized if option != correct_answer]


def _build_topic_payload(task: Task) -> Optional[Dict[str, Any]]:
    """Формирует информацию о теме задачи."""
    if not task.topic:
        return None
    return {
        "id": task.topic.id,
        "name": task.topic.name,
    }


def _build_subtopic_payload(task: Task) -> Optional[Dict[str, Any]]:
    """Формирует информацию о подтеме, если она задана."""
    if not task.subtopic:
        return None
    return {
        "id": task.subtopic.id,
        "name": task.subtopic.name,
    }


def _build_group_payload(task: Task) -> Optional[Dict[str, Any]]:
    """Формирует информацию о группе/канале Telegram."""
    group = task.group
    if not group:
        return None

    return {
        "id": group.id,
        "group_name": group.group_name,
        "group_id": group.group_id,
        "username": group.username,
        "language": group.language,
        "location_type": group.location_type,
    }


def _build_poll_payload(poll) -> Dict[str, Any]:
    """Сериализует объект опроса TaskPoll."""
    return {
        "poll_id": poll.poll_id,
        "poll_question": poll.poll_question,
        "poll_options": poll.poll_options,
        "is_anonymous": poll.is_anonymous,
        "poll_type": poll.poll_type,
        "allows_multiple_answers": poll.allows_multiple_answers,
        "total_voter_count": poll.total_voter_count,
        "poll_link": poll.poll_link,
    }


def _build_translations_payload(task: Task) -> List[Dict[str, Any]]:
    """Формирует список переводов с расширенными данными и опросами."""
    translations_payload: List[Dict[str, Any]] = []

    translations = task.translations.all()
    for translation in translations:
        poll_manager = getattr(translation, "taskpoll_set", None)
        polls = []
        if poll_manager is not None:
            polls = [_build_poll_payload(poll) for poll in poll_manager.all()]
        translation_payload = {
            "id": translation.id,
            "language": translation.language,
            "question": translation.question,
            "answers": _normalize_answers(translation.answers),
            "correct_answer": translation.correct_answer,
            "incorrect_answers": _get_incorrect_answers(translation.answers, translation.correct_answer),
            "explanation": translation.explanation,
            "publish_date": _serialize_datetime(translation.publish_date),
            "polls": polls,
        }

        translations_payload.append(translation_payload)

    return translations_payload


def create_full_webhook_data(task: Task) -> Dict[str, Any]:
    """
    Формирует полный полезный груз вебхука для задачи.

    Включает информацию об основной задаче, теме, переводах и опросах.
    """
    logger.debug("Формируем данные вебхука для задачи %s", task.id)

    # Конструируем URL для вебхука с учетом окружения
    image_url = task.image_url
    if image_url and not settings.DEBUG and settings.AWS_PUBLIC_MEDIA_DOMAIN:
        try:
            parsed_url = urlparse(image_url)
            # Заменяем домен на продакшен-домен
            prod_url_parts = parsed_url._replace(netloc=settings.AWS_PUBLIC_MEDIA_DOMAIN)
            image_url = urlunparse(prod_url_parts)
        except Exception as e:
            logger.error(f"Ошибка при формировании URL изображения для вебхука: {e}")
            # В случае ошибки оставляем как есть

    payload = {
        "type": "quiz_published_full",
        "id": str(uuid.uuid4()),
        "timestamp": timezone.now().isoformat(),
        "task": {
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
            "topic": _build_topic_payload(task),
            "subtopic": _build_subtopic_payload(task),
            "group": _build_group_payload(task),
        },
        "translations": _build_translations_payload(task),
    }

    # Добавляем external_link, если его нет
    if not payload["task"]["external_link"]:
        translation = task.translations.first()
        if translation:
            final_link, _ = DefaultLinkService.get_final_link(task, translation)
            payload["task"]["external_link"] = final_link
            logger.debug("Добавлена автоматическая external_link: %s", final_link)

    logger.debug("Готовый полезный груз вебхука для задачи %s: %s", task.id, payload)
    return payload


def create_russian_only_webhook_data(tasks: List[Task]) -> Dict[str, Any]:
    """
    Формирует payload для вебхука с данными только на русском языке.
    """
    logger.debug("Формируем русский вебхук для %s задач", len(tasks))

    tasks_payload = []
    for task in tasks:
        full_data = create_full_webhook_data(task)
        # Фильтруем переводы, оставляя только русский язык
        russian_translations = [trans for trans in full_data.get("translations", []) if trans.get("language") == "ru"]
        if russian_translations:  # Отправляем задачу только если есть русский перевод
            tasks_payload.append({
                "task": full_data.get("task"),
                "translations": russian_translations
            })

    # Get global custom links
    global_links = GlobalWebhookLink.objects.filter(is_active=True).values('name', 'url')

    bulk_payload = {
        "type": "quiz_published_russian_only",
        "id": str(uuid.uuid4()),
        "timestamp": timezone.now().isoformat(),
        "published_tasks": tasks_payload,
        "global_custom_links": list(global_links),
    }

    logger.debug("Русский payload готов.")
    return bulk_payload


def create_english_only_webhook_data(tasks: List[Task]) -> Dict[str, Any]:
    """
    Формирует payload для вебхука с данными только на английском языке.
    """
    logger.debug("Формируем английский вебхук для %s задач", len(tasks))

    tasks_payload = []
    for task in tasks:
        full_data = create_full_webhook_data(task)
        # Фильтруем переводы, оставляя только английский язык
        english_translations = [trans for trans in full_data.get("translations", []) if trans.get("language") == "en"]
        if english_translations:  # Отправляем задачу только если есть английский перевод
            tasks_payload.append({
                "task": full_data.get("task"),
                "translations": english_translations
            })

    # Get global custom links
    global_links = GlobalWebhookLink.objects.filter(is_active=True).values('name', 'url')

    bulk_payload = {
        "type": "quiz_published_english_only",
        "id": str(uuid.uuid4()),
        "timestamp": timezone.now().isoformat(),
        "published_tasks": tasks_payload,
        "global_custom_links": list(global_links),
    }

    logger.debug("Английский payload готов.")
    return bulk_payload


def create_bulk_webhook_data(tasks: List[Task]) -> Dict[str, Any]:
    """
    Формирует агрегированный payload для списка опубликованных задач.
    """
    logger.debug("Формируем сводный вебхук для %s задач", len(tasks))

    tasks_payload = []
    for task in tasks:
        full_data = create_full_webhook_data(task)
        # Убираем внешнюю обертку, оставляя только 'task' и 'translations'
        tasks_payload.append({
            "task": full_data.get("task"),
            "translations": full_data.get("translations")
        })

    # Get global custom links
    global_links = GlobalWebhookLink.objects.filter(is_active=True).values('name', 'url')

    bulk_payload = {
        "type": "quiz_published_bulk",
        "id": str(uuid.uuid4()),
        "timestamp": timezone.now().isoformat(),
        "published_tasks": tasks_payload,
        "global_custom_links": list(global_links),
    }

    logger.debug("Сводный payload готов.")
    return bulk_payload

