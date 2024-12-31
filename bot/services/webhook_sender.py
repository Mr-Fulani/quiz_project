# webhook_sender.py

import asyncio
import json
import logging
import ssl
import uuid
from typing import Dict

import aiohttp
import certifi
from aiogram import Bot

from bot.utils.markdownV2 import escape_markdown
from bot.utils.url_validator import is_valid_url
from bot.config import MAKE_WEBHOOK_TIMEOUT, MAKE_WEBHOOK_RETRIES, MAKE_WEBHOOK_RETRY_DELAY

logger = logging.getLogger(__name__)







async def notify_admin(bot: Bot, admin_chat_id: int, message: str):
    """
    Отправляет сообщение администратору с экранированием MarkdownV2.
    """
    try:
        escaped_message = escape_markdown(message)
        await bot.send_message(admin_chat_id, escaped_message, parse_mode="MarkdownV2")
        logger.info(f"Уведомление отправлено администратору {admin_chat_id}.")
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение администратору {admin_chat_id}: {e}")


async def send_quiz_published_webhook(webhook_url: str, data: Dict) -> bool:
    """
    Отправляет данные о опубликованном опросе на указанный URL вебхука.
    """
    try:
        required_fields = [
            "type", "poll_link", "image_url", "question",
            "correct_answer", "incorrect_answers", "language",
            "group", "caption", "published_at"
        ]

        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"❌ Отсутствуют необходимые поля в данных вебхука: {missing_fields}")
            return False

        if not (is_valid_url(data.get("poll_link", "")) and is_valid_url(data.get("image_url", ""))):
            logger.error(
                f"❌ Некорректные URL в данных вебхука: "
                f"poll_link={data.get('poll_link')}, image_url={data.get('image_url')}"
            )
            return False

        # Обработка incorrect_answers
        if "incorrect_answers" in data:
            if isinstance(data["incorrect_answers"], str):
                try:
                    # Попытка преобразовать строку JSON в список
                    data["incorrect_answers"] = json.loads(data["incorrect_answers"])
                except json.JSONDecodeError:
                    # Если строка не является JSON, разделяем по разделителю
                    # Предполагаем, что ответы разделены переносом строки или запятой
                    answers = data["incorrect_answers"].split('\n') if '\n' in data["incorrect_answers"] else data["incorrect_answers"].split(',')
                    # Очищаем от пробелов и пустых строк
                    data["incorrect_answers"] = [ans.strip() for ans in answers if ans.strip()]
            elif isinstance(data["incorrect_answers"], list):
                # Если это уже список, оставляем как есть
                pass
            else:
                # Если это что-то другое, преобразуем в пустой список
                logger.warning(f"Неподдерживаемый формат incorrect_answers: {type(data['incorrect_answers'])}")
                data["incorrect_answers"] = []

        logger.info(f"📤 Подготовка отправки вебхука на {webhook_url} для языка {data.get('language')}")
        logger.debug(f"📤 Данные вебхука:\n{json.dumps(data, ensure_ascii=False, indent=2)}")

        headers = {
            'Content-Type': 'application/json',
            'X-Request-ID': str(uuid.uuid4()),
            'X-Webhook-ID': data.get('id', ''),
            'X-Webhook-Sequence': f"{data.get('sequence_number', 0)}/{data.get('total_webhooks', 0)}",
            'X-Webhook-Batch': data.get('webhook_batch_id', ''),
            'X-Webhook-Language': data.get('language', '')
        }

        success = await send_webhook(webhook_url, data, headers)

        if success:
            logger.info(
                f"✅ Вебхук успешно отправлен на {webhook_url} для языка '{data.get('language', 'Unknown')}' (ID: {data.get('id')})"
            )
        else:
            logger.error(
                f"❌ Вебхук не удалось отправить на {webhook_url} для языка '{data.get('language', 'Unknown')}' (ID: {data.get('id')})"
            )

        return success

    except Exception as e:
        logger.exception(
            f"❌ Ошибка при подготовке вебхука для языка '{data.get('language', 'Unknown')}' (ID: {data.get('id')}): {e}"
        )
        return False


async def send_webhook(webhook_url: str, data: Dict, headers: Dict) -> bool:
    """
    Отправляет данные на внешний вебхук.
    """
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=MAKE_WEBHOOK_TIMEOUT),
            connector=aiohttp.TCPConnector(ssl=ssl_context)
    ) as session:
        for attempt in range(1, MAKE_WEBHOOK_RETRIES + 1):
            try:
                logger.info(
                    f"📤 Попытка {attempt}/{MAKE_WEBHOOK_RETRIES} отправки вебхука на {webhook_url}"
                )

                async with session.post(webhook_url, json=data, headers=headers) as response:
                    response_text = await response.text()

                    logger.info(f"📨 Webhook response from {webhook_url}:")
                    logger.info(f"Status: {response.status}")
                    logger.info(f"Headers: {dict(response.headers)}")
                    logger.info(f"Body: {response_text}")

                    if response.status in [200, 201, 202, 204]:
                        return True

            except Exception as e:
                logger.exception(
                    f"❌ Попытка {attempt} не удалась для вебхука на {webhook_url}: {e}"
                )

            if attempt < MAKE_WEBHOOK_RETRIES:
                delay = MAKE_WEBHOOK_RETRY_DELAY * attempt
                logger.info(
                    f"⏳ Ожидание {delay} секунд перед следующей попыткой отправки вебхука на {webhook_url}"
                )
                await asyncio.sleep(delay)

        return False







