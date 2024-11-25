
import logging
import ssl
import asyncio
import aiohttp
from typing import Dict, List
import certifi
from datetime import datetime
import json
import re
import uuid
import random

from config import MAKE_WEBHOOK_URL, MAKE_WEBHOOK_TIMEOUT, MAKE_WEBHOOK_RETRIES, MAKE_WEBHOOK_RETRY_DELAY

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'^(?:http|https)://'
    r'(?:\S+(?::\S*)?@)?'
    r'(?:(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+'
    r'[A-Za-z]{2,6}'
    r'(?::\d{2,5})?'
    r'(?:/\S*)?$'
)


def is_valid_url(url: str) -> bool:
    """Проверяет корректность URL."""
    return bool(re.match(URL_REGEX, url))




async def send_webhooks_sequentially(webhooks_data: List[Dict]) -> List[bool]:
    """
    Последовательно отправляет вебхуки с существенной задержкой между отправками.
    """
    results = []
    total = len(webhooks_data)

    for index, webhook_data in enumerate(webhooks_data, 1):
        try:
            logger.info(f"📤 Отправка вебхука {index}/{total} для языка {webhook_data.get('language')}")

            # Добавляем больше уникальных идентификаторов
            webhook_data.update({
                "id": str(uuid.uuid4()),
                "sequence_number": index,
                "total_webhooks": total,
                "webhook_batch_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat()
            })

            # Более длительная случайная задержка между отправками (2-4 секунды)
            if index > 1:
                delay = random.uniform(2.0, 4.0)
                logger.info(f"⏳ Ожидание {delay:.1f} секунд перед отправкой следующего вебхука")
                await asyncio.sleep(delay)

            success = await send_quiz_published_webhook(webhook_data)
            results.append(success)

            if success:
                logger.info(
                    f"✅ Вебхук {index}/{total} для языка {webhook_data.get('language')} "
                    f"(ID: {webhook_data['id']}) успешно отправлен"
                )
                # Дополнительная задержка после успешной отправки
                await asyncio.sleep(1.0)
            else:
                logger.error(
                    f"❌ Вебхук {index}/{total} для языка {webhook_data.get('language')} "
                    f"(ID: {webhook_data['id']}) не удалось отправить"
                )
                # Более длительная задержка после неудачной отправки
                await asyncio.sleep(2.0)

        except Exception as e:
            logger.exception(
                f"❌ Ошибка при отправке вебхука {index}/{total} "
                f"для языка {webhook_data.get('language', 'Unknown')}: {e}"
            )
            results.append(False)
            await asyncio.sleep(2.0)  # Задержка после ошибки

    # Итоговая статистика
    success_count = sum(1 for r in results if r)
    logger.info(
        f"📊 Итоги отправки вебхуков:\n"
        f"✅ Успешно: {success_count}/{total}\n"
        f"❌ Неудачно: {total - success_count}/{total}"
    )

    return results


async def send_quiz_published_webhook(data: Dict) -> bool:
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

        logger.info(f"📤 Подготовка отправки вебхука для языка {data.get('language')} (ID: {data.get('id')})")
        logger.info(
            f"📤 Вебхук {data.get('sequence_number')}/{data.get('total_webhooks')} из batch {data.get('webhook_batch_id')}")
        logger.debug(f"📤 Данные вебхука:\n{json.dumps(data, ensure_ascii=False, indent=2)}")

        headers = {
            'Content-Type': 'application/json',
            'X-Request-ID': str(uuid.uuid4()),
            'X-Webhook-ID': data.get('id', ''),
            'X-Webhook-Sequence': f"{data.get('sequence_number', 0)}/{data.get('total_webhooks', 0)}",
            'X-Webhook-Batch': data.get('webhook_batch_id', ''),
            'X-Webhook-Language': data.get('language', '')
        }

        success = await send_webhook(data, headers)

        if success:
            logger.info(
                f"✅ Вебхук успешно отправлен для группы '{data.get('group', {}).get('name', 'Unknown')}' "
                f"на языке '{data.get('language', 'Unknown')}' (ID: {data.get('id')})"
            )
        else:
            logger.error(
                f"❌ Не удалось отправить вебхук для группы '{data.get('group', {}).get('name', 'Unknown')}' "
                f"на языке '{data.get('language', 'Unknown')}' (ID: {data.get('id')})"
            )

        return success

    except Exception as e:
        logger.exception(
            f"❌ Ошибка при подготовке вебхука для группы '{data.get('group', {}).get('name', 'Unknown')}' "
            f"на языке '{data.get('language', 'Unknown')}' (ID: {data.get('id')}): {e}"
        )
        return False


async def send_webhook(data: Dict, headers: Dict) -> bool:
    """
    Отправляет данные на внешний вебхук (Make.com).
    """
    if not MAKE_WEBHOOK_URL:
        logger.error("❌ MAKE_WEBHOOK_URL не установлен в конфигурации.")
        return False

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=MAKE_WEBHOOK_TIMEOUT),
            connector=aiohttp.TCPConnector(ssl=ssl_context)
    ) as session:
        for attempt in range(1, MAKE_WEBHOOK_RETRIES + 1):
            try:
                logger.info(
                    f"📤 Попытка {attempt}/{MAKE_WEBHOOK_RETRIES} отправки вебхука "
                    f"для языка {data.get('language')} (ID: {data.get('id')})"
                )

                async with session.post(MAKE_WEBHOOK_URL, json=data, headers=headers) as response:
                    response_text = await response.text()

                    logger.info(f"📨 Webhook response for {data.get('language')} (ID: {data.get('id')}):")
                    logger.info(f"Status: {response.status}")
                    logger.info(f"Headers: {dict(response.headers)}")
                    logger.info(f"Body: {response_text}")

                    if response.status in [200, 201, 202, 204]:
                        return True

            except Exception as e:
                logger.exception(
                    f"❌ Attempt {attempt} failed for language {data.get('language')} "
                    f"(ID: {data.get('id')}): {e}"
                )

            if attempt < MAKE_WEBHOOK_RETRIES:
                delay = MAKE_WEBHOOK_RETRY_DELAY * attempt
                logger.info(
                    f"⏳ Waiting {delay} seconds before next attempt for language "
                    f"{data.get('language')} (ID: {data.get('id')})"
                )
                await asyncio.sleep(delay)

        return False




