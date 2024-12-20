# bot/services/default_link_service.py

import logging
from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import DefaultLink, Task

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
            logger.debug(f"Запрос на получение ссылки по умолчанию для языка '{language}' и темы '{topic}'.")
            result = await self.db_session.execute(
                select(DefaultLink).where(
                    (DefaultLink.language == language) &
                    (DefaultLink.topic == topic)
                )
            )

            default_link = result.scalar_one_or_none()

            if default_link:
                logger.info(f"Найдена ссылка по умолчанию для языка '{language}' и темы '{topic}': {default_link.link}")
                return default_link.link
            else:
                logger.warning(f"Ссылка по умолчанию для языка '{language}' и темы '{topic}' не найдена. Используется стандартная ссылка.")
                return "https://t.me/proger_dude"
        except Exception as e:
            logger.error(f"Ошибка при получении ссылки по умолчанию: {e}")
            return "https://t.me/proger_dude"

    async def add_default_link(self, language: str, topic: str, link: str) -> DefaultLink:
        """
        Добавляет или обновляет ссылку по умолчанию для указанного языка и темы.
        Логика:
        1. Проверяем, есть ли ссылка для (language, topic).
        2. Если есть — обновляем. Если нет — добавляем новую.
        3. Очищаем external_link у задач для этого языка и топика.
        4. Коммитим изменения.
        """
        try:
            # Шаг 1: Проверяем наличие ссылки
            logger.info(f"Проверка наличия ссылки для языка '{language}' и темы '{topic}'...")
            result = await self.db_session.execute(
                select(DefaultLink).where(
                    (DefaultLink.language == language) &
                    (DefaultLink.topic == topic)
                )
            )
            default_link = result.scalar_one_or_none()

            if not default_link:
                # Ссылка не найдена, добавляем новую
                default_link = DefaultLink(language=language, topic=topic, link=link)
                self.db_session.add(default_link)
                logger.info(f"Добавлена новая ссылка для языка '{language}' и темы '{topic}': {link}")
            else:
                # Ссылка уже существует, обновляем ее
                old_link = default_link.link
                default_link.link = link
                logger.info(f"Обновлена ссылка для языка '{language}' и темы '{topic}'. Была: {old_link}, стала: {link}")

            # Шаг 2: Очищаем external_link у соответствующих задач
            logger.info(f"Очищаем external_link у задач для языка '{language}' и темы '{topic}'...")
            await self.db_session.execute(
                update(Task)
                .where(Task.topic.has(name=topic))
                .where(Task.translations.any(language=language))
                .values(external_link=None)
            )
            logger.info(f"Поле external_link очищено у задач с темой '{topic}' и языком '{language}'.")

            # Шаг 3: Коммитим изменения
            await self.db_session.commit()
            logger.info("Изменения успешно зафиксированы в базе данных.")

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
            logger.info(f"Попытка удаления ссылки для языка '{language}' и темы '{topic}'...")
            result = await self.db_session.execute(
                select(DefaultLink).where(
                    (DefaultLink.language == language) &
                    (DefaultLink.topic == topic)
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
        Возвращает список всех ссылок по умолчанию из базы.
        Также выводит информацию о количестве найденных ссылок в лог.
        """
        try:
            logger.info("Запрос на получение списка всех ссылок по умолчанию...")
            result = await self.db_session.execute(select(DefaultLink))
            links = result.scalars().all()
            count = len(links)
            logger.info(f"Найдено ссылок по умолчанию: {count}")
            for dl in links:
                logger.info(f"Язык: {dl.language}, Тема: {dl.topic}, Ссылка: {dl.link}")
            return links
        except Exception as e:
            logger.error(f"Ошибка при получении списка ссылок: {e}")
            return []








