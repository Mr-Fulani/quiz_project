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
    try:
        escaped_message = escape_markdown(message)
        await bot.send_message(admin_chat_id, escaped_message, parse_mode="MarkdownV2")
        logger.info(f"Уведомление отправлено администратору {admin_chat_id}.")
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение администратору {admin_chat_id}: {e}")

async def send_webhook(webhook_url: str, data: Dict, headers: Dict) -> bool:
    """
    Отправляет данные на внешний вебхук с повторами при неудаче.
    """
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=MAKE_WEBHOOK_TIMEOUT),
        connector=aiohttp.TCPConnector(ssl=ssl_context)
    ) as session:
        for attempt in range(1, MAKE_WEBHOOK_RETRIES + 1):
            try:
                logger.info(f"📤 Попытка {attempt}/{MAKE_WEBHOOK_RETRIES} отправки вебхука на {webhook_url}")

                async with session.post(webhook_url, json=data, headers=headers) as response:
                    response_text = await response.text()
                    logger.info(f"📨 Webhook response from {webhook_url}:")
                    logger.info(f"Status: {response.status}")
                    logger.info(f"Headers: {dict(response.headers)}")
                    logger.info(f"Body: {response_text}")

                    if response.status in [200, 201, 202, 204]:
                        return True
            except Exception as e:
                logger.exception(f"❌ Попытка {attempt} не удалась для вебхука на {webhook_url}: {e}")

            if attempt < MAKE_WEBHOOK_RETRIES:
                delay = MAKE_WEBHOOK_RETRY_DELAY * attempt
                logger.info(f"⏳ Ожидание {delay} секунд перед повтором отправки вебхука на {webhook_url}")
                await asyncio.sleep(delay)

        return False

async def send_quiz_published_webhook(webhook_url: str, data: Dict) -> bool:
    """
    Вызов для отправки "quiz_published" на указанный URL,
    перед этим проверяем поля.
    """
    try:
        required_fields = [
            "type", "poll_link", "image_url", "question",
            "correct_answer", "incorrect_answers", "language",
            "group", "caption", "published_at"
        ]
        missing = [f for f in required_fields if f not in data]
        if missing:
            logger.error(f"❌ Отсутствуют необходимые поля в данных вебхука: {missing}")
            return False

        if not (is_valid_url(data.get("poll_link", "")) and is_valid_url(data.get("image_url", ""))):
            logger.error(
                f"❌ Некорректные URL в данных вебхука: "
                f"poll_link={data.get('poll_link')}, image_url={data.get('image_url')}"
            )
            return False

        # преобразуем incorrect_answers, если это строка
        if "incorrect_answers" in data:
            ians = data["incorrect_answers"]
            if isinstance(ians, str):
                try:
                    ians_parsed = json.loads(ians)
                    if isinstance(ians_parsed, list):
                        data["incorrect_answers"] = ians_parsed
                    else:
                        # fallback: пустой
                        data["incorrect_answers"] = []
                except json.JSONDecodeError:
                    # fallback: парсим построчно или через запятую
                    splitted = ians.split('\n') if '\n' in ians else ians.split(',')
                    data["incorrect_answers"] = [s.strip() for s in splitted if s.strip()]
            elif not isinstance(ians, list):
                data["incorrect_answers"] = []
                logger.warning(f"Неподдерживаемый формат incorrect_answers: {type(ians)}")

        logger.info(f"📤 Подготовка отправки вебхука 'quiz_published' → {webhook_url} [Lang={data.get('language')}]")

        headers = {
            'Content-Type': 'application/json',
            'X-Request-ID': str(uuid.uuid4()),
            'X-Webhook-ID': data.get('id', ''),
            'X-Webhook-Sequence': f"{data.get('sequence_number', 0)}/{data.get('total_webhooks', 0)}",
            'X-Webhook-Batch': data.get('webhook_batch_id', ''),
            'X-Webhook-Language': data.get('language', '')
        }

        return await send_webhook(webhook_url, data, headers)
    except Exception as e:
        logger.exception(f"❌ Ошибка при подготовке вебхука quiz_published: {e}")
        return False


