# webhook_sender.py

import asyncio
import json
import logging
import random
import ssl
import uuid
from datetime import datetime
from typing import Dict, List

import aiohttp
import certifi
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.utils.markdownV2 import escape_markdown
from bot.utils.url_validator import is_valid_url
from config import MAKE_WEBHOOK_TIMEOUT, MAKE_WEBHOOK_RETRIES, MAKE_WEBHOOK_RETRY_DELAY
from database.models import Webhook

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


async def send_webhooks_sequentially(webhooks_data: List[Dict], webhooks: List[Webhook], db_session: AsyncSession,
                                     bot: Bot, admin_chat_id: int) -> List[bool]:
    """
    Последовательно отправляет вебхуки на каждый URL из списка.
    Уведомляет только инициирующего администратора.
    Не деактивирует вебхуки автоматически.
    """
    results = []
    failed_urls = set()

    for webhook in webhooks:
        if not webhook.is_active:
            logger.info(f"🔕 Вебхук {webhook.id} не активен. Пропуск.")
            continue
        if webhook.url in failed_urls:
            logger.warning(
                f"⚠️ Вебхук на {webhook.url} ранее не отправлялся успешно. Пропуск остальных вебхуков с этим URL.")
            await notify_admin(bot, admin_chat_id,
                               f"⚠️ Вебхук на `{webhook.url}` ранее не отправлялся успешно. Пропуск остальных вебхуков с этим URL.")
            continue

        for index, webhook_data in enumerate(webhooks_data, 1):
            if webhook.url in failed_urls:
                break  # Пропускаем дальнейшие данные для этого URL

            try:
                logger.info(
                    f"📤 Отправка вебхука {index}/{len(webhooks_data)} на URL {webhook.url} для языка {webhook_data.get('language')}")
                logger.debug(
                    f"🔍 Структура incorrect_answers перед отправкой: {webhook_data['incorrect_answers']} (тип элементов: {[type(ans) for ans in webhook_data['incorrect_answers']]})")

                # Убедимся, что incorrect_answers является списком
                incorrect_answers = webhook_data.get('incorrect_answers', [])
                if isinstance(incorrect_answers, str):
                    try:
                        incorrect_answers = json.loads(incorrect_answers)
                        webhook_data['incorrect_answers'] = incorrect_answers
                        logger.debug("🔄 incorrect_answers десериализованы из строки в список.")
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Ошибка десериализации incorrect_answers: {e}")
                        webhook_data['incorrect_answers'] = []
                elif not isinstance(incorrect_answers, list):
                    logger.error("❌ incorrect_answers имеет неподдерживаемый тип. Ожидается список строк.")
                    webhook_data['incorrect_answers'] = []

                # Добавляем уникальные идентификаторы
                webhook_data_with_ids = webhook_data.copy()
                webhook_data_with_ids.update({
                    "id": str(uuid.uuid4()),
                    "sequence_number": index,
                    "total_webhooks": len(webhooks_data),
                    "webhook_batch_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat()
                })


                success = await send_quiz_published_webhook(webhook.url, webhook_data_with_ids)
                results.append(success)

                if success:
                    logger.info(
                        f"✅ Вебхук {index}/{len(webhooks_data)} на {webhook.url} для языка {webhook_data.get('language')} (ID: {webhook_data_with_ids['id']}) успешно отправлен"
                    )
                    # Дополнительная задержка после успешной отправки
                    await asyncio.sleep(1.0)
                    # Уведомляем инициирующего администратора об успешной отправке
                    await notify_admin(bot, admin_chat_id, f"✅ Вебхук `{webhook.url}` успешно отправлен.")
                else:
                    logger.error(
                        f"❌ Вебхук {index}/{len(webhooks_data)} на {webhook.url} для языка {webhook_data.get('language')} (ID: {webhook_data_with_ids['id']}) не удалось отправить"
                    )
                    failed_urls.add(webhook.url)
                    # Уведомляем инициирующего администратора об ошибке
                    await notify_admin(bot, admin_chat_id, f"❌ Вебхук `{webhook.url}` не удалось отправить.")
                    # Пауза после неудачной отправки
                    await asyncio.sleep(2.0)
            except Exception as e:
                logger.exception(
                    f"❌ Ошибка при отправке вебхука {index}/{len(webhooks_data)} на {webhook.url} для языка {webhook_data.get('language', 'Unknown')}: {e}"
                )
                failed_urls.add(webhook.url)
                # Уведомляем инициирующего администратора об ошибке
                await notify_admin(bot, admin_chat_id, f"❌ Ошибка при отправке вебхука `{webhook.url}`: {e}")
                results.append(False)
                await asyncio.sleep(2.0)  # Задержка после ошибки

    # Итоговая статистика
    success_count = sum(1 for r in results if r)
    failed_count = len(results) - success_count
    logger.info(
        f"📊 Итоги отправки вебхуков:\n"
        f"✅ Успешно: {success_count}/{len(results)}\n"
        f"❌ Неудачно: {failed_count}/{len(results)}"
    )
    await notify_admin(bot, admin_chat_id,
                       f"📊 Итоги отправки вебхуков:\n✅ Успешно: {success_count}\n❌ Неудачно: {failed_count}")

    return results




async def send_quiz_published_webhook(webhook_url: str, data: Dict) -> bool:
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