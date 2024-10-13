from aiogram import BaseMiddleware
from typing import Callable, Awaitable, Dict, Any
from sqlalchemy.orm import Session
from aiogram.types import Message

from database.database import AsyncSessionMaker




class DbSessionMiddleware(BaseMiddleware):
    """Middleware для передачи асинхронной сессии базы данных в каждый обработчик."""

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        # Создаем асинхронную сессию базы данных
        async with AsyncSessionMaker() as db_session:
            data["db_session"] = db_session  # Передаем сессию в обработчик
            return await handler(event, data)  # Передаем управление обработчику