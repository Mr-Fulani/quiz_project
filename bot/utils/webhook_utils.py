# bot/services/webhook_utils.py

from datetime import datetime
from typing import Dict, Tuple

from bot.database.models import Group
from bot.handlers.webhook_handler import get_incorrect_answers


async def create_webhook_data(
    task_id: int,
    channel_username: str,
    poll_msg,  # Оставляем универсальный тип
    image_url: str,
    poll_message: Dict,
    translation,
    group: Group,
    image_message,  # Оставляем универсальный тип
    dont_know_option: str,
    external_link: str
) -> Tuple[Dict, str]:
    """
    Создаёт словарь данных для вебхука и возвращает poll_link отдельно.
    Добавляет task_id для возможности последующей проверки image_url.
    """
    # Проверка poll_msg на атрибуты
    message_id = poll_msg.get("message_id") if isinstance(poll_msg, dict) else getattr(poll_msg, "message_id", None)
    poll_link = f"https://t.me/{channel_username}/{message_id}"

    # Проверка image_message на атрибуты
    caption = image_message.get("caption", "") if isinstance(image_message, dict) else getattr(image_message, "caption", "")

    webhook_data = {
        "type": "quiz_published",
        "task_id": task_id,
        "poll_link": poll_link,
        "image_url": image_url,
        "question": poll_message["question"],
        "correct_answer": translation.correct_answer,
        "incorrect_answers": await get_incorrect_answers(translation.answers, translation.correct_answer),
        "language": translation.language,
        "group": {
            "id": group.id,
            "name": group.group_name
        },
        "caption": caption,
        "published_at": datetime.utcnow().isoformat()
    }

    # Добавляем "Не знаю, но хочу узнать" с локализованным текстом и ссылкой
    dont_know_with_link = f"{dont_know_option} ({external_link})"
    webhook_data["incorrect_answers"].append(dont_know_with_link)

    return webhook_data, poll_link



