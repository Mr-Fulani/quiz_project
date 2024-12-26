"""
Middleware, чтобы на каждый апдейт создавалась и передавалась в handler() 
новая асинхронная сессия (AsyncSession).
"""

import logging
from aiogram import BaseMiddleware
from typing import Callable, Awaitable, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware для передачи асинхронной сессии базы данных (AsyncSession)
    в каждый handler.
    """
    def __init__(self, session_maker: sessionmaker):
        """
        session_maker: это должен быть sessionmaker(bind=..., class_=AsyncSession),
        созданный где-то в main.py (чтобы не плодить лишние фабрики).
        """
        super().__init__()
        self.session_maker = session_maker

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """
        Создаём новую Session на каждый апдейт/событие, 
        передаём её в data["db_session"], и по завершении
        контроля - закрываем (через асинх. контекст).
        """
        async with self.session_maker() as db_session:  # type: AsyncSession
            data["db_session"] = db_session
            return await handler(event, data)