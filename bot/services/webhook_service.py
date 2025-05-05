import asyncio
import logging
import random
import uuid
from datetime import datetime
from typing import List, Optional, Dict

from aiogram import Bot
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Webhook, Admin
from bot.services.webhook_sender import (
    notify_admin,
    send_quiz_published_webhook
)
from bot.utils.logging_utils import log_webhook_summary



logger = logging.getLogger(__name__)



class WebhookService:
    def __init__(self, db_session: AsyncSession):
        """Инициализирует сервис для работы с вебхуками.

        Args:
            db_session (AsyncSession): Асинхронная сессия SQLAlchemy для работы с базой данных.
        """
        self.db_session = db_session

    async def add_webhook(self, url: str, service_name: Optional[str] = None) -> Optional[Webhook]:
        """Добавляет новый вебхук в базу данных.

        Args:
            url (str): URL вебхука.
            service_name (Optional[str]): Название сервиса (опционально).

        Returns:
            Optional[Webhook]: Созданный вебхук или None, если произошла ошибка (например, URL уже существует).

        Raises:
            IntegrityError: Если URL уже существует в базе данных (нарушение уникальности).
        """
        webhook = Webhook(
            id=uuid.uuid4(),
            url=url,
            service_name=service_name,
            is_active=True,
            created_at=datetime.utcnow(),  # Исправление: явно задаем created_at
            updated_at=datetime.utcnow()   # Исправление: явно задаем updated_at
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
        """Удаляет вебхук по его ID.

        Args:
            webhook_id (uuid.UUID): Уникальный идентификатор вебхука.

        Returns:
            bool: True, если вебхук успешно удален, False, если вебхук не найден.
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
        """Получает список всех вебхуков.

        Args:
            include_inactive (bool): Если True, включает неактивные вебхуки. По умолчанию False.

        Returns:
            List[Webhook]: Список вебхуков.
        """
        query = select(Webhook)
        if not include_inactive:
            query = query.where(Webhook.is_active == True)
        result = await self.db_session.execute(query)
        return result.scalars().all()

    async def get_webhook(self, webhook_id: uuid.UUID) -> Optional[Webhook]:
        """Получает вебхук по его ID.

        Args:
            webhook_id (uuid.UUID): Уникальный идентификатор вебхука.

        Returns:
            Optional[Webhook]: Найденный вебхук или None, если вебхук не существует.
        """
        query = select(Webhook).where(Webhook.id == webhook_id)
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_webhooks(self) -> List[Webhook]:
        """Получает список активных вебхуков.

        Returns:
            List[Webhook]: Список активных вебхуков.
        """
        return await self.list_webhooks()

    async def prepare_webhook_data(self, webhook_data: Dict, index: int, total_webhooks: int) -> Dict:
        """Добавляет служебные поля в данные вебхука для логирования и трассировки.

        Args:
            webhook_data (Dict): Исходные данные вебхука.
            index (int): Порядковый номер вебхука в текущей отправке.
            total_webhooks (int): Общее количество вебхуков в отправке.

        Returns:
            Dict: Данные вебхука с добавленными служебными полями.
        """
        data_copy = webhook_data.copy()
        data_copy.update({
            "id": str(uuid.uuid4()),
            "sequence_number": index,
            "total_webhooks": total_webhooks,
            "webhook_batch_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat()
        })
        return data_copy

    async def send_webhooks(
        self,
        webhooks_data: List[Dict],
        webhooks: List[Webhook],
        bot: Bot,
        admin_chat_id: int
    ) -> List[bool]:
        """Отправляет данные на указанные вебхуки с задержками между отправками.

        Args:
            webhooks_data (List[Dict]): Список словарей с данными для отправки.
            webhooks (List[Webhook]): Список вебхуков, на которые отправляются данные.
            bot (Bot): Экземпляр Telegram-бота для отправки уведомлений.
            admin_chat_id (int): ID чата администратора для уведомлений.

        Returns:
            List[bool]: Список результатов отправки (True — успех, False — неудача).
        """
        results = []
        failed_urls = set()

        for webhook in webhooks:
            if not webhook.is_active:
                logger.info(f"🔕 Вебхук {webhook.id} [{webhook.service_name}] не активен, пропускаем.")
                continue

            for index, wd in enumerate(webhooks_data, start=1):
                if webhook.url in failed_urls:
                    await notify_admin(
                        bot,
                        admin_chat_id,
                        f"⚠️ Этот вебхук {webhook.url} уже ошибся раньше, пропускаем остальные."
                    )
                    break

                try:
                    wd_prepared = await self.prepare_webhook_data(wd, index, len(webhooks_data))
                    logger.info(
                        f"📤 Отправка {index}/{len(webhooks_data)} на {webhook.url}, язык={wd.get('language')}"
                    )

                    if index > 1:
                        delay = random.uniform(2.0, 4.0)
                        logger.info(f"⏳ Пауза {delay:.1f} c перед отправкой следующего вебхука.")
                        await asyncio.sleep(delay)

                    ok = await send_quiz_published_webhook(webhook.url, wd_prepared)
                    results.append(ok)
                    if ok:
                        logger.info(f"✅ Успешно на {webhook.url}")
                        await notify_admin(bot, admin_chat_id, f"✅ Успешно: {webhook.url}")
                    else:
                        logger.error(f"❌ Не удалось на {webhook.url}")
                        failed_urls.add(webhook.url)
                        await notify_admin(bot, admin_chat_id, f"❌ Ошибка при отправке: {webhook.url}")
                except Exception as e:
                    logger.exception(
                        f"❌ Ошибка при отправке вебхука {webhook.url}: {e}"
                    )
                    failed_urls.add(webhook.url)
                    results.append(False)
                    await notify_admin(
                        bot,
                        admin_chat_id,
                        f"❌ Ошибка при отправке вебхука {webhook.url}: {str(e)}"
                    )

        success = sum(1 for x in results if x)
        fail = len(results) - success
        summary_msg = log_webhook_summary(success, fail)
        await notify_admin(bot, admin_chat_id, summary_msg)

        return results

    async def activate_webhook(self, webhook_id: uuid.UUID) -> bool:
        """Активирует вебхук по его ID.

        Args:
            webhook_id (uuid.UUID): Уникальный идентификатор вебхука.

        Returns:
            bool: True, если вебхук успешно активирован, False, если вебхук не найден.
        """
        webhook = await self.get_webhook(webhook_id)
        if webhook:
            webhook.is_active = True
            await self.db_session.commit()
            logger.info(f"Вебхук {webhook_id} активирован.")
            return True
        logger.warning(f"Нет вебхука с ID={webhook_id} для активации.")
        return False

    async def deactivate_webhook(self, webhook_id: uuid.UUID) -> bool:
        """Деактивирует вебхук по его ID.

        Args:
            webhook_id (uuid.UUID): Уникальный идентификатор вебхука.

        Returns:
            bool: True, если вебхук успешно деактивирован, False, если вебхук не найден.
        """
        webhook = await self.get_webhook(webhook_id)
        if webhook:
            webhook.is_active = False
            await self.db_session.commit()
            logger.info(f"Вебхук {webhook_id} деактивирован.")
            return True
        logger.warning(f"Нет вебхука с ID={webhook_id} для деактивации.")
        return False

    async def get_active_admin_ids(self) -> List[int]:
        """Получает список ID активных администраторов.

        Returns:
            List[int]: Список ID администраторов.
        """
        query = select(Admin.id)
        result = await self.db_session.execute(query)
        return [row[0] for row in result.fetchall()]