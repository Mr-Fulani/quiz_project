# bot/services/webhook_service.py
import asyncio
import json
import logging
import random
import ssl
import uuid
from datetime import datetime
from typing import List, Optional, Dict

import aiohttp
import certifi
from aiogram import Bot
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import MAKE_WEBHOOK_RETRIES, MAKE_WEBHOOK_RETRY_DELAY, MAKE_WEBHOOK_TIMEOUT
from bot.database.models import Webhook, Admin  # Предполагается, что модель Admin существует
from bot.services.webhook_sender import notify_admin, send_quiz_published_webhook

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_webhook(self, url: str, service_name: Optional[str] = None) -> Optional[Webhook]:
        """
        Добавляет новый вебхук в базу данных.
        """
        webhook = Webhook(
            id=uuid.uuid4(),
            url=url,
            service_name=service_name,
            is_active=True
        )
        try:
            self.db_session.add(webhook)
            await self.db_session.commit()
            logger.info(f"Вебхук добавлен: ID={webhook.id}, URL={webhook.url}, Сервис={webhook.service_name}")
            return webhook
        except IntegrityError as e:
            await self.db_session.rollback()
            logger.error(f"Ошибка при добавлении вебхука {url}: {e}")
            return None

    async def delete_webhook(self, webhook_id: uuid.UUID) -> bool:
        """
        Удаляет вебхук по его ID.
        """
        webhook = await self.get_webhook(webhook_id)
        if not webhook:
            logger.warning(f"Вебхук с ID {webhook_id} не найден для удаления.")
            return False

        stmt = delete(Webhook).where(Webhook.id == webhook_id)
        result = await self.db_session.execute(stmt)
        await self.db_session.commit()
        if result.rowcount > 0:
            logger.info(f"Удален вебхук с ID: {webhook_id}")
            return True
        logger.warning(f"Вебхук с ID {webhook_id} не найден.")
        return False

    async def list_webhooks(self, include_inactive=False) -> List[Webhook]:
        """
        Возвращает список всех вебхуков, с опцией включения неактивных.
        """
        query = select(Webhook)
        if not include_inactive:
            query = query.where(Webhook.is_active == True)
        result = await self.db_session.execute(query)
        return result.scalars().all()

    async def get_webhook(self, webhook_id: uuid.UUID) -> Optional[Webhook]:
        """
        Получает вебхук по его ID.
        """
        query = select(Webhook).where(Webhook.id == webhook_id)
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_webhooks(self) -> List[Webhook]:
        """
        Возвращает список только активных вебхуков.
        """
        return await self.list_webhooks()

    async def prepare_webhook_data(self, webhook_data: Dict, index: int, total_webhooks: int) -> Dict:
        """
        Подготавливает данные для отправки вебхука, добавляя необходимые идентификаторы и обрабатывая incorrect_answers.
        """
        webhook_data_with_ids = webhook_data.copy()
        webhook_data_with_ids.update({
            "id": str(uuid.uuid4()),
            "sequence_number": index,
            "total_webhooks": total_webhooks,
            "webhook_batch_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat()
        })

        # Обработка incorrect_answers
        if "incorrect_answers" in webhook_data_with_ids:
            i_answers = webhook_data_with_ids["incorrect_answers"]
            if isinstance(i_answers, str):
                try:
                    deserialized = json.loads(i_answers)
                    if isinstance(deserialized, list):
                        webhook_data_with_ids["incorrect_answers"] = deserialized
                        logger.debug("🔄 incorrect_answers десериализованы из строки в список.")
                    else:
                        logger.error(f"❌ Ожидался список, получен другой тип: {type(deserialized)}")
                        webhook_data_with_ids["incorrect_answers"] = []
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка десериализации incorrect_answers: {e}")
                    webhook_data_with_ids["incorrect_answers"] = []
            elif not isinstance(i_answers, list):
                logger.error(f"❌ incorrect_answers имеет неподдерживаемый тип: {type(i_answers)}")
                webhook_data_with_ids["incorrect_answers"] = []

        return webhook_data_with_ids

    async def send_webhooks(self, webhooks_data: List[Dict], webhooks: List[Webhook],
                          bot: Bot, admin_chat_id: int) -> List[bool]:
        """
        Отправляет данные на все активные вебхуки последовательно.
        """
        results = []
        failed_urls = set()

        for webhook in webhooks:
            if not webhook.is_active:
                logger.info(f"🔕 Вебхук {webhook.id} не активен. Пропуск.")
                continue

            for index, webhook_data in enumerate(webhooks_data, 1):
                if webhook.url in failed_urls:
                    await notify_admin(
                        bot,
                        admin_chat_id,
                        f"⚠️ Вебхук на `{webhook.url}` ранее не отправлялся успешно. Пропуск остальных вебхуков с этим URL."
                    )
                    break

                try:
                    logger.info(
                        f"📤 Отправка вебхука {index}/{len(webhooks_data)} на URL {webhook.url} "
                        f"для языка {webhook_data.get('language')}"
                    )

                    # Подготовка данных для отправки
                    webhook_data_with_ids = await self.prepare_webhook_data(
                        webhook_data,
                        index,
                        len(webhooks_data)
                    )

                    # Задержка между отправками
                    if index > 1:
                        delay = random.uniform(2.0, 4.0)
                        await notify_admin(
                            bot,
                            admin_chat_id,
                            f"⏳ Ожидание {delay:.1f} секунд перед отправкой следующего вебхука."
                        )
                        await asyncio.sleep(delay)

                    # Отправка вебхука
                    success = await send_quiz_published_webhook(webhook.url, webhook_data_with_ids)
                    results.append(success)

                    if success:
                        logger.info(
                            f"✅ Вебхук {index}/{len(webhooks_data)} на {webhook.url} ({webhook.service_name}) "
                            f"для языка {webhook_data.get('language')} (ID: {webhook_data_with_ids['id']}) "
                            f"успешно отправлен"
                        )
                        await notify_admin(
                            bot,
                            admin_chat_id,
                            f"✅ Вебхук `{webhook.url}` ({webhook.service_name}) успешно отправлен."
                        )
                        await asyncio.sleep(1.0)
                    else:
                        logger.error(
                            f"❌ Вебхук {index}/{len(webhooks_data)} на {webhook.url} ({webhook.service_name}) "
                            f"для языка {webhook_data.get('language')} (ID: {webhook_data_with_ids['id']}) "
                            f"не удалось отправить"
                        )
                        failed_urls.add(webhook.url)
                        await notify_admin(
                            bot,
                            admin_chat_id,
                            f"❌ Вебхук `{webhook.url}` ({webhook.service_name}) не удалось отправить."
                        )
                        await asyncio.sleep(2.0)
                except Exception as e:
                    logger.exception(
                        f"❌ Ошибка при отправке вебхука {index}/{len(webhooks_data)} на {webhook.url} "
                        f"({webhook.service_name}) для языка {webhook_data.get('language', 'Unknown')}: {e}"
                    )
                    failed_urls.add(webhook.url)
                    await notify_admin(
                        bot,
                        admin_chat_id,
                        f"❌ Ошибка при отправке вебхука `{webhook.url}` ({webhook.service_name}): {e}"
                    )
                    results.append(False)
                    await asyncio.sleep(2.0)

        # Итоговая статистика
        success_count = sum(1 for r in results if r)
        failed_count = len(results) - success_count
        summary_msg = (
            f"📊 Итоги отправки вебхуков:\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Неудачно: {failed_count}"
        )
        logger.info(summary_msg)
        await notify_admin(bot, admin_chat_id, summary_msg)

        return results

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



    async def activate_webhook(self, webhook_id: uuid.UUID) -> bool:
        """
        Активирует вебхук по его ID.
        """
        webhook = await self.get_webhook(webhook_id)
        if webhook:
            webhook.is_active = True
            await self.db_session.commit()
            logger.info(f"Вебхук с ID {webhook_id} активирован.")
            return True
        logger.warning(f"Вебхук с ID {webhook_id} не найден для активации.")
        return False

    async def deactivate_webhook(self, webhook_id: uuid.UUID) -> bool:
        """
        Деактивирует вебхук по его ID.
        """
        webhook = await self.get_webhook(webhook_id)
        if webhook:
            webhook.is_active = False
            await self.db_session.commit()
            logger.info(f"Вебхук с ID {webhook_id} деактивирован.")
            return True
        logger.warning(f"Вебхук с ID {webhook_id} не найден для деактивации.")
        return False

    async def get_active_admin_ids(self) -> List[int]:
        """
        Получает список ID всех администраторов, взаимодействующих с ботом.
        """
        # Просто возвращает все ID из таблицы admins
        query = select(Admin.id)
        result = await self.db_session.execute(query)
        return [row[0] for row in result.fetchall()]