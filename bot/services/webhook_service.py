# bot/services/webhook_service.py

import logging
import uuid
from typing import List, Optional, Dict

from aiogram import Bot
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Webhook, Admin  # Предполагается, что модель Admin существует

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
            return None  # Возвращаем None, если возникла ошибка дублирования

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

    async def send_data_to_webhooks_sequentially(self, webhooks_data: List[Dict], webhooks: List[Webhook], db_session: AsyncSession, bot: Bot, admin_chat_id: int) -> List[bool]:
        """
        Отправляет данные на все активные вебхуки последовательно с учетом новых требований.
        """
        from webhook_sender import send_webhooks_sequentially  # Импорт функции

        results = await send_webhooks_sequentially(
            webhooks_data,
            webhooks,
            db_session,
            bot,
            admin_chat_id  # Передача ID чата администратора
        )
        return results

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