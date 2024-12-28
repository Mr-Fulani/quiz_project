import logging
from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import DefaultLink, Task, MainFallbackLink

logger = logging.getLogger(__name__)

class DefaultLinkService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_default_link(self, language: str, topic: str) -> str:
        """
        Возвращает ссылку по умолчанию для указанного языка и темы из базы данных.
        Если ссылки нет, возвращает главную статическую ссылку.
        Если и её нет, возвращает заранее заданную ссылку.
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
                # Получаем главную статическую ссылку
                fallback_result = await self.db_session.execute(select(MainFallbackLink).limit(1))
                fallback_link = fallback_result.scalar_one_or_none()
                if fallback_link:
                    logger.info(f"Используется главная статическая ссылка: {fallback_link.link}")
                    return fallback_link.link
                else:
                    logger.warning(f"Главная статическая ссылка не найдена. Используется стандартная ссылка.")
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

    async def set_main_fallback_link(self, link: str) -> MainFallbackLink:
        """
        Устанавливает или обновляет главную статическую ссылку.
        """
        try:
            logger.info("Установка или обновление главной статической ссылки...")
            result = await self.db_session.execute(select(MainFallbackLink).limit(1))
            fallback_link = result.scalar_one_or_none()

            if not fallback_link:
                # Ссылка не установлена, добавляем новую
                fallback_link = MainFallbackLink(link=link)
                self.db_session.add(fallback_link)
                logger.info(f"Добавлена новая главная статическая ссылка: {link}")
            else:
                # Ссылка уже существует, обновляем её
                old_link = fallback_link.link
                fallback_link.link = link
                logger.info(f"Обновлена главная статическая ссылка. Была: {old_link}, стала: {link}")

            await self.db_session.commit()
            logger.info("Главная статическая ссылка успешно зафиксирована в базе данных.")

            return fallback_link
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Ошибка при установке главной статической ссылки: {e}")
            raise e

    async def remove_main_fallback_link(self) -> bool:
        """
        Удаляет главную статическую ссылку.
        Возвращает True, если удаление прошло успешно, иначе False.
        """
        try:
            logger.info("Попытка удаления главной статической ссылки...")
            result = await self.db_session.execute(select(MainFallbackLink).limit(1))
            fallback_link = result.scalar_one_or_none()
            if fallback_link:
                await self.db_session.delete(fallback_link)
                await self.db_session.commit()
                logger.info("Главная статическая ссылка удалена.")
                return True
            else:
                logger.warning("Главная статическая ссылка не найдена.")
                return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Ошибка при удалении главной статической ссылки: {e}")
            return False

    async def get_main_fallback_link(self) -> str:
        """
        Возвращает главную статическую ссылку. Если её нет, возвращает стандартную ссылку.
        """
        try:
            result = await self.db_session.execute(select(MainFallbackLink).limit(1))
            fallback_link = result.scalar_one_or_none()
            if fallback_link:
                logger.info(f"Главная статическая ссылка: {fallback_link.link}")
                return fallback_link.link
            else:
                logger.warning("Главная статическая ссылка не установлена. Используется стандартная ссылка.")
                return "https://t.me/proger_dude"
        except Exception as e:
            logger.error(f"Ошибка при получении главной статической ссылки: {e}")
            return "https://t.me/proger_dude"