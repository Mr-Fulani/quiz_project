# # bot/services/webhook_service.py
#
# import logging
# import aiohttp
# import uuid
# from sqlalchemy.exc import IntegrityError
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, delete
# from typing import List, Optional, Dict
# from database.models import Webhook, Admin  # Предполагается, что модель Admin существует
#
# from bot.utils.markdownV2 import escape_markdown  # Импорт вашей функции экранирования
#
# logger = logging.getLogger(__name__)
#
# class WebhookService:
#     def __init__(self, db_session: AsyncSession):
#         self.db_session = db_session
#
#     async def add_webhook(self, url: str, service_name: Optional[str] = None) -> Optional[Webhook]:
#         """
#         Добавляет новый вебхук в базу данных.
#         """
#         webhook = Webhook(
#             id=uuid.uuid4(),
#             url=url,
#             service_name=service_name,
#             is_active=True
#         )
#         try:
#             self.db_session.add(webhook)
#             await self.db_session.commit()
#             logger.info(f"Вебхук добавлен: ID={webhook.id}, URL={webhook.url}, Сервис={webhook.service_name}")
#             return webhook
#         except IntegrityError as e:
#             await self.db_session.rollback()
#             logger.error(f"Ошибка при добавлении вебхука {url}: {e}")
#             return None  # Возвращаем None, если возникла ошибка дублирования
#
#     async def delete_webhook(self, webhook_id: uuid.UUID) -> bool:
#         """
#         Удаляет вебхук по его ID.
#         """
#         webhook = await self.get_webhook(webhook_id)
#         if not webhook:
#             logger.warning(f"Вебхук с ID {webhook_id} не найден для удаления.")
#             return False
#
#         stmt = delete(Webhook).where(Webhook.id == webhook_id)
#         result = await self.db_session.execute(stmt)
#         await self.db_session.commit()
#         if result.rowcount > 0:
#             logger.info(f"Удален вебхук с ID: {webhook_id}")
#             return True
#         logger.warning(f"Вебхук с ID {webhook_id} не найден.")
#         return False
#
#     async def list_webhooks(self, include_inactive=False) -> List[Webhook]:
#         """
#         Возвращает список всех вебхуков, с опцией включения неактивных.
#         """
#         query = select(Webhook)
#         if not include_inactive:
#             query = query.where(Webhook.is_active == True)
#         result = await self.db_session.execute(query)
#         return result.scalars().all()
#
#     async def get_webhook(self, webhook_id: uuid.UUID) -> Optional[Webhook]:
#         """
#         Получает вебхук по его ID.
#         """
#         query = select(Webhook).where(Webhook.id == webhook_id)
#         result = await self.db_session.execute(query)
#         return result.scalar_one_or_none()
#
#     async def get_active_webhooks(self) -> List[Webhook]:
#         """
#         Возвращает список только активных вебхуков.
#         """
#         return await self.list_webhooks()
#
#
#     async def send_data_to_webhooks(self, data: Dict, bot, admin_id: int) -> List[Dict]:
#         """
#         Отправляет данные на все активные вебхуки.
#         Уведомляет инициирующего администратора о неработающих вебхуках.
#         """
#         webhooks = await self.get_active_webhooks()
#         results = []
#         for webhook in webhooks:
#             success = await self._send_data_to_webhook(webhook, data, bot, admin_id)
#             results.append({
#                 "webhook": webhook,
#                 "success": success
#             })
#         return results
#
#     async def _send_data_to_webhook(self, webhook: Webhook, data: Dict, bot, admin_id: int) -> bool:
#         """
#         Отправляет данные на указанный вебхук.
#         Уведомляет инициирующего администратора, если отправка не удалась.
#         """
#         try:
#             logger.debug(f"Отправка данных на вебхук {webhook.url}: {data}")
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(webhook.url, json=data, timeout=10) as response:
#                     if response.status in [200, 201, 202, 204]:
#                         logger.info(f"Вебхук {webhook.url} успешно отправлен.")
#                         await self.notify_admin(bot, admin_id, f"✅ Вебхук {webhook.url} успешно отправлен.")
#                         return True
#                     else:
#                         error_message = f"Статус {response.status}"
#                         logger.warning(f"Вебхук {webhook.url} вернул статус {response.status}")
#                         await self.notify_admin(bot, admin_id, f"⚠️ Вебхук {webhook.url} вернул статус {response.status}")
#                         return False
#         except Exception as e:
#             error_message = str(e)
#             logger.error(f"Ошибка при отправке данных на вебхук {webhook.url}: {e}")
#             await self.notify_admin(bot, admin_id, f"❌ Ошибка при отправке данных на вебхук {webhook.url}: {e}")
#             return False
#
#
#     async def notify_admin(self, bot, admin_id: int, message: str):
#         """
#         Уведомляет конкретного администратора о событии.
#         """
#         try:
#             await bot.send_message(admin_id, message, parse_mode="MarkdownV2")
#             logger.info(f"Уведомление отправлено администратору {admin_id}.")
#         except Exception as e:
#             logger.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")
#
#
#     async def activate_webhook(self, webhook_id: uuid.UUID) -> bool:
#         """
#         Активирует вебхук по его ID.
#         """
#         webhook = await self.get_webhook(webhook_id)
#         if webhook:
#             webhook.is_active = True
#             await self.db_session.commit()
#             logger.info(f"Вебхук с ID {webhook_id} активирован.")
#             return True
#         logger.warning(f"Вебхук с ID {webhook_id} не найден для активации.")
#         return False
#
#
#     async def deactivate_webhook(self, webhook_id: uuid.UUID) -> bool:
#         """
#         Деактивирует вебхук по его ID.
#         """
#         webhook = await self.get_webhook(webhook_id)
#         if webhook:
#             webhook.is_active = False
#             await self.db_session.commit()
#             logger.info(f"Вебхук с ID {webhook_id} деактивирован.")
#             return True
#         logger.warning(f"Вебхук с ID {webhook_id} не найден для деактивации.")
#         return False
#
#
#     async def notify_admins(self, bot, webhook: Webhook, error_message: str):
#         """
#         Уведомляет активных администраторов, взаимодействующих с ботом, о неработающем вебхуке.
#         """
#         admin_ids = await self.get_active_admin_ids()
#         if not admin_ids:
#             logger.warning("Нет активных администраторов для уведомления.")
#             return
#
#         # Экранирование только названия сервиса и ошибки
#         escaped_service = escape_markdown(webhook.service_name or "Не указано")
#         escaped_error = escape_markdown(error_message)
#
#         # Формирование сообщения
#         message = (
#             f"⚠️ **Ошибка отправки вебхука:**\n"
#             f"**ID:** `{webhook.id}`.\n"  # Без экранирования
#             f"**URL:** <{webhook.url}>\n"  # Угловые скобки для URL
#             f"**Сервис:** {escaped_service}\n"
#             f"**Ошибка:** {escaped_error}\n"
#             f"Пожалуйста, проверьте вебхук."
#         )
#         for admin_id in admin_ids:
#             try:
#                 await bot.send_message(admin_id, message, parse_mode="MarkdownV2")
#                 logger.info(f"Оповещение отправлено администратору {admin_id}.")
#             except Exception as e:
#                 logger.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")
#
#
#     async def get_active_admin_ids(self) -> List[int]:
#         """
#         Получает список ID всех активных администраторов, взаимодействующих с ботом.
#         """
#         # Предполагается, что модель Admin имеет поле `id` типа int и `is_active` типа bool
#         query = select(Admin.id).where(Admin.is_active == True)
#         result = await self.db_session.execute(query)
#         return [row[0] for row in result.fetchall()]









