from datetime import datetime
from typing import Dict, Tuple

from bot.database.models import TelegramGroup
from bot.handlers.webhook_handler import get_incorrect_answers


async def create_webhook_data(
    task_id: int,
    channel_username: str,
    poll_msg,        # dict или объект Aiogram
    image_url: str,  # финальная ссылка на картинку
    poll_message: Dict,
    translation,
    group: TelegramGroup,
    image_message,   # dict или объект
    dont_know_option: str,
    external_link: str
) -> Tuple[Dict, str]:
    """
    Создаёт данные для вебхука на основе информации о задаче и опросе.

    Args:
        task_id (int): ID задачи.
        channel_username (str): Имя пользователя канала (например, '@ChannelName').
        poll_msg: Сообщение с опросом (dict или объект Aiogram).
        image_url (str): URL изображения задачи.
        poll_message (Dict): Данные сообщения с опросом.
        translation: Объект перевода задачи (содержит вопрос, ответы, язык).
        group (TelegramGroup): Объект группы/канала Telegram.
        image_message: Сообщение с изображением (dict или объект Aiogram).
        dont_know_option (str): Текст варианта "Не знаю".
        external_link (str): Внешняя ссылка для варианта "Не знаю".

    Returns:
        Tuple[Dict, str]: Словарь с данными для вебхука и ссылка на опрос.
    """
    message_id = None
    if isinstance(poll_msg, dict):
        message_id = poll_msg.get("message_id")
    else:
        # poll_msg может быть aiogram.types.Message / или Poll / etc.
        message_id = getattr(poll_msg, "message_id", None)

    poll_link = f"https://t.me/{channel_username}/{message_id}"

    if isinstance(image_message, dict):
        caption = image_message.get("caption", "")
    else:
        caption = getattr(image_message, "caption", "")

    # Список неправильных ответов (без правильного)
    incorrects = await get_incorrect_answers(translation.answers, translation.correct_answer)

    webhook_data = {
        "type": "quiz_published",
        "task_id": task_id,
        "poll_link": poll_link,
        "image_url": image_url,
        "question": poll_message["question"],
        "correct_answer": translation.correct_answer,
        "incorrect_answers": incorrects,  # без "не знаю"
        "language": translation.language,
        "group": {
            "id": group.id,
            "name": group.group_name
        },
        "caption": caption,
        "published_at": datetime.utcnow().isoformat()
    }

    # добавляем "не знаю" с ссылкой
    dont_know_with_link = f"{dont_know_option} ({external_link})"
    webhook_data["incorrect_answers"].append(dont_know_with_link)

    return webhook_data, poll_link