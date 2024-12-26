"""
Middleware, автоматически регистрирующий пользователя в базе
(если это Message/CallbackQuery/PollAnswer и не бот).
"""

import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, PollAnswer
from typing import Any, Dict, Awaitable, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User
from bot.utils.time import get_current_time

logger = logging.getLogger(__name__)

class UserMiddleware(BaseMiddleware):
    """Добавляет пользователя в БД, если его там нет, пропускает, если бот или нет from_user."""

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
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
            select(User).where(User.telegram_id == telegram_id)
        )
        user_obj = result.scalar_one_or_none()

        if not user_obj:
            # Создаём новую запись
            new_user = User(
                telegram_id=telegram_id,
                username=username,
                subscription_status="active",
                created_at=get_current_time().replace(tzinfo=None),
                language=language
            )
            db_session.add(new_user)
            try:
                await db_session.commit()
                logger.info(f"Добавлен новый пользователь: {telegram_id}")
            except Exception as e:
                await db_session.rollback()
                logger.error(f"Ошибка при добавлении пользователя {telegram_id}: {e}")
        else:
            logger.debug(f"Пользователь {telegram_id} уже существует в базе.")

        # Передаём управление дальше
        return await handler(event, data)