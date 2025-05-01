import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, PollAnswer
from typing import Any, Dict, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models import TelegramUser
from bot.utils.time import get_current_time

logger = logging.getLogger(__name__)

class UserMiddleware(BaseMiddleware):
    """
    Middleware для автоматической регистрации пользователей в таблице telegram_users.
    Проверяет наличие пользователя по telegram_id и создаёт новую запись, если его нет.
    Обрабатывает события Message, CallbackQuery и PollAnswer, пропуская ботов и события без from_user.
    """

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обрабатывает входящее событие, проверяет или создаёт пользователя в базе и передаёт управление дальше.

        Args:
            handler (Callable): Следующий обработчик в цепочке middleware.
            event (Any): Входящее событие (Message, CallbackQuery, PollAnswer и др.).
            data (Dict[str, Any]): Данные, переданные в middleware, включая db_session.

        Returns:
            Any: Результат выполнения следующего обработчика.
        """
        logger.warning("=== UserMiddleware TRIGGERED! ===")
        db_session: AsyncSession = data.get("db_session")

        # Пытаемся понять, от кого событие
        from_user = None
        if isinstance(event, Message) and event.from_user:
            from_user = event.from_user
            logger.debug(f"Обработка Message от пользователя ID={from_user.id}")
        elif isinstance(event, CallbackQuery) and event.from_user:
            from_user = event.from_user
            logger.debug(f"Обработка CallbackQuery от пользователя ID={from_user.id}")
        elif isinstance(event, PollAnswer) and event.user:
            from_user = event.user
            logger.debug(f"Обработка PollAnswer от пользователя ID={from_user.id}")
        else:
            # Любые другие типы апдейтов, где нет from_user
            logger.debug(f"Событие {type(event).__name__} без from_user, пропускаем.")
            return await handler(event, data)

        # Если это бот, игнорируем
        if from_user.is_bot:
            logger.debug(f"Игнорируем событие от бота (ID={from_user.id}).")
            return await handler(event, data)

        telegram_id = from_user.id
        username = from_user.username or None
        language = getattr(from_user, "language_code", None) or "unknown"

        logger.info(f"Проверка пользователя с telegram_id={telegram_id}")

        # Проверяем наличие в БД
        result = await db_session.execute(
            select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
        )
        user_obj = result.scalar_one_or_none()

        if not user_obj:
            # Создаём новую запись
            new_user = TelegramUser(
                telegram_id=telegram_id,
                username=username,
                first_name=from_user.first_name or None,
                last_name=from_user.last_name or None,
                subscription_status="active",
                created_at=get_current_time().replace(tzinfo=None),
                language=language
            )
            db_session.add(new_user)
            try:
                await db_session.commit()
                logger.warning("<<< COMMIT DONE >>>")
                logger.info(f"Добавлен новый пользователь: {telegram_id}")
            except Exception as e:
                await db_session.rollback()
                logger.error(f"Ошибка при добавлении пользователя {telegram_id}: {e}")
        else:
            logger.debug(f"Пользователь {telegram_id} уже существует в базе.")

        # Передаём управление дальше
        return await handler(event, data)