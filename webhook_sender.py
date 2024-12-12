# webhook_sender.py

import asyncio
import json
import logging
import random
import re
import ssl
import uuid
from datetime import datetime
from typing import Dict, List

import aiohttp
import certifi
from sqlalchemy.ext.asyncio import AsyncSession

from bot.utils.url_validator import is_valid_url
from config import MAKE_WEBHOOK_TIMEOUT, MAKE_WEBHOOK_RETRIES, MAKE_WEBHOOK_RETRY_DELAY, ALLOWED_USERS
from database.models import Webhook
from aiogram import Bot

logger = logging.getLogger(__name__)




async def send_webhooks_sequentially(webhooks_data: List[Dict], webhooks: List[Webhook], db_session: AsyncSession, bot: Bot) -> List[bool]:
    """
    Последовательно отправляет вебхуки на каждый URL из списка.
    """
    results = []
    total = len(webhooks) * len(webhooks_data)

    for webhook in webhooks:
        if not webhook.is_active:
            logger.info(f"🔕 Вебхук {webhook.id} не активен. Пропуск.")
            continue

        for index, webhook_data in enumerate(webhooks_data, 1):
            try:
                logger.info(f"📤 Отправка вебхука {index}/{total} на URL {webhook.url} для языка {webhook_data.get('language')}")

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

                success = await send_quiz_published_webhook(webhook.url, webhook_data)
                results.append(success)

                if success:
                    logger.info(
                        f"✅ Вебхук {index}/{total} на {webhook.url} для языка {webhook_data.get('language')} (ID: {webhook_data['id']}) успешно отправлен"
                    )
                    # Дополнительная задержка после успешной отправки
                    await asyncio.sleep(1.0)
                    # Уведомляем администраторов об успешной отправке
                    await notify_admins(bot, f"✅ Вебхук {webhook.url} успешно отправлен.")
                else:
                    logger.error(
                        f"❌ Вебхук {index}/{total} на {webhook.url} для языка {webhook_data.get('language')} (ID: {webhook_data['id']}) не удалось отправить"
                    )
                    # Помечаем вебхук как неактивный
                    webhook.is_active = False
                    await db_session.commit()
                    # Уведомляем администраторов об ошибке и деактивации вебхука
                    await notify_admins(bot, f"❌ Вебхук {webhook.url} не удалось отправить.")
                    # Более длительная задержка после неудачной отправки
                    await asyncio.sleep(2.0)

            except Exception as e:
                logger.exception(
                    f"❌ Ошибка при отправке вебхука {index}/{total} на {webhook.url} для языка {webhook_data.get('language', 'Unknown')}: {e}"
                )
                # Помечаем вебхук как неактивный
                webhook.is_active = False
                await db_session.commit()
                # Уведомляем администраторов об ошибке и деактивации вебхука
                await notify_admins(bot, f"❌ Ошибка при отправке вебхука {webhook.url}: {e}")
                results.append(False)
                await asyncio.sleep(2.0)  # Задержка после ошибки

        # Сохраняем изменения в базе данных после обработки вебхука
        await db_session.commit()

    # Итоговая статистика
    success_count = sum(1 for r in results if r)
    logger.info(
        f"📊 Итоги отправки вебхуков:\n"
        f"✅ Успешно: {success_count}/{len(results)}\n"
        f"❌ Неудачно: {len(results) - success_count}/{len(results)}"
    )

    return results




async def notify_admins(bot: Bot, message: str):
    """Отправляет сообщение всем администраторам из ALLOWED_USERS."""
    for admin_id in ALLOWED_USERS:
        try:
            await bot.send_message(chat_id=admin_id, text=message)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")






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
                f"❌ Не удалось отправить вебхук на {webhook_url} для языка '{data.get('language', 'Unknown')}' (ID: {data.get('id')})"
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