# bot/services/webhook_service.py

import logging
import aiohttp
import uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional, Dict
from database.models import Webhook, Admin  # Предполагается, что модель Admin существует

from bot.utils.markdownV2 import escape_markdown  # Импорт вашей функции экранирования

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

    async def send_data_to_webhooks(self, data: Dict, bot, admin_id: int) -> List[Dict]:
        """
        Отправляет данные на все активные вебхуки.
        Уведомляет инициирующего администратора о неработающих вебхуках.
        """
        webhooks = await self.get_active_webhooks()
        results = []
        for webhook in webhooks:
            success = await self._send_data_to_webhook(webhook, data, bot, admin_id)
            results.append({
                "webhook": webhook,
                "success": success
            })
        return results

    async def _send_data_to_webhook(self, webhook: Webhook, data: Dict, bot, admin_id: int) -> bool:
        """
        Отправляет данные на указанный вебхук.
        Уведомляет инициирующего администратора, если отправка не удалась.
        """
        try:
            logger.debug(f"Отправка данных на вебхук {webhook.url}: {data}")
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook.url, json=data, timeout=10) as response:
                    if response.status in [200, 201, 202, 204]:
                        logger.info(f"Вебхук {webhook.url} успешно отправлен.")
                        await self.notify_admin(bot, admin_id, f"✅ Вебхук {webhook.url} успешно отправлен.")
                        return True
                    else:
                        error_message = f"Статус {response.status}"
                        logger.warning(f"Вебхук {webhook.url} вернул статус {response.status}")
                        await self.notify_admin(bot, admin_id, f"⚠️ Вебхук {webhook.url} вернул статус {response.status}")
                        return False
        except Exception as e:
            error_message = str(e)
            logger.error(f"Ошибка при отправке данных на вебхук {webhook.url}: {e}")
            await self.notify_admin(bot, admin_id, f"❌ Ошибка при отправке данных на вебхук {webhook.url}: {e}")
            return False

    async def notify_admin(self, bot, admin_id: int, message: str):
        """
        Уведомляет конкретного администратора о событии.
        """
        try:
            escaped_message = escape_markdown(message)
            logger.debug(f"Отправка сообщения администратору {admin_id}: {escaped_message}")
            await bot.send_message(admin_id, escaped_message, parse_mode="MarkdownV2")
            logger.info(f"Уведомление отправлено администратору {admin_id}.")
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")

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