# bot/services/webhook_utils.py

from datetime import datetime
from typing import Dict, Tuple

from bot.database.models import Group


async def create_webhook_data(
    task_id: int,  # Добавляем task_id
    channel_username: str,
    poll_msg: Dict,  # Предполагается, что это словарь с ключами, например, message_id
    image_url: str,
    poll_message: Dict,
    translation,
    group: Group,
    image_message: Dict,
    dont_know_option: str,
    external_link: str
) -> Tuple[Dict, str]:
    """
    Создаёт словарь данных для вебхука и возвращает poll_link отдельно.
    Добавляет task_id для возможности последующей проверки image_url.
    """
    poll_link = f"https://t.me/{channel_username}/{poll_msg.get('message_id')}"
    webhook_data = {
        "type": "quiz_published",
        "task_id": task_id,  # Включаем task_id
        "poll_link": poll_link,
        "image_url": image_url,  # Остаётся строкой URL
        "question": poll_message["question"],
        "correct_answer": translation.correct_answer,
        "incorrect_answers": poll_message["incorrect_answers"],
        "language": translation.language,
        "group": {
            "id": group.id,
            "name": group.name
        },
        "caption": image_message.get("caption", ""),
        "published_at": datetime.utcnow().isoformat()
    }

    # Добавляем "Не знаю, но хочу узнать" с локализованным текстом и ссылкой
    dont_know_with_link = f"{dont_know_option} ({external_link})"
    webhook_data["incorrect_answers"].append(dont_know_with_link)

    return webhook_data, poll_link



