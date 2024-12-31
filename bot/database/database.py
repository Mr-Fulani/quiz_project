import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from bot.config import DATABASE_URL
from typing import AsyncGenerator


# Настройка логгера
logger = logging.getLogger(__name__)

# Создаем базу данных моделей
Base = declarative_base()



# Создаем асинхронный движок для подключения к базе данных
async_engine = create_async_engine(DATABASE_URL, echo=True)



# Создаем фабрику асинхронных сессий с использованием async_sessionmaker
AsyncSessionMaker = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession
)


# Функция получения асинхронной сессии с использованием asynccontextmanager
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionMaker() as session:
        try:
            yield session
        except Exception as e:
            logger.error("Ошибка в сессии базы данных. Откатываем транзакцию.")
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug("Сессия базы данных закрыта.")



