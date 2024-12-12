# bot/services/default_link_service.py

import logging
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import DefaultLink

logger = logging.getLogger(__name__)

class DefaultLinkService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_default_link(self, language: str, topic: str) -> str:
        """
        Возвращает ссылку по умолчанию для указанного языка и темы из базы данных.
        Если ссылки нет, возвращает стандартную ссылку.
        """
        try:
            result = await self.db_session.execute(
                select(DefaultLink).where(
                    DefaultLink.language == language,
                    DefaultLink.topic == topic
                )
            )
            default_link = result.scalar_one_or_none()
            if default_link:
                return default_link.link
            else:
                return "https://t.me/developers_hub_ru"
        except Exception as e:
            logger.error(f"Ошибка при получении ссылки по умолчанию: {e}")
            return "https://t.me/developers_hub_ru"

    async def add_default_link(self, language: str, topic: str, link: str) -> DefaultLink:
        """
        Добавляет или обновляет ссылку по умолчанию для указанного языка и темы.
        """
        try:
            result = await self.db_session.execute(
                select(DefaultLink).where(
                    DefaultLink.language == language,
                    DefaultLink.topic == topic
                )
            )
            default_link = result.scalar_one_or_none()
            if default_link:
                default_link.link = link
                logger.info(f"Обновлена ссылка для языка '{language}' и темы '{topic}'.")
            else:
                default_link = DefaultLink(language=language, topic=topic, link=link)
                self.db_session.add(default_link)
                logger.info(f"Добавлена новая ссылка для языка '{language}' и темы '{topic}'.")
            await self.db_session.commit()
            return default_link
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Ошибка при добавлении/обновлении ссылки: {e}")
            raise e

    async def remove_default_link(self, language: str, topic: str) -> bool:
        """
        Удаляет ссылку по умолчанию для указанного языка и темы.
        Возвращает True, если удаление прошло успешно, иначе False.
        """
        try:
            result = await self.db_session.execute(
                select(DefaultLink).where(
                    DefaultLink.language == language,
                    DefaultLink.topic == topic
                )
            )
            default_link = result.scalar_one_or_none()
            if default_link:
                await self.db_session.delete(default_link)
                await self.db_session.commit()
                logger.info(f"Удалена ссылка для языка '{language}' и темы '{topic}'.")
                return True
            else:
                logger.warning(f"Ссылка для языка '{language}' и темы '{topic}' не найдена.")
                return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Ошибка при удалении ссылки: {e}")
            return False

    async def list_default_links(self) -> list:
        """
        Возвращает список всех ссылок по умолчанию.
        """
        try:
            result = await self.db_session.execute(select(DefaultLink))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении списка ссылок: {e}")
            return []