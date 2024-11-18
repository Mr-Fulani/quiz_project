# webhook_sender.py

import logging
import ssl
import asyncio
import aiohttp
from typing import Dict, List
import certifi
from datetime import datetime
import json
import re

from config import MAKE_WEBHOOK_URL, MAKE_WEBHOOK_TIMEOUT, MAKE_WEBHOOK_RETRIES, MAKE_WEBHOOK_RETRY_DELAY

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'^(?:http|https)://'  # http:// или https://
    r'(?:\S+(?::\S*)?@)?'  # пользователь и пароль
    r'(?:(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+'  # домены
    r'[A-Za-z]{2,6}'  # расширение домена
    r'(?::\d{2,5})?'  # порт
    r'(?:/\S*)?$'  # путь
)

def is_valid_url(url: str) -> bool:
    return re.match(URL_REGEX, url) is not None

async def send_webhook(data: Dict):
    """
    Отправляет данные на внешний вебхук (Make.com).

    :param data: Словарь с данными для отправки.
    """
    if not MAKE_WEBHOOK_URL:
        logger.error("❌ MAKE_WEBHOOK_URL не установлен в конфигурации.")
        return

    if not is_valid_url(MAKE_WEBHOOK_URL):
        logger.error(f"❌ Некорректный URL вебхука: {MAKE_WEBHOOK_URL}")
        return

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=MAKE_WEBHOOK_TIMEOUT),
        connector=aiohttp.TCPConnector(ssl=ssl_context)
    ) as session:
        for attempt in range(1, MAKE_WEBHOOK_RETRIES + 1):
            try:
                logger.debug(f"Попытка отправки вебхука №{attempt} с данными: {data}")
                async with session.post(MAKE_WEBHOOK_URL, json=data) as response:
                    response_text = await response.text()
                    if response.status in [200, 201, 202, 204]:
                        logger.info(f"✅ Вебхук успешно отправлен. Ответ: {response_text}")
                        break
                    else:
                        logger.error(f"❌ Ошибка при отправке вебхука. Статус: {response.status}, Ответ: {response_text}")
            except Exception as e:
                logger.exception(f"❌ Исключение при отправке вебхука: {e}")

            if attempt < MAKE_WEBHOOK_RETRIES:
                logger.info(f"⏳ Ожидание перед следующей попыткой: {MAKE_WEBHOOK_RETRY_DELAY} секунд")
                await asyncio.sleep(MAKE_WEBHOOK_RETRY_DELAY)
            else:
                logger.error("❌ Все попытки отправки вебхука завершились неудачей.")

async def send_quiz_published_webhook(data: Dict):
    """
    Формирует и отправляет вебхук о публикации опроса.

    :param data: Словарь с данными вебхука.
    """
    try:
        # Проверка наличия необходимых полей
        required_fields = [
            "type", "poll_link", "image_url", "question",
            "correct_answer", "incorrect_answers", "language",
            "group", "caption", "published_at"
        ]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"❌ Отсутствуют необходимые поля в данных вебхука: {missing_fields}")
            return

        # Проверка URL
        if not (is_valid_url(data.get("poll_link", "")) and is_valid_url(data.get("image_url", ""))):
            logger.error(f"❌ Некорректные URL в данных вебхука: poll_link={data.get('poll_link')}, image_url={data.get('image_url')}")
            return

        # Логирование данных вебхука
        logger.debug(f"📤 Отправка webhook данных:\n{json.dumps(data, ensure_ascii=False, indent=2)}")

        # Отправка вебхука на Make.com
        await send_webhook(data)
        logger.info(f"✅ Вебхук отправлен для группы '{data.get('group', {}).get('name', 'Unknown')}' на языке '{data.get('language', 'Unknown')}'")

    except Exception as e:
        logger.exception(f"❌ Не удалось отправить вебхук для группы '{data.get('group', {}).get('name', 'Unknown')}' на языке '{data.get('language', 'Unknown')}': {e}")