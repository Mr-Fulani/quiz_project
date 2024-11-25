# middlewares/db_session_middleware.py

import logging
from aiogram import BaseMiddleware
from typing import Callable, Awaitable, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from database.database import async_engine

logger = logging.getLogger(__name__)


# Создайте sessionmaker с асинхронным движком
AsyncSessionLocal = sessionmaker(
    async_engine, expire_on_commit=False, class_=AsyncSession
)


class DbSessionMiddleware(BaseMiddleware):
    """Middleware для передачи асинхронной сессии базы данных в каждый обработчик."""

    def __init__(self, session_maker: sessionmaker):
        super().__init__()
        self.session_maker = session_maker

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        # Создаем асинхронную сессию базы данных
        async with self.session_maker() as db_session:
            data["db_session"] = db_session  # Передаем сессию в обработчик
            return await handler(event, data)  # Передаем управление обработчику